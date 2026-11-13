#!/usr/bin/env python3
"""Validación offline de un proyecto PBIP antes de desplegarlo (no necesita Power BI).

Comprueba lo que suele romper un despliegue y que Desktop no siempre avisa:
  * todos los JSON del modelo y del informe se pueden parsear
  * el modelo tiene definition.pbism + definition/*.tmdl
  * el informe apunta (byPath) a una carpeta .SemanticModel que existe
  * no se ha colado la caché local (.pbi/cache.abf) ni ficheros de usuario en Git

Uso: python ci/validate_pbip.py src/Powerbi GreatAdventuresVentas
Escribe un resumen en $GITHUB_STEP_SUMMARY si existe.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

JSON_EXT = {".json", ".pbir", ".pbism", ".platform", ".pbip"}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    root, name = Path(sys.argv[1]), sys.argv[2]
    model, report = root / f"{name}.SemanticModel", root / f"{name}.Report"
    errors, info = [], []

    for folder in (model, report):
        if not folder.is_dir():
            errors.append(f"No existe la carpeta {folder}")
    if errors:
        return finish(errors, info)

    # 1. JSON válidos
    n_json = 0
    for f in list(model.rglob("*")) + list(report.rglob("*")):
        if f.is_file() and f.suffix in JSON_EXT and ".pbi" not in f.parts:
            n_json += 1
            try:
                json.loads(f.read_text(encoding="utf-8-sig"))
            except Exception as e:  # noqa: BLE001
                errors.append(f"JSON inválido: {f} → {e}")
    info.append(f"{n_json} ficheros JSON parseados")

    # 2. Modelo TMDL
    if not (model / "definition.pbism").is_file():
        errors.append("Falta definition.pbism en el modelo")
    tmdl = list((model / "definition").rglob("*.tmdl"))
    tables = list((model / "definition" / "tables").glob("*.tmdl"))
    measures = sum(f.read_text(encoding="utf-8-sig").count("\tmeasure ") for f in tables)
    if not tmdl:
        errors.append("El modelo no tiene ficheros TMDL")
    info.append(f"Modelo: {len(tmdl)} ficheros TMDL, {len(tables)} tablas, {measures} medidas")

    # 3. El informe apunta al modelo correcto
    pbir = report / "definition.pbir"
    if pbir.is_file():
        ref = json.loads(pbir.read_text(encoding="utf-8-sig")).get("datasetReference", {})
        by_path = (ref.get("byPath") or {}).get("path")
        if by_path and not (report / by_path).resolve().is_dir():
            errors.append(f"definition.pbir apunta a {by_path}, que no existe")
        info.append(f"Informe enlazado a: {by_path or ref.get('byConnection', '?')}")
    pages = list((report / "definition" / "pages").glob("*/page.json"))
    visuals = list((report / "definition" / "pages").glob("*/visuals/*/visual.json"))
    info.append(f"Informe: {len(pages)} páginas, {len(visuals)} visuales")

    # 4. Nada de caché ni ajustes locales versionados
    try:
        tracked = subprocess.run(["git", "ls-files", str(root)], capture_output=True, text=True, check=True).stdout
        bad = [p for p in tracked.splitlines() if p.endswith("cache.abf") or p.endswith("localSettings.json")]
        if bad:
            errors.append("Ficheros locales versionados (añádelos a .gitignore): " + ", ".join(bad))
    except Exception:  # noqa: BLE001 — fuera de Git no se comprueba
        pass

    return finish(errors, info)


def finish(errors, info) -> int:
    lines = ["### Validación PBIP", ""] + [f"- {i}" for i in info]
    lines += [f"- ❌ {e}" for e in errors] or ["- ✅ Sin errores"]
    text = "\n".join(lines)
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(text + "\n\n")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
