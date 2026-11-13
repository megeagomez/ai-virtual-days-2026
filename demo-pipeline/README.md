# Pipeline de ejemplo · Power BI con GitHub Actions + PowerBiDeploymentMCP

Material de la charla **DevOps conversacional** (AI Virtual Days 2026). Copia este contenido en la raíz
del repo donde vive tu proyecto `.pbip`:

```
powerbi/
  Ventas.SemanticModel/          ← TMDL; contrato de orígenes Src_<Tabla> (ver abajo)
  Ventas.Report/                 ← PBIR
.github/workflows/powerbi-ci.yml ← la pipeline
.github/actions/setup-pbi/       ← Python + MCP + azure/login (OIDC) + auth az_cli
ci/
  synthetic/generate.py          ← dato sintético determinista (semilla)
  synthetic/inline_into_tmdl.py  ← embebe el CSV en las expresiones Src_* (sin gateway)
  pbi_rest.py                    ← refresh + executeQueries (lo que el MCP aún no expone)
  dax_regression.py              ← consultas vs resultados dorados
  reconcile.py                   ← cuadre DAX vs oráculo DuckDB
  promote_gate.ps1               ← convierte "Promoción cancelada" (exit 0) en fallo
  save_state.ps1                 ← persiste la DuckDB del MCP en la rama pbi-state
tests/
  dax/*.dax  golden/*.json  reconcile.yaml
```

## Flujo

| Disparador | Jobs |
|---|---|
| Pull request | `validate`: dato sintético → modelo CI → refresh → regresión DAX → cuadre |
| Push a `main` | `validate` → `deploy-dev` → `promote-int` → **aprobación** → `promote-prod` |
| Manual | igual que `main`, con `confirm_drift` y `update_golden` opcionales |

`validate` publica en un workspace **fuera de la cadena** (`Ventas [CI]`), así el dato sintético nunca
viaja con una promoción. La cadena Desarrollo → Integracion → Produccion usa los verbos del MCP:
`deploy` (desde el repo) y `promote` (de entorno a entorno, con detección de drift).

## Preparación (una vez)

1. **App registration + credencial federada** (OIDC) para el repo y para cada environment de GitHub
   (`repo:<org>/<repo>:environment:produccion`, …). Guarda `AZURE_CLIENT_ID` y `AZURE_TENANT_ID` como
   *variables* del repo; no hace falta ningún secreto.
2. **Tenant de Fabric/Power BI**: permitir que las entidades de servicio usen las API, y habilitar
   *Dataset Execute Queries REST API*. Añade la entidad de servicio como miembro/colaborador de los
   workspaces CI, Desarrollo, Integracion y Produccion.
3. **Environments de GitHub** `desarrollo`, `integracion`, `produccion`; en `produccion`, *required reviewers*.
4. **Estado del MCP**: crea los entornos y el proyecto (desde el chat con el agente o con el CLI) apuntando
   `POWERBI_MCP_DB_PATH` a `.pbi-state/metadata.duckdb`, y súbelo a una rama huérfana `pbi-state`:
   ```powershell
   $env:POWERBI_MCP_DB_PATH = "$PWD\.pbi-state\metadata.duckdb"
   python pbi_cli.py env-create Desarrollo  "WS Dev"  --stage-order 1
   python pbi_cli.py env-create Integracion "WS Int"  --stage-order 2
   python pbi_cli.py env-create Produccion  "WS Prod" --stage-order 3
   python pbi_cli.py project-create Ventas
   python pbi_cli.py project-add-artifact Ventas model  Ventas --folder "Ventas/Modelos"
   python pbi_cli.py project-add-artifact Ventas report Ventas --rebind Ventas --folder "Ventas/Informes"
   ```
5. **Contrato de orígenes en el modelo**: cada tabla lee de `expression Src_<Tabla>` en
   `definition/expressions.tmdl` y su partición solo hace `Src_<Tabla>`. Ejemplo en
   `tests/fixtures/Ventas.SemanticModel`. Medidas usadas por los tests: `[Ventas]`, `[Coste]`,
   `[Margen %]`, `[Clientes con compra]`, `[Ventas YTD]`; tabla `'Fecha'` con `[Fecha]`, `[Año]`, `[Mes]`.
6. Primera ejecución manual con `update_golden = true`, revisa los dorados y súbelos con un PR.

## Por qué así (lo que el agente descubrió al generar la pipeline)

- `pbi_cli.py promote` sin `--yes` ante drift imprime *Promoción cancelada* y **sale con código 0**:
  sin `promote_gate.ps1` la pipeline quedaría en verde sin haber promocionado.
- La caché de tokens del MCP usa **DPAPI** → `runs-on: windows-latest`.
- `auth --method az_cli` explícito: en modo `auto`, si no hubiera sesión az, el CLI caería a *device flow*
  y el job se quedaría esperando a un humano.
- La DuckDB del MCP es el **estado** (entornos, proyectos, hashes de lo promocionado). Un runner es
  efímero: sin `pbi-state` no hay detección de drift. `concurrency` evita escrituras simultáneas.
- `executeQueries` y el refresh son llamadas REST de Power BI que el MCP aún no expone → `pbi_rest.py`.
  Candidatas naturales a tools del MCP (`execute_dax`, `refresh_model`).
- Los PR desde forks no reciben token OIDC: `validate` solo funciona para ramas del propio repo.

## Probar en local lo que no necesita Power BI

```powershell
python ci/synthetic/generate.py --seed 20261107 --rows 6000 --out build/synthetic
python ci/synthetic/inline_into_tmdl.py --model tests/fixtures/Ventas.SemanticModel --data build/synthetic --out build/ci
python ci/reconcile.py --data build/synthetic --spec tests/reconcile.yaml --oracle-only
```
