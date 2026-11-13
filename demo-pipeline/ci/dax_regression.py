"""Regresión de consultas: cada tests/dax/<nombre>.dax se ejecuta contra el modelo publicado en CI
y su resultado se compara con tests/golden/<nombre>.json (obtenido con la misma semilla sintética).

Golden = "esto no ha cambiado". Si una medida cambia a propósito, se regenera el dorado
(workflow_dispatch con update_golden) y el cambio queda revisado en el PR.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from pbi_rest import execute_dax, resolve

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # consolas Windows en cp1252

DECIMALS = 6


def normalize(rows: list[dict]) -> dict:
    columns = list(rows[0].keys()) if rows else []
    norm = []
    for r in rows:
        out = []
        for c in columns:
            v = r.get(c)
            if isinstance(v, float):
                v = round(v, DECIMALS)
                if v == int(v):
                    v = int(v)
            out.append(v)
        norm.append(out)
    norm.sort(key=lambda row: json.dumps(row, default=str))
    return {"columns": columns, "rows": norm}


def diff(expected: dict, actual: dict, limit: int = 8) -> list[str]:
    msgs = []
    if expected["columns"] != actual["columns"]:
        msgs.append(f"columnas: {expected['columns']} → {actual['columns']}")
    exp = {json.dumps(r, default=str) for r in expected["rows"]}
    act = {json.dumps(r, default=str) for r in actual["rows"]}
    for r in sorted(exp - act)[:limit]:
        msgs.append(f"− {r}")
    for r in sorted(act - exp)[:limit]:
        msgs.append(f"+ {r}")
    if len(expected["rows"]) != len(actual["rows"]):
        msgs.append(f"filas: {len(expected['rows'])} → {len(actual['rows'])}")
    return msgs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--tests", type=Path, default=Path("tests/dax"))
    ap.add_argument("--golden", type=Path, default=Path("tests/golden"))
    ap.add_argument("--update-golden", action="store_true")
    a = ap.parse_args()
    ws, ds = resolve(a.workspace, a.dataset)
    a.golden.mkdir(parents=True, exist_ok=True)
    report = ["## 🧪 Regresión de consultas DAX", "", "| Consulta | Filas | Estado |", "|---|---:|---|"]
    details, failed = [], 0
    for test in sorted(a.tests.glob("*.dax")):
        actual = normalize(execute_dax(ws, ds, test.read_text(encoding="utf-8")))
        gold = a.golden / f"{test.stem}.json"
        if a.update_golden:
            gold.write_text(json.dumps(actual, indent=1, ensure_ascii=False), encoding="utf-8")
            report.append(f"| `{test.stem}` | {len(actual['rows'])} | 📝 dorado regenerado |")
            continue
        if not gold.exists():
            failed += 1
            report.append(f"| `{test.stem}` | {len(actual['rows'])} | ❌ sin dorado (lanza update_golden) |")
            continue
        changes = diff(json.loads(gold.read_text(encoding="utf-8")), actual)
        if changes:
            failed += 1
            report.append(f"| `{test.stem}` | {len(actual['rows'])} | ❌ cambió |")
            details += [f"### {test.stem}", "```diff", *changes, "```"]
        else:
            report.append(f"| `{test.stem}` | {len(actual['rows'])} | ✅ igual |")
    text = "\n".join(report + [""] + details) + "\n"
    print(text)
    Path("build/reports").mkdir(parents=True, exist_ok=True)
    Path("build/reports/dax_regression.md").write_text(text, encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(text)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    main()
