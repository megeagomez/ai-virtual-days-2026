# Guion de demos · DevOps conversacional (AI Virtual Days 2026)

Los bloques `text` son **prompts para copiar y pegar** en el chat. Los bloques `powershell` se escriben en la terminal.
Diapos asociadas: 10 (Demo 0), 13–15 (Demo 1) y 29–30 (Demos 2 y 3).

| Pieza | Valor |
|---|---|
| PBIP | `D:\Presentaciones\2026\11. AI VirtualDAys\src\Powerbi` → modelo + informe `GreatAdventuresVentas` |
| Workspaces del pipeline | `AIVD Ventas DEV` · `AIVD Ventas PROD` |
| Demo 0 (publicar hablando) | PBIP `demos\Powerbi\Ventas` (copia de la de `src` renombrada a `Ventas`) · informe suelto `demos\Powerbi\Sueltos\DashboardVentas.Report` · workspace `AIVD Ventas Demo` |
| Workspaces de la demo agéntica | `AIVD Demo Agente MCP` · `AIVD Demo Agente sin MCP` (vacíos) |
| Repo | `github.com/megeagomez/ai-virtual-days-2026` · ramas `dev` y `main` (sellada) |
| Cuenta Fabric | `miguel.egea@midatalab.com` (az login) · cuenta GitHub: `megeagomez` |

---

## Antes de la charla (checklist)

- [ ] `az login` con la cuenta de Fabric y `gh auth status` en verde con `megeagomez`.
- [ ] **Datos en AIVD Ventas Demo** (modelo `Ventas`): igual que abajo, credenciales OAuth2 + *Actualizar ahora*. Sin datos, el «antes» de la Demo 0 sale vacío.
- [ ] Demo 0 en su estado inicial: `./demos/Powerbi/margen-pct.ps1 -Deshacer` y en `AIVD Ventas Demo` solo `Ventas` (sin `DashboardVentas`).
- [ ] **Datos en DEV y PROD**: en cada workspace → modelo `GreatAdventuresVentas` → *Configuración → Credenciales del origen de datos* → OAuth2 → *Actualizar ahora*. Solo una vez: los despliegues posteriores (`updateDefinition`) **no borran los datos**.
- [ ] Workspaces de la demo agéntica vacíos: `./demos/reset-demo.ps1`.
- [ ] Repo en `dev`, sin cambios pendientes y con `src` en v1 (`git status`, `git log --oneline -3`).
- [ ] Release v1 en PROD ya creada (`gh release list`): así el rollback tiene a dónde volver.
- [ ] Pestañas abiertas: portal de los 4 workspaces · `Actions` · `Releases` · esta guía.
- [ ] Plan B: `demos/sin-mcp/deploy-rest.ps1` abierto en VS Code; ensayo grabado de las Demos 2–3 por si la cola de runners va lenta.

---

## Demo 0 · Publicar hablando (≈5 min · diapo 10)

**Idea**: quien no programa publica, actualiza y reenlaza informes hablando, y el «Reemplazar» no borra los datos.
Claude Desktop con `powerbi-mcp-deploy` activo y `fabric` desactivado. Abre `demos\Powerbi\Ventas\Ventas.pbip` en Desktop.

1. En el portal, enseña el informe `Ventas` de **AIVD Ventas Demo** con sus cifras: esto es el «antes».

```text
Con powerbi-mcp-deploy: lista los workspaces que tengan "Demo" en el nombre y dime qué hay publicado en "AIVD Ventas Demo".
```

2. En Desktop, en la tabla *Ventas*, nueva medida y **guarda** el .pbip:
   `Margen % = DIVIDE([Ventas netas] - [Coste], [Ventas netas])` (formato porcentaje).
   Si el tiempo aprieta: cierra Desktop y ejecuta `./demos/Powerbi/margen-pct.ps1`.

```text
Con powerbi-mcp-deploy: sube el proyecto Power BI de D:\Presentaciones\2026\11. AI VirtualDAys\demos\Powerbi\Ventas (modelo e informe Ventas) al workspace "AIVD Ventas Demo", sustituyendo lo que ya hay.
```

Esperado: `upload_semantic_model` → `"operation": "updated"` y `upload_report` → `"updated"`.
Antes de refrescar el portal pregunta: «¿alguien cree que esto acaba de borrar los datos?». Refresca: aparece **Margen %** y las cifras siguen ahí.

3. Reenlace entre workspaces: un informe suelto, sin su modelo al lado.

```text
Con powerbi-mcp-deploy: sube el informe D:\Presentaciones\2026\11. AI VirtualDAys\demos\Powerbi\Sueltos\DashboardVentas.Report al workspace "AIVD Ventas Demo", dentro de la carpeta "Informes", y enlázalo al modelo semántico GreatAdventuresVentas del workspace "AIVD Ventas DEV".
```

Esperado: `upload_report(rebind_to_model="GreatAdventuresVentas", rebind_workspace_name="AIVD Ventas DEV", folder_path="Informes")`.
Di en voz alta: el MCP parchea `definition.pbir` de `byPath` a `byConnection` para que apunte al modelo correcto aunque viva en otro workspace.

