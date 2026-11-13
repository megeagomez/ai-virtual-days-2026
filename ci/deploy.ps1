<#
  Despliega el PBIP (modelo + informe) en un workspace con el CLI de PowerBiDeploymentMCP.
  Lo usan los workflows de despliegue y de rollback; también sirve en local.

  ./ci/deploy.ps1 -Workspace "AIVD Ventas DEV" -PbipDir src/Powerbi -Name GreatAdventuresVentas
#>
param(
  [Parameter(Mandatory)] [string] $Workspace,
  [Parameter(Mandatory)] [string] $PbipDir,
  [Parameter(Mandatory)] [string] $Name,
  [string] $Cli = "tools/pbimcp/pbi_cli.py"
)
$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"

function Invoke-Cli {
  python $Cli @args
  if ($LASTEXITCODE -ne 0) { throw "pbi_cli.py $($args[0]) falló (exit $LASTEXITCODE)" }
}

# 1. Modelo: si existe → updateDefinition (no borra los datos ya cargados); si no → create
Invoke-Cli upload-model  $Workspace "$PbipDir/$Name.SemanticModel" --name $Name
# 2. Informe: se reenlaza al modelo del MISMO workspace (byPath → byConnection)
Invoke-Cli upload-report $Workspace "$PbipDir/$Name.Report" --name $Name --rebind $Name
# 3. Evidencia: qué quedó publicado
Invoke-Cli contents $Workspace
