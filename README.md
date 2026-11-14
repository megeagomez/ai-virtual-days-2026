# DevOps conversacional · AI Virtual Days 2026

Material de la charla sobre [PowerBiDeploymentMCP](https://github.com/megeagomez/PowerBiDeploymentMCP):
desplegar Power BI hablando con un agente y, con el mismo CLI, en GitHub Actions.

| Carpeta / fichero | Qué es |
|---|---|
| `devops-conversacional-aivd.html` | La presentación (un único HTML; se genera con `python src/build.py`) |
| `src/index.html`, `src/theme/`, `src/assets/` | Fuentes de la presentación |
| `src/Powerbi/` | Proyecto PBIP de ejemplo: modelo + informe `GreatAdventuresVentas` |
| `demos/GUION-DEMOS.md` | **Guion de las demos** con los prompts para copiar y pegar |
| `demos/Powerbi/` | PBIP `Ventas` e informe suelto `DashboardVentas` para la demo «publicar hablando» (diapo 10) |
| `demos/cambios/` | Cambios v2 (bueno) y v3 (malo, a propósito) para enseñar versiones y rollback |
| `demos/sin-mcp/` | Plan B de la demo sin MCP: despliegue con la API REST de Fabric a mano |
| `.github/workflows/` | `powerbi-cicd.yml` (dev → DEV, PR → PROD) y `rollback-prod.yml` |
| `ci/` | `validate_pbip.py` (validación offline) y `deploy.ps1` (despliegue con el CLI del MCP) |
| `demo-pipeline/` | Variante avanzada: dato sintético, regresión DAX, cuadre y cadena DEV → INT → PROD |

## El pipeline

| Evento | Qué pasa |
|---|---|
| push a `dev` | `validate` → `deploy-dev`: publica el PBIP en **AIVD Ventas DEV** |
| pull request a `main` | `validate` + `plan-prod`: qué hay en PROD y qué ficheros cambian |
| merge en `main` | `validate` → `deploy-prod`: publica en **AIVD Ventas PROD** y crea la Release `prod-AAAAMMDD-HHMMSS` con el PBIP |
| manual `rollback-prod` | redespliega el PBIP de una Release concreta (y lo registra como versión nueva) |

`main` está protegida: solo admite cambios por PR con el check `validate` en verde.
El despliegue usa `pbi_cli.py upload-model` / `upload-report --rebind`, fijado a un commit concreto del MCP.

## Puesta en marcha (una vez)

1. **App registration** (PyUploader) → *Certificados y secretos → Credenciales federadas → GitHub Actions*, organización
   `megeagomez`, repositorio `ai-virtual-days-2026`, tres credenciales:
   - Entorno `dev` → `repo:megeagomez/ai-virtual-days-2026:environment:dev`
   - Entorno `prod` → `repo:megeagomez/ai-virtual-days-2026:environment:prod`
   - Pull request → `repo:megeagomez/ai-virtual-days-2026:pull_request`

   Alternativa sin OIDC: guarda el secreto del app registration como secret `AZURE_CLIENT_SECRET` del repo.
2. **Fabric**: el tenant debe permitir que las entidades de servicio llamen a las API públicas de Fabric, y el service principal
   tiene que ser *Contributor* de `AIVD Ventas DEV` y `AIVD Ventas PROD`.
3. **Variables del repo**: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID` (y opcionalmente `PBI_WS_DEV`, `PBI_WS_PROD`).
4. **Environments** `dev` y `prod`, y protección de `main` (PR obligatorio + check `validate`).
5. **Datos**: en cada workspace, credenciales del origen (OAuth2) y un refresco. Solo la primera vez: los despliegues
   posteriores sustituyen la definición del modelo sin borrar los datos cargados.
