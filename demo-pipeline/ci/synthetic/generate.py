"""Dato sintético determinista para validar el modelo Ventas.

Misma semilla → mismos CSV → mismos resultados: por eso podemos tener "resultados dorados"
y un oráculo independiente. Además plantamos a propósito los casos que suelen romper medidas:
  · 29/02/2024 y cambio de año (31/12 → 01/01)
  · devoluciones (cantidad e importe negativos)
  · ventas de un cliente que no existe en la dimensión (fila "en blanco" en Power BI)
  · importes nulos
Salida: clientes.csv, productos.csv, ventas.csv y schema.json (tipos para Power Query y DuckDB).
"""
from __future__ import annotations

import sys

import argparse
import csv
import json
import random
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # consolas Windows en cp1252

SCHEMA = {
    "Clientes": {"id_cliente": "int", "nombre": "text", "segmento": "text", "region": "text"},
    "Productos": {"id_producto": "int", "producto": "text", "categoria": "text", "precio": "decimal", "coste_unitario": "decimal"},
    "Ventas": {"id_venta": "int", "fecha": "date", "id_cliente": "int", "id_producto": "int",
               "cantidad": "int", "importe": "decimal", "coste": "decimal"},
}
SEGMENTOS = ["Empresa", "Pyme", "Particular"]
REGIONES = ["Norte", "Sur", "Este", "Oeste", "Centro"]
CATEGORIAS = {"Bicicletas": (350, 2500), "Accesorios": (5, 120), "Ropa": (15, 180), "Componentes": (20, 600)}
CLIENTE_HUERFANO = 9999


def money(x: float) -> Decimal:
    return Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--rows", type=int, default=6000)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    rnd = random.Random(a.seed)
    a.out.mkdir(parents=True, exist_ok=True)

    clientes = [{"id_cliente": i, "nombre": f"Cliente {i:04d}", "segmento": rnd.choice(SEGMENTOS),
                 "region": rnd.choice(REGIONES)} for i in range(1, 401)]
    productos = []
    for i in range(1, 121):
        cat = rnd.choice(list(CATEGORIAS))
        lo, hi = CATEGORIAS[cat]
        precio = money(rnd.uniform(lo, hi))
        productos.append({"id_producto": i, "producto": f"{cat[:3].upper()}-{i:03d}", "categoria": cat,
                          "precio": precio, "coste_unitario": money(float(precio) * rnd.uniform(0.45, 0.8))})

    start, days = date(2024, 1, 1), (date(2025, 12, 31) - date(2024, 1, 1)).days
    fixed_dates = [date(2024, 2, 29), date(2024, 12, 31), date(2025, 1, 1)]
    ventas = []
    for i in range(1, a.rows + 1):
        prod = rnd.choice(productos)
        fecha = fixed_dates[i % 3] if i <= 30 else start + timedelta(days=rnd.randint(0, days))
        cantidad = rnd.randint(1, 6)
        if rnd.random() < 0.02:                       # devoluciones
            cantidad = -cantidad
        id_cliente = CLIENTE_HUERFANO if i % 500 == 0 else rnd.choice(clientes)["id_cliente"]
        importe = money(float(prod["precio"]) * cantidad)
        coste = money(float(prod["coste_unitario"]) * cantidad)
        ventas.append({"id_venta": i, "fecha": fecha.isoformat(), "id_cliente": id_cliente,
                       "id_producto": prod["id_producto"], "cantidad": cantidad,
                       "importe": "" if i % 997 == 0 else importe, "coste": coste})   # importes nulos

    for name, rows in (("Clientes", clientes), ("Productos", productos), ("Ventas", ventas)):
        with open(a.out / f"{name.lower()}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(SCHEMA[name]))
            w.writeheader()
            w.writerows(rows)
    (a.out / "schema.json").write_text(json.dumps(SCHEMA, indent=2), encoding="utf-8")
    print(f"OK semilla={a.seed}: {len(clientes)} clientes, {len(productos)} productos, {len(ventas)} ventas → {a.out}")


if __name__ == "__main__":
    main()
