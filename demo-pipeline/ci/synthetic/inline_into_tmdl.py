"""Copia el modelo .SemanticModel y sustituye sus orígenes por el dato sintético embebido en M.

Contrato del modelo: cada tabla lee de una expresión compartida `Src_<Tabla>` en
definition/expressions.tmdl (p. ej. `expression Src_Ventas = ...`), y la partición de la tabla
solo hace `= Src_Ventas`. En producción esas expresiones apuntan al origen real; en CI este
script las reemplaza por el CSV comprimido (gzip + base64) — el mismo truco que usa
"Especificar datos" en Power BI Desktop. Resultado: un modelo sin orígenes de datos que se
refresca en el servicio sin gateway ni credenciales.
"""
from __future__ import annotations

import sys

import argparse
import base64
import gzip
import json
import re
import shutil
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # consolas Windows en cp1252

M_TYPES = {"int": "Int64.Type", "text": "type text", "decimal": "Currency.Type", "date": "type date"}


def m_expression(csv_path: Path, columns: dict[str, str]) -> list[str]:
    payload = base64.b64encode(gzip.compress(csv_path.read_bytes(), mtime=0)).decode()
    numeric = [c for c, t in columns.items() if t != "text"]
    types = ", ".join(f'{{"{c}", {M_TYPES[t]}}}' for c, t in columns.items())
    body = [
        "let",
        f'\tFuente = Csv.Document(Binary.Decompress(Binary.FromText("{payload}", BinaryEncoding.Base64), Compression.GZip), '
        '[Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),',
        "\tCabeceras = Table.PromoteHeaders(Fuente, [PromoteAllScalars=true]),",
        f'\tSinVacios = Table.ReplaceValue(Cabeceras, "", null, Replacer.ReplaceValue, {{{", ".join(json.dumps(c) for c in numeric)}}}),',
        f'\tTipado = Table.TransformColumnTypes(SinVacios, {{{types}}}, "en-US")',
        "in",
        "\tTipado",
    ]
    return ["\t\t" + line for line in body]


def replace_expression(lines: list[str], name: str, new_body: list[str]) -> list[str]:
    header = re.compile(rf"^expression\s+'?{re.escape(name)}'?\s*=\s*(.*)$")
    for i, line in enumerate(lines):
        m = header.match(line)
        if not m:
            continue
        j = i + 1
        if m.group(1).strip() and not m.group(1).strip().startswith("```"):
            pass  # expresión de una sola línea: no hay cuerpo indentado que saltar
        else:
            while j < len(lines) and (lines[j].strip() == "" or lines[j].startswith("\t\t")):
                j += 1
        return lines[:i] + [f"expression {name} ="] + new_body + [""] + lines[j:]
    raise SystemExit(f"No encuentro `expression {name}` en expressions.tmdl — revisa el contrato Src_<Tabla>")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=Path, required=True, help="Carpeta X.SemanticModel")
    ap.add_argument("--data", type=Path, required=True, help="Salida de generate.py")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    target = a.out / a.model.name
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(a.model, target)
    expr_file = target / "definition" / "expressions.tmdl"
    schema = json.loads((a.data / "schema.json").read_text(encoding="utf-8"))
    lines = expr_file.read_text(encoding="utf-8-sig").splitlines()
    for table, columns in schema.items():
        lines = replace_expression(lines, f"Src_{table}", m_expression(a.data / f"{table.lower()}.csv", columns))
        print(f"  Src_{table} ← {table.lower()}.csv")
    expr_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"OK modelo CI en {target}")


if __name__ == "__main__":
    main()