---

## Demo 1 · El mismo encargo, con y sin MCP (≈8 min · diapos 13–15)

**Idea (honesta)**: los dos agentes publican. Cuando creé el MCP (junio de 2026) el agente sin MCP tardaba muchísimo más y fallaba
mucho más; hoy escribe su propio script de PowerShell, falla en una tontería, lo arregla y despliega. **Publicar ya no es la diferencia:
lo es todo lo demás** (historial, entornos, interfaz fija, el mismo CLI en CI), y buena parte de eso cabe en una skill (diapo 15).
Lanza primero el agente **sin** MCP (es el que tarda) y, mientras trabaja, el agente **con** MCP.

### 1A · Agente SIN MCP

Terminal 1 (Claude Code sin servidores MCP ni skills, solo terminal y `az`):

```powershell
cd "D:\Presentaciones\2026\11. AI VirtualDAys"
claude --strict-mcp-config --mcp-config demos/sin-mcp/no-mcp.json --disallowedTools Skill
```

> Sin el CLI `claude` en el PATH (`npm i -g @anthropic-ai/claude-code`): abre una sesión nueva de Claude Code en VS Code,
> `/mcp` → desactiva `powerbi-mcp-deploy` y `fabric`, y añade al prompt «no uses skills». Comprueba con `/mcp` que no queda ningún servidor de Power BI ni de Fabric.

```text
No tienes ningún servidor MCP de Power BI ni de Fabric, y no uses skills. Tienes una terminal con Azure CLI con sesión iniciada (az login) y permisos sobre Microsoft Fabric.

Publica el proyecto Power BI que está en D:\Presentaciones\2026\11. AI VirtualDAys\src\Powerbi (el modelo semántico y el informe GreatAdventuresVentas) en el workspace "AIVD Demo Agente sin MCP". El informe tiene que quedar enlazado al modelo de ese mismo workspace.

No modifiques los ficheros originales: si necesitas transformarlos, trabaja sobre una copia en .\build\.
Cuando termines, dime qué hay publicado en el workspace y enséñame el historial de despliegues de ese workspace.
```

Lo esperable hoy (ensayado): escribe un script de PowerShell, **falla por un detalle, lo corrige solo y publica**. No lo vendas como fracaso.
Mientras trabaja, señala lo que está **reinventando**: token de Fabric · cada fichero en base64 · excluir `.platform` y `.pbi/` ·
respuesta 202 y sondeo · `definition.pbir` de `byPath` a `byConnection`. Y al final pregúntale por el historial: **no existe**.

> **Plan B** si se atasca: `./demos/sin-mcp/deploy-rest.ps1 -Workspace "AIVD Demo Agente sin MCP" -PbipDir src/Powerbi -Name GreatAdventuresVentas`
> Enseña el fichero: ~100 líneas para lo que el MCP resuelve con una tool.

### 1B · Agente CON MCP

Claude Desktop con **mi** servidor `powerbi-mcp-deploy` (PowerBiDeploymentMCP, `uvx powerbi-mcp-deployment@0.2.3`).
En Claude Desktop también está `fabric` (el MCP de Fabric de Microsoft): **desactívalo durante la demo**
(*Configuración → Desarrollador*, o el interruptor de herramientas del chat) para que no haya dos caminos posibles.

```text
Usa únicamente el servidor MCP "powerbi-mcp-deploy" (PowerBiDeploymentMCP) y sus herramientas upload_semantic_model, upload_report, get_workspace_contents y query_deployments. No uses el servidor "fabric" ni otros MCP o skills de Microsoft.

Publica el proyecto Power BI que está en D:\Presentaciones\2026\11. AI VirtualDAys\src\Powerbi (el modelo semántico y el informe GreatAdventuresVentas) en el workspace "AIVD Demo Agente MCP". El informe tiene que quedar enlazado al modelo de ese mismo workspace.

Cuando termines, dime qué hay publicado en el workspace y enséñame el historial de despliegues de ese workspace.
```

Esperado: `upload_semantic_model` → `upload_report` (con `rebind_to_model`) → `get_workspace_contents` → `query_deployments`.

### 1C · Preguntas de seguimiento (a los dos agentes)

```text
¿Qué versión del modelo GreatAdventuresVentas hay publicada en ese workspace, quién la subió, cuándo y desde qué carpeta?
```

```text
Haz una copia de seguridad completa del workspace en D:\Backups\AIVD (modelos e informes en formato PBIP).
```

En el agente con MCP, empieza cada seguimiento con «Con powerbi-mcp-deploy: …».
Con MCP: `query_deployments` / `query_version_history` y `download_workspace`. Sin MCP: o no lo sabe, o improvisa otro script.

### 1D · Marcador (rellénalo en directo, diapo 14)

| | Sin MCP | Con MCP |
|---|---|---|
| Tiempo hasta publicado | | |
| Nº de llamadas / comandos | | |
| Errores y reintentos | | |
| ¿Queda historial? | | |
| ¿Lo repetiría igual mañana? | | |

