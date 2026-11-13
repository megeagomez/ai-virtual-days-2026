"""Llamadas REST de Power BI que el MCP todavía no expone como tool: refresh y executeQueries.

El token sale de la misma sesión `az login` (OIDC) que usa el MCP en el runner.
Uso CLI:  python ci/pbi_rest.py refresh --workspace "Ventas [CI]" --dataset Ventas --timeout 900
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time

import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # consolas Windows en cp1252

API = "https://api.powerbi.com/v1.0/myorg"
RESOURCE = "https://analysis.windows.net/powerbi/api"
_token: str | None = None


def token() -> str:
    global _token
    if _token is None:
        az = shutil.which("az") or shutil.which("az.cmd")
        if not az:
            sys.exit("No se encuentra Azure CLI (az). ¿Falta azure/login?")
        _token = subprocess.check_output(
            [az, "account", "get-access-token", "--resource", RESOURCE, "--query", "accessToken", "-o", "tsv"],
            text=True,
        ).strip()
    return _token


def _call(method: str, path: str, **kw) -> requests.Response:
    for attempt in range(5):
        r = requests.request(method, f"{API}{path}", headers={"Authorization": f"Bearer {token()}"}, timeout=120, **kw)
        if r.status_code == 429 or r.status_code >= 500:
            wait = int(r.headers.get("Retry-After", 2 ** attempt * 5))
            print(f"  … {r.status_code}, reintento en {wait}s")
            time.sleep(wait)
            continue
        if r.status_code >= 400:
            sys.exit(f"{method} {path} → {r.status_code}: {r.text[:800]}")
        return r
    sys.exit(f"{method} {path}: agotados los reintentos")


def workspace_id(name: str) -> str:
    safe = name.replace("'", "''")
    groups = _call("GET", "/groups", params={"$filter": f"name eq '{safe}'"}).json()["value"]
    if not groups:
        sys.exit(f"Workspace no encontrado o sin acceso: {name}")
    return groups[0]["id"]


def dataset_id(ws_id: str, name: str) -> str:
    for d in _call("GET", f"/groups/{ws_id}/datasets").json()["value"]:
        if d["name"] == name:
            return d["id"]
    sys.exit(f"Modelo semántico no encontrado: {name}")


def resolve(workspace: str, dataset: str) -> tuple[str, str]:
    ws = workspace_id(workspace)
    return ws, dataset_id(ws, dataset)


def refresh(workspace: str, dataset: str, timeout: int = 900) -> None:
    ws, ds = resolve(workspace, dataset)
    started = time.time()
    r = _call("POST", f"/groups/{ws}/datasets/{ds}/refreshes", json={"notifyOption": "NoNotification"})
    request_id = r.headers.get("RequestId") or r.headers.get("x-ms-request-id")
    print(f"Refresh solicitado ({request_id or 'sin requestId'}) para {workspace}/{dataset}")
    while time.time() - started < timeout:
        time.sleep(10)
        history = _call("GET", f"/groups/{ws}/datasets/{ds}/refreshes", params={"$top": 5}).json()["value"]
        mine = next((h for h in history if request_id and h.get("requestId") == request_id), history[0] if history else None)
        status = (mine or {}).get("status", "Unknown")
        print(f"  estado: {status}")
        if status == "Completed":
            return
        if status in ("Failed", "Disabled", "Cancelled"):
            sys.exit(f"Refresh {status}: {mine.get('serviceExceptionJson', '')}")
    sys.exit(f"Refresh sin terminar tras {timeout}s")


def execute_dax(ws: str, ds: str, query: str) -> list[dict]:
    body = {"queries": [{"query": query}], "serializerSettings": {"includeNulls": True}}
    res = _call("POST", f"/groups/{ws}/datasets/{ds}/executeQueries", json=body).json()
    result = res["results"][0]
    if "error" in result:
        raise RuntimeError(result["error"])
    return result["tables"][0]["rows"]


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("refresh")
    pr.add_argument("--workspace", required=True)
    pr.add_argument("--dataset", required=True)
    pr.add_argument("--timeout", type=int, default=900)
    a = p.parse_args()
    if a.cmd == "refresh":
        refresh(a.workspace, a.dataset, a.timeout)
