<#  Deja vacíos los dos workspaces de la demo agéntica (para ensayar las veces que haga falta).
    Solo toca "AIVD Demo Agente MCP" y "AIVD Demo Agente sin MCP". Necesita `az login`.
    ./demos/reset-demo.ps1        (pide confirmación)
    ./demos/reset-demo.ps1 -Yes   #>
param([switch] $Yes)
$ErrorActionPreference = "Stop"
$api = "https://api.fabric.microsoft.com/v1"
$token = az account get-access-token --resource https://api.fabric.microsoft.com --query accessToken -o tsv 2>$null
$h = @{ Authorization = "Bearer $token" }
$all = (Invoke-RestMethod "$api/workspaces" -Headers $h).value

foreach ($name in "AIVD Demo Agente MCP", "AIVD Demo Agente sin MCP") {
  $ws = $all | Where-Object displayName -eq $name
  if (-not $ws) { Write-Warning "No existe: $name"; continue }
  $items = (Invoke-RestMethod "$api/workspaces/$($ws.id)/items" -Headers $h).value
  if (-not $items) { Write-Host "$name ya está vacío"; continue }
  $items | ForEach-Object { Write-Host "  $name → [$($_.type)] $($_.displayName)" }
  if (-not $Yes -and (Read-Host "¿Borrar estos $($items.Count) elementos de '$name'? (s/N)") -ne "s") { continue }
  # informes primero: un modelo con informes enlazados no se puede borrar
  $items | Sort-Object { $_.type -ne "Report" } | ForEach-Object {
    Invoke-RestMethod -Method Delete "$api/workspaces/$($ws.id)/items/$($_.id)" -Headers $h | Out-Null
    Write-Host "  ✓ borrado [$($_.type)] $($_.displayName)"
  }
}