**Cierre (diapo 15 · ¿sigue haciendo falta el MCP?)**: para publicar, cada vez menos. Agente solo = bueno para una vez.
Skill = conocimiento + script versionado, con Git y Releases como historial (justo lo que hace nuestro pipeline).
MCP + CLI = interfaz fija y estado compartido (entornos, drift, auditoría). «Lo que hoy es un MCP, mañana puede ser una skill».

**Puente a la Demo 2**: «Lo que el agente hace con el MCP es lo mismo que hace el CLI del MCP. Y el CLI se puede poner en una GitHub Action».

---

## Demo 2 · dev → DEV, PR → PROD con main sellada (≈5 min · diapos 29–30)

Enseña antes `.github/workflows/powerbi-cicd.yml` (30 segundos): `validate` → `deploy-dev` / `plan-prod` / `deploy-prod`, todo con `pbi_cli.py`.
Autenticación: OIDC del app registration **PyUploader** → `azure/login` → `pbi_cli.py auth --method az_cli`. Sin secretos.

### 2.1 · Cambio v2 en dev → despliegue automático en DEV

```powershell
git switch dev
./demos/cambios/v2-margen-neto.ps1          # añade la medida 'Margen neto'
git commit -am "v2: medida Margen neto"
git push
gh run watch                                 # validate → deploy-dev
```

En el portal: `AIVD Ventas DEV` → modelo → aparece **Margen neto** en *Rentabilidad*. Los datos siguen ahí.

### 2.2 · main está sellada

```powershell
git push origin dev:main
```

Esperado: `GH006: Protected branch update failed … Changes must be made through a pull request`.

### 2.3 · PR → plan → merge → PROD

```powershell
gh pr create --base main --head dev --title "v2: medida Margen neto" --body "Nueva medida en Rentabilidad"
gh pr checks --watch                         # validate + plan-prod
gh pr merge --merge
gh run watch                                 # validate → deploy-prod → Release
```

En el PR enseña el **summary de plan-prod**: qué hay ahora en PROD y qué ficheros cambian.

### Opcional · que lo pida el agente

```text
Abre un pull request de dev a main con los cambios del modelo GreatAdventuresVentas, espera a que pasen los checks y, si están en verde, haz el merge. Después dime qué versión ha quedado publicada en PROD.
```

---

## Demo 3 · Historial de versiones y vuelta atrás (≈5 min · diapo 30)

### 3.1 · Un cambio que sale mal (v3)

Lánzalo en directo o tenlo ya hecho antes de la charla:

```powershell
./demos/cambios/v3-error-ventas-netas.ps1    # 'Ventas netas' pasa a sumar el BRUTO
git commit -am "v3: ajuste de Ventas netas"
git push
gh pr create --base main --head dev --title "v3: ajuste Ventas netas" --body "Revisión de la medida"
gh pr checks --watch ; gh pr merge --merge ; gh run watch
```

En PROD las ventas salen **infladas** (el despliegue funciona; el error es de negocio).

### 3.2 · Todas las versiones subidas

```powershell
gh release list
gh release view <tag-v3>
```

O la pestaña **Releases**: cada despliegue a PROD es una versión con su tag `prod-AAAAMMDD-HHMMSS`, commit, autor, enlace a la ejecución y el **PBIP comprimido** descargable.

### 3.3 · Volver a una versión concreta

```powershell
gh workflow run rollback-prod -f version=<tag-v2> -f target=prod
gh run watch
gh release list                              # aparece «ROLLBACK a <tag-v2>» como versión nueva
```

En el portal: PROD vuelve a las cifras correctas y conserva *Margen neto*.

**Remate**: el rollback apaga el fuego; `git revert` arregla la fuente. Si no, el próximo merge vuelve a subir v3:

```powershell
git switch dev ; git pull
git revert --no-edit <sha-commit-v3>          # git log --oneline para verlo
git push                                     # y PR a main como siempre
```

### Opcional · que lo pida el agente

```text
Usa gh (GitHub CLI) sobre el repo megeagomez/ai-virtual-days-2026, no ningún MCP de Fabric.
Lista las versiones publicadas en PROD (releases prod-*), dime cuál fue la última sin el cambio de "Ventas netas" y restaura PROD a esa versión con el workflow rollback-prod. Avísame cuando termine.
```

---

## Volver al estado inicial tras un ensayo

```powershell
./demos/reset-demo.ps1 -Yes                                  # vacía los workspaces de la demo agéntica
./demos/Powerbi/margen-pct.ps1 -Deshacer                     # Demo 0: quita 'Margen %' (o descarta los cambios de Desktop con git)
#   y en el portal de AIVD Ventas Demo borra DashboardVentas; vuelve a subir Ventas (sin la medida) con el agente
gh workflow run rollback-prod -f version=<tag-v1> -f target=prod
gh workflow run rollback-prod -f version=<tag-v1> -f target=dev
# y en git, revierte v2/v3 en dev y haz PR a main (o restaura src/Powerbi desde el tag v1)
```
