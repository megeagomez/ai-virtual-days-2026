# Prompt para GitHub Copilot (Sonnet 5.5, modo agente) · puerta de rendimiento en la GitHub Action

Copia desde la línea siguiente hasta el final en el chat de Copilot en VS Code, en modo **Agent** y con la carpeta
`D:\Presentaciones\2026\11. AI VirtualDAys` abierta. Antes, deja el JSON del Performance Analyzer en
`tests/perf/baseline-performance-analyzer.json`, o dile al agente dónde está.

---

Trabaja en el repo abierto (`megeagomez/ai-virtual-days-2026`, rama `dev`). Ejecuta tú todos los comandos necesarios en la terminal (PowerShell, Windows) y verifica cada paso. No me pidas que los lance yo, salvo que un paso necesite login interactivo.

## Contexto

- El pipeline está en `.github/workflows/powerbi-cicd.yml`:
  - `validate`.
  - `deploy-dev` (push a `dev` → workspace "AIVD Ventas DEV").
  - `plan-prod` (PR a `main`).
  - `deploy-prod` (push a `main` → "AIVD Ventas PROD" + Release `prod-*`).
  - Rollback en `.github/workflows/rollback-prod.yml`.
- La autenticación está en `.github/actions/pbi-cli/action.yml`: service principal con el secreto `AZURE_CLIENT_SECRET` (o OIDC) → `az login` → CLI de PowerBiDeploymentMCP con `auth --method az_cli`. Variables del repo: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `PBI_WS_DEV`, `PBI_WS_PROD`.
- El modelo y el informe son `GreatAdventuresVentas` (PBIP en `src/Powerbi`, informe en formato PBIR).
- `main` está protegida: solo entra por PR con el check `validate` en verde. **Nunca hagas push a `main`.**
- `demo-pipeline/ci/pbi_rest.py` ya tiene código para `executeQueries` y refresh contra la API de Power BI. Reutilízalo o adáptalo.
- El tenant tiene activado *Dataset Execute Queries REST API*, y el service principal es Contributor en DEV y PROD.

## Objetivo

Añadir una **puerta de rendimiento**: si alguna página del informe tarda **el doble o más** que la línea base, se rechaza la puesta en producción por degradación.

La línea base parte de una exportación del Performance Analyzer de Power BI Desktop: `tests/perf/baseline-performance-analyzer.json`.

## Antes de escribir código

1. Abre el JSON y **describe su estructura real**: eventos, cómo se relacionan (`id`/`parentId`), dónde está el texto DAX (p. ej. `metrics.QueryText`), duraciones y qué identifica a cada visual.
2. No supongas que trae el nombre de la página. En PBIR, cada visual vive en `src/Powerbi/GreatAdventuresVentas.Report/definition/pages/<pageId>/visuals/<visualId>/`, y el nombre de la página está en el `page.json` de esa carpeta. Usa eso para mapear visual → página.
3. Dime qué páginas, visuales y consultas DAX has encontrado antes de seguir.

## Diseño (respétalo salvo que encuentres un motivo técnico; si es así, explícamelo)

- En GitHub Actions no hay Power BI Desktop. **Mide el tiempo de las consultas DAX** relanzando cada consulta del JSON con `executeQueries`. El tiempo de render de los visuales no se puede medir; dilo en el informe.
- **Línea base medida en el servicio.** Ejecuta las mismas consultas contra el modelo de PROD (versión actual) y contra el candidato, en el mismo job. Los tiempos de Desktop del JSON van solo como referencia informativa, porque Desktop y el servicio no son comparables.
  - Añade el modo `--baseline json` para comparar contra los tiempos del JSON, desactivado por defecto.
- **Candidato**: el modelo de "AIVD Ventas DEV", que tiene desplegado el contenido de `dev`, es decir, lo que se va a fusionar.
- **Métrica por página**: suma de las medianas de sus consultas.
  - Por consulta: 1 ejecución de calentamiento descartada y 3 ejecuciones medidas (configurable).
- **Regla**: falla si `tiempo_candidato / tiempo_baseline >= PERF_MAX_RATIO` (por defecto 2.0) **y** el candidato supera `PERF_MIN_MS` (por defecto 500 ms). Así se evita el ruido en páginas muy rápidas.
  - Ambos valores son configurables como variables del repo, con estos valores por defecto.
