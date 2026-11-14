#!/usr/bin/env python3
"""
ci/perf_gate.py — Puerta de rendimiento de consultas DAX.

Compara tiempos reales de PROD (baseline) contra DEV (candidato) usando
executeQueries. Falla si alguna página tarda ≥ PERF_MAX_RATIO × baseline
y el candidato supera PERF_MIN_MS en total por página.

Uso típico (GitHub Actions):
  python ci/perf_gate.py \\
    --json tests/perf/baseline-performance-analyzer.json \\
    --pbip-dir src/Powerbi/GreatAdventuresVentas.Report/definition/pages \\
    --baseline-ws "AIVD Ventas PROD" \\
    --candidate-ws "AIVD Ventas DEV" \\
    --dataset GreatAdventuresVentas

Modo json (compara contra tiempos de Power BI Desktop, solo local):
  python ci/perf_gate.py --baseline json ...
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import statistics
import subprocess
import sys
import time
from typing import Optional

import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

API = "https://api.powerbi.com/v1.0/myorg"
RESOURCE = "https://analysis.windows.net/powerbi/api"
_token: Optional[str] = None

PERF_MAX_RATIO = float(os.environ.get("PERF_MAX_RATIO", "2.0"))
PERF_MIN_MS = float(os.environ.get("PERF_MIN_MS", "500"))
DEFAULT_RUNS = 3
DEFAULT_WARMUP = 1


# ──────────────────────────────── HTTP layer ────────────────────────────────

def _get_token() -> str:
    global _token
    if _token is None:
        az = shutil.which("az") or shutil.which("az.cmd")
        if not az:
            sys.exit("No se encuentra Azure CLI (az).")
        _token = subprocess.check_output(
            [az, "account", "get-access-token", "--resource", RESOURCE, "--query", "accessToken", "-o", "tsv"],
            text=True,
        ).strip()
    return _token


def _call(method: str, path: str, **kw) -> requests.Response:
    for attempt in range(5):
        r = requests.request(
            method, f"{API}{path}",
            headers={"Authorization": f"Bearer {_get_token()}"},
            timeout=120, **kw,
        )
        if r.status_code == 429 or r.status_code >= 500:
            wait = int(r.headers.get("Retry-After", 2 ** attempt * 5))
            print(f"  … {r.status_code}, reintento en {wait}s")
            time.sleep(wait)
            continue
        if r.status_code >= 400:
            sys.exit(f"{method} {path} → {r.status_code}: {r.text[:800]}")
        return r
    sys.exit(f"{method} {path}: agotados los reintentos")


def _workspace_id(name: str) -> str:
    safe = name.replace("'", "''")
    groups = _call("GET", "/groups", params={"$filter": f"name eq '{safe}'"}).json()["value"]
    if not groups:
        sys.exit(f"Workspace no encontrado o sin acceso: {name}")
    return groups[0]["id"]


def _dataset_id(ws_id: str, name: str) -> str:
    for d in _call("GET", f"/groups/{ws_id}/datasets").json()["value"]:
        if d["name"] == name:
            return d["id"]
    sys.exit(f"Modelo semántico no encontrado: {name}")


def _time_dax(ws_id: str, ds_id: str, query: str) -> float:
    """Ejecuta una consulta DAX y devuelve el tiempo en ms. Lanza RuntimeError en error semántico."""
    t0 = time.perf_counter()
    body = {"queries": [{"query": query}], "serializerSettings": {"includeNulls": True}}
    res = _call("POST", f"/groups/{ws_id}/datasets/{ds_id}/executeQueries", json=body).json()
    elapsed_ms = (time.perf_counter() - t0) * 1000
    for result in res.get("results", []):
        if "error" in result:
            raise RuntimeError(result["error"].get("message", str(result["error"])))
    return elapsed_ms


# ──────────────────────────── JSON/PBIR parsing ─────────────────────────────

def _load_json(path: str) -> dict:
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def _build_page_map(pages_dir: str) -> dict[str, str]:
    """Devuelve {visualId → page display name} leyendo el PBIR."""
    page_map: dict[str, str] = {}
    p = pathlib.Path(pages_dir)
    if not p.exists():
        print(f"⚠  Directorio de páginas no encontrado: {pages_dir}")
        return page_map
    for page_folder in sorted(p.iterdir()):
        if not page_folder.is_dir():
            continue
        page_json_path = page_folder / "page.json"
        if not page_json_path.exists():
            continue
        try:
            page_data = json.loads(page_json_path.read_text(encoding="utf-8-sig"))
            display_name = page_data.get("displayName", page_folder.name)
        except Exception:
            display_name = page_folder.name
        visuals_dir = page_folder / "visuals"
        if visuals_dir.exists():
            for visual_folder in visuals_dir.iterdir():
                if visual_folder.is_dir():
                    page_map[visual_folder.name] = display_name
    return page_map


def _extract_queries(data: dict, page_map: dict[str, str]) -> dict[str, list[dict]]:
    """
    Extrae consultas DAX del JSON del Performance Analyzer, agrupadas por página.

    La cadena de parentId es:
      Execute DAX Query → Execute Semantic Query → Query → Visual Container Lifecycle
    """
    events: dict[str, dict] = {e["id"]: e for e in data["events"] if "id" in e}
    result: dict[str, list[dict]] = {}
    seen: set[tuple[str, str]] = set()

    for ev in data["events"]:
        if ev.get("name") != "Execute DAX Query":
            continue
        qt = ev.get("metrics", {}).get("QueryText", "")
        if not qt:
            continue
        # Excluye DMV y consultas de sistema
        if qt.lstrip().upper().startswith("SELECT"):
            continue

        # Sube la cadena: EDQ → ESQ → Query → VCL
        ese = events.get(ev.get("parentId", ""))
        if not ese or ese.get("name") != "Execute Semantic Query":
            continue
        query_ev = events.get(ese.get("parentId", ""))
        if not query_ev or query_ev.get("name") != "Query":
            continue
        vcl = events.get(query_ev.get("parentId", ""))
        if not vcl or vcl.get("name") != "Visual Container Lifecycle":
            continue

        visual_id = vcl.get("metrics", {}).get("visualId", "")
        if not visual_id:
            vcl_id = vcl.get("id", "")
            visual_id = vcl_id.split("-")[0] if vcl_id else ""
        visual_title = vcl.get("metrics", {}).get("visualTitle", visual_id)
        page_name = page_map.get(visual_id, "Sin página")

        key = (visual_id, qt)
        if key in seen:
            continue
        seen.add(key)

        # Duración Desktop (referencia informativa; no se usa en modo service)
        desktop_ms = 0.0
        if "start" in ev and "end" in ev:
            try:
                from datetime import datetime
                s = datetime.fromisoformat(ev["start"].replace("Z", "+00:00"))
                e2 = datetime.fromisoformat(ev["end"].replace("Z", "+00:00"))
                desktop_ms = (e2 - s).total_seconds() * 1000
            except Exception:
                pass

        if page_name not in result:
            result[page_name] = []
        result[page_name].append({
            "visual_id": visual_id,
            "visual_title": visual_title,
            "query_text": qt,
            "desktop_ms": desktop_ms,
        })

    return result


# ──────────────────────────── Timing ────────────────────────────────────────

def _measure(ws_id: str, ds_id: str, query: str, runs: int, warmup: int) -> Optional[float]:
    """Warmup + N ejecuciones, devuelve la mediana en ms o None si hay error."""
    timings: list[float] = []
    for i in range(warmup + runs):
        try:
            ms = _time_dax(ws_id, ds_id, query)
        except Exception as exc:
            if i >= warmup:
                print(f"      ⚠  Error en query: {str(exc)[:120]}")
                return None
            continue
        if i >= warmup:
            timings.append(ms)
    return statistics.median(timings) if timings else None


# ──────────────────────────── Summary ───────────────────────────────────────

def _build_summary(page_results: dict, args: argparse.Namespace, baseline_from_json: bool) -> str:
    lines = [
        "## 🏎  perf-gate · Degradación DAX",
        "",
        f"| Página | Baseline (ms) | Candidato (ms) | Ratio | Estado |",
        f"|--------|:-------------:|:--------------:|:-----:|--------|",
    ]
    for page_name, r in sorted(page_results.items()):
        status = "❌ **FALLO**" if r["degraded"] else "✅"
        bold = r["degraded"]
        pn = f"**{page_name}**" if bold else page_name
        base = f"{r['baseline_ms']:.0f}" if r.get("baseline_ms") else "—"
        cand = f"{r['candidate_ms']:.0f}" if r.get("candidate_ms") else "—"
        ratio_val = r.get("ratio")
        ratio = f"{ratio_val:.2f}×" if ratio_val and ratio_val != float("inf") else "—"
        lines.append(f"| {pn} | {base} | {cand} | {ratio} | {status} |")

    lines += [
        "",
        f"> **Regla:** falla si `ratio ≥ {PERF_MAX_RATIO}` **y** candidato total `≥ {PERF_MIN_MS} ms` por página.",
        f"> **Medición:** {args.warmup} ejecución(es) de calentamiento descartada(s) + {args.runs} medidas → mediana.",
        f"> **Baseline:** {'tiempos del JSON de Power BI Desktop _(solo referencia; Desktop ≠ servicio)_' if baseline_from_json else f'workspace **{args.baseline_ws}** (versión actual en servicio)'}.",
        f"> **Candidato:** workspace **{args.candidate_ws}**.",
        "",
        "> ⚠ El tiempo de _render_ de los visuales no es medible con `executeQueries`; "
        "solo se miden las consultas DAX.",
        "",
    ]

    # Consulta más lenta de cada página degradada
    degraded = {k: v for k, v in page_results.items() if v.get("degraded")}
    if degraded:
        lines.append("### Consultas más lentas de páginas con degradación")
        lines.append("")
        for page_name, r in sorted(degraded.items()):
            sq = r.get("slowest_query", "")
            if sq:
                lines.append(f"**{page_name}** — consulta más lenta del candidato:")
                lines.append("")
                lines.append("```dax")
                lines.append(sq[:600])
                lines.append("```")
                lines.append("")

    return "\n".join(lines)


# ──────────────────────────── Main ──────────────────────────────────────────

def run(args: argparse.Namespace) -> int:
    data = _load_json(args.json)
    page_map = _build_page_map(args.pbip_dir)
    pages_queries = _extract_queries(data, page_map)

    if not pages_queries:
        print("⚠  No se encontraron consultas DAX con QueryText en el JSON de baseline.")
        return 0

    total_q = sum(len(v) for v in pages_queries.values())
    print(f"Páginas con consultas DAX: {len(pages_queries)}  |  Consultas únicas: {total_q}")
    print(f"Regla: ratio ≥ {PERF_MAX_RATIO}× y candidato ≥ {PERF_MIN_MS} ms → FALLO")
    print()

    baseline_from_json = args.baseline == "json"

    cand_ws_id = _workspace_id(args.candidate_ws)
    cand_ds_id = _dataset_id(cand_ws_id, args.dataset)
    print(f"Candidato : {args.candidate_ws!r} / {args.dataset} ({cand_ds_id[:8]}…)")

    if not baseline_from_json:
        base_ws_id = _workspace_id(args.baseline_ws)
        base_ds_id = _dataset_id(base_ws_id, args.dataset)
        print(f"Baseline  : {args.baseline_ws!r} / {args.dataset} ({base_ds_id[:8]}…)")
    else:
        base_ws_id = base_ds_id = ""
        print("Baseline  : tiempos del JSON de Power BI Desktop (referencia)")
    print()

    page_results: dict[str, dict] = {}
    degraded_pages: list[str] = []

    for page_name, queries in sorted(pages_queries.items()):
        print(f"📄  {page_name}  ({len(queries)} consultas)")
        page_base_total = 0.0
        page_cand_total = 0.0
        page_failed = False
        slowest_q_text = ""
        slowest_q_cand_ms = 0.0
        q_evidence: list[dict] = []

        for q in queries:
            qt = q["query_text"]
            qt_preview = qt[:60].replace("\n", " ").replace("\r", "").strip()
            print(f"   • {q['visual_title']}: {qt_preview}…")

            if baseline_from_json:
                base_ms: Optional[float] = q["desktop_ms"]
                print(f"     baseline (Desktop): {base_ms:.0f} ms")
            else:
                base_ms = _measure(base_ws_id, base_ds_id, qt, args.runs, args.warmup)
                if base_ms is None:
                    print("     ⚠  Falló en PROD, omitiendo esta consulta")
                    continue
                print(f"     baseline (PROD) : {base_ms:.0f} ms")

            cand_ms = _measure(cand_ws_id, cand_ds_id, qt, args.runs, args.warmup)
            if cand_ms is None:
                print("     ❌ Falló en DEV (éxito en baseline) → FALLO")
                page_failed = True
                cand_ms_display: Optional[float] = None
                ratio_display: Optional[float] = None
            else:
                ratio_v = cand_ms / base_ms if base_ms and base_ms > 0 else float("inf")
                print(f"     candidato (DEV) : {cand_ms:.0f} ms  ratio: {ratio_v:.2f}×")
                cand_ms_display = cand_ms
                ratio_display = ratio_v
                page_cand_total += cand_ms
                if cand_ms > slowest_q_cand_ms:
                    slowest_q_cand_ms = cand_ms
                    slowest_q_text = qt

            page_base_total += base_ms if base_ms else 0
            q_evidence.append({
                "visual_id": q["visual_id"],
                "visual_title": q["visual_title"],
                "desktop_ms": q["desktop_ms"],
                "baseline_ms": base_ms,
                "candidate_ms": cand_ms_display,
                "ratio": ratio_display,
                "failed_in_candidate": cand_ms is None,
            })

        if not q_evidence:
            continue

        page_ratio = (
            page_cand_total / page_base_total
            if page_base_total > 0
            else (float("inf") if page_cand_total > 0 else 1.0)
        )
        is_degraded = page_failed or (
            page_ratio >= PERF_MAX_RATIO and page_cand_total >= PERF_MIN_MS
        )
        status = "❌ FALLO" if is_degraded else "✅ OK"
        print(
            f"   {status}  baseline={page_base_total:.0f} ms  "
            f"candidato={page_cand_total:.0f} ms  ratio={page_ratio:.2f}×"
        )
        print()

        page_results[page_name] = {
            "baseline_ms": page_base_total,
            "candidate_ms": page_cand_total,
            "ratio": page_ratio,
            "degraded": is_degraded,
            "failed": page_failed,
            "slowest_query": slowest_q_text[:600],
            "queries": q_evidence,
        }

        if is_degraded:
            degraded_pages.append(page_name)

    # Step summary
    summary_text = _build_summary(page_results, args, baseline_from_json)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(summary_text + "\n")

    # Evidence JSON (artifact)
    evidence_dir = pathlib.Path(args.evidence_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    import datetime
    evidence = {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "baseline": args.baseline_ws if not baseline_from_json else "json",
        "candidate_ws": args.candidate_ws,
        "dataset": args.dataset,
        "perf_max_ratio": PERF_MAX_RATIO,
        "perf_min_ms": PERF_MIN_MS,
        "runs": args.runs,
        "warmup": args.warmup,
        "pages": page_results,
    }
    ev_file = evidence_dir / "perf-evidence.json"
    ev_file.write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Evidencias → {ev_file}")

    if degraded_pages:
        print(f"\n❌  Degradación detectada en: {', '.join(degraded_pages)}")
        return 1

    print("✅  Sin degradación de rendimiento.")
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description="Puerta de rendimiento DAX")
    p.add_argument("--json", required=True,
                   help="Ruta al JSON del Performance Analyzer de Power BI Desktop")
    p.add_argument("--pbip-dir", required=True,
                   help="Ruta a .../GreatAdventuresVentas.Report/definition/pages")
    p.add_argument("--baseline", default="service",
                   help="'service' (mide contra baseline-ws) o 'json' (tiempos de Desktop)")
    p.add_argument("--baseline-ws", default=os.environ.get("WS_PROD", "AIVD Ventas PROD"),
                   help="Workspace baseline (PROD). Ignorado con --baseline json")
    p.add_argument("--candidate-ws", default=os.environ.get("WS_DEV", "AIVD Ventas DEV"),
                   help="Workspace candidato (DEV)")
    p.add_argument("--dataset", default=os.environ.get("PBI_NAME", "GreatAdventuresVentas"),
                   help="Nombre del modelo semántico")
    p.add_argument("--runs", type=int, default=DEFAULT_RUNS,
                   help=f"Ejecuciones medidas por consulta (defecto: {DEFAULT_RUNS})")
    p.add_argument("--warmup", type=int, default=DEFAULT_WARMUP,
                   help=f"Ejecuciones de calentamiento descartadas (defecto: {DEFAULT_WARMUP})")
    p.add_argument("--evidence-dir", default="perf-evidence",
                   help="Directorio de salida para el JSON de evidencias")
    args = p.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
