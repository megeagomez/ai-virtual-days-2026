# Persiste la base de datos DuckDB del MCP (entornos, proyectos, hashes de lo promocionado)
# en la rama huérfana `pbi-state`. Sin esto, cada runner empieza sin memoria y no hay detección de drift.
param([Parameter(Mandatory)] [string] $Message)
Set-Location .pbi-state
git config user.name  "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add metadata.duckdb
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) { git commit -m "estado pbi: $Message"; git push origin HEAD:pbi-state }