- Si una consulta falla en el candidato pero no en la base, también es fallo.
  - Recuerda que `executeQueries` tiene límites de filas y valores, y no admite DMV.
- Script nuevo: `ci/perf_gate.py`. Debe:
  - salir con código ≠ 0 si hay degradación;
  - escribir en `$GITHUB_STEP_SUMMARY` una tabla por página: baseline ms · candidato ms · ratio · ✅/❌, con la página culpable destacada;
  - escribir la consulta más lenta de cada página;
  - generar un JSON de evidencias que se publique como artifact.

## Cambios en el workflow

- Job nuevo **`perf-gate`**, con un nombre visible claro, p. ej. `perf-gate · degradación ×2`, para que se vea al enseñar la Action:
  - se ejecuta en los **PR a `main`** (después de `validate`, como informativo y para enseñarlo);
  - se ejecuta en el **push a `main`**, donde `deploy-prod` debe depender de él (`needs: [validate, perf-gate]`). Si falla, no hay despliegue a PROD ni Release.
- Usa la action `./.github/actions/pbi-cli` para autenticarte. El token de Power BI sale de `az account get-access-token --resource https://analysis.windows.net/powerbi/api`.
- No toques la lógica existente de `deploy-dev`, `plan-prod`, `deploy-prod` ni del rollback, salvo para añadir la dependencia.
- Si es posible, añade `perf-gate` como check requerido en la protección de `main`. Primero enséñame el comando `gh api` y espera mi confirmación.

## Demo de la degradación

- Crea `demos/cambios/v4-medida-lenta.ps1` (idempotente, con `-Deshacer`, en el mismo estilo que `demos/cambios/v2-margen-neto.ps1`). Debe cambiar una medida que usen los visuales de una página concreta por una versión equivalente pero **lenta**, para que esa página tarde ≥ 2×. Por ejemplo, iteración fila a fila con transición de contexto (`SUMX` sobre la tabla de hechos con `CALCULATE`).
- **Verifícalo de verdad, no lo supongas.**
  1. Ejecuta `ci/perf_gate.py` en local con mi sesión `az` (cuenta de Fabric) comparando PROD contra DEV con el cambio aplicado.
     - Para aplicarlo en DEV sin pasar por git, despliega con `./ci/deploy.ps1`. El CLI está en `D:\Presentaciones\2026\10. Datasaturday\PowerBiDeploymentMCP\pbi_cli.py`.
  2. Si no llega a 2×, haz la medida más lenta hasta que llegue.
  3. Al terminar, deshaz el cambio y vuelve a desplegar DEV para que quede como estaba.
- Comprueba que DEV y PROD tienen datos cargados. Si el modelo está vacío, la medición no sirve: avísame.

## Documentación y presentación

- `demos/GUION-DEMOS.md`: añade una sección **«Demo 3b · Puerta de rendimiento»** (opcional en la charla) con:
  - los comandos: aplicar v4 → push a `dev` → PR → ver `perf-gate` en rojo → `-Deshacer`;
  - qué enseñar en el resumen del job.
- `src/index.html`: en la diapo «dev → DEV · PR → PROD», añade el paso de rendimiento en la cadena sin romper el diseño. Regenera la presentación con `python src/build.py` y comprueba que no se descuadra.
- `README.md`: añade una línea con la nueva puerta en la tabla del pipeline.

## Cómo subirlo

- Haz commit en `dev`. Los mensajes de commit van en español.
- Push con:
  `git -c credential.helper= -c "credential.helper=!C:/Users/miguel.egea/tools/gh/bin/gh.exe auth git-credential" push origin dev`
  (o `git push` a secas si ya está configurado `gh auth setup-git`).
- `gh` está en `$env:USERPROFILE\tools\gh\bin\gh.exe`.
- Abre un PR de `dev` a `main` y vigila los checks con `gh pr checks --watch`. Comprueba que `perf-gate` pasa en verde **sin** el cambio v4.
- **No hagas merge sin preguntarme.**

## Al terminar, dame

- La estructura del JSON y cómo has mapeado visuales a páginas.
- La tabla de tiempos real (PROD contra DEV) con y sin v4.
- Qué ficheros has cambiado.
- Cualquier limitación (render no medido, ruido de la capacidad Trial, límites de `executeQueries`).
