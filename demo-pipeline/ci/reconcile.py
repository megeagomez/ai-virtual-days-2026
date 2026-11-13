"""Cuadre de datos: el modelo publicado (DAX) contra un oráculo independiente (SQL en DuckDB)
calculado sobre EXACTAMENTE el mismo CSV sintético que se inyectó en el modelo.

Golden dice "no ha cambiado"; el oráculo dice "es correcto". Si una medida está mal desde el
principio, la regresión no lo ve; el cuadre sí.

Cada check de tests/reconcile.yaml define `dax`, `sql` y `keys` (nº de columnas clave al
principio). El resto de columnas se comparan numéricamente con la tolerancia indicada.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import duckdb
import yaml

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # consolas Windows en cp1252

DUCK_TYPES = {"int": "BIGINT", "text": "VARCHAR", "decimal": "DECIMAL(18,2)", "date": "DATE"}
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def oracle(data: Path) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    schema = json.loads((data / "schema.json").read_text(encoding="utf-8"))
    for table, cols in schema.items():
        types = ", ".join(f"'{c}': '{DUCK_TYPES[t]}'" for c, t in cols.items())
        path = (data / f"{table.lower()}.csv").as_posix()
        con.execute(f"CREATE TABLE {table.lower()} AS SELECT * FROM read_csv('{path}', header=true, columns={{{types}}})")
    return con


def key(v) -> str:
    if v is None:
        return ""
    s = str(v)
    if ISO_DATE.match(s):
        return s[:10]
    if re.fullmatch(r"-?\d+\.0+", s):
        return s.split(".")[0]
    return s


def as_map(rows: list[list], nkeys: int) -> dict[tuple, list]:
    return {tuple(key(v) for v in r[:nkeys]): [float(v) if v is not None else None for v in r[nkeys:]] for r in rows}


def compare(dax_rows: list[list], sql_rows: list[list], nkeys: int, tol: float) -> tuple[float, list[str]]:
    d, s = as_map(dax_rows, nkeys), as_map(sql_rows, nkeys)
    problems, worst = [], 0.0
    for k in sorted(set(d) | set(s)):
        if k not in d or k not in s:
            problems.append(f"{k}: solo en {'DAX' if k in d else 'oráculo'}")
            continue
        for a, b in zip(d[k], s[k]):
            if a is None and b is None:
                continue
            delta = abs((a or 0.0) - (b or 0.0))
            worst = max(worst, delta)
            if delta > tol:
                problems.append(f"{k}: modelo={a} oráculo={b} (Δ {delta:.4f})")
    return worst, problems


def main() -> None:
    sys.path.insert(0, str(Path(__file__).parent))
    from pbi_rest import execute_dax, resolve

    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace")
    ap.add_argument("--dataset")
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--spec", type=Path, default=Path("tests/reconcile.yaml"))
    ap.add_argument("--oracle-only", action="store_true", help="Solo ejecuta el SQL (prueba local sin Power BI)")
    a = ap.parse_args()
    spec = yaml.safe_load(a.spec.read_text(encoding="utf-8"))
    tol = float(spec.get("tolerance", 0.01))
    con = oracle(a.data)
    if a.oracle_only:
        for chk in spec["checks"]:
            print(f"· {chk['name']}: {con.execute(chk['sql']).fetchall()[:5]}")
        return
    ws, ds = resolve(a.workspace, a.dataset)
    report = ["## ⚖️ Cuadre contra el oráculo sintético", "", f"Tolerancia: {tol}", "",
              "| Comprobación | Filas | Máx. Δ | Estado |", "|---|---:|---:|---|"]
    details, failed = [], 0
    for chk in spec["checks"]:
        dax_rows = [list(r.values()) for r in execute_dax(ws, ds, chk["dax"])]
        sql_rows = [list(r) for r in con.execute(chk["sql"]).fetchall()]
        worst, problems = compare(dax_rows, sql_rows, int(chk.get("keys", 0)), tol)
        status = "✅ cuadra" if not problems else "❌ descuadre"
        failed += bool(problems)
        report.append(f"| {chk['name']} | {len(sql_rows)} | {worst:.4f} | {status} |")
        if problems:
            details += [f"### {chk['name']}", *[f"- {p}" for p in problems[:10]]]
    text = "\n".join(report + [""] + details) + "\n"
    print(text)
    Path("build/reports").mkdir(parents=True, exist_ok=True)
    Path("build/reports/reconcile.md").write_text(text, encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(text)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
