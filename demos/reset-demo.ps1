<#  Vacía los workspaces de las demos (elementos y carpetas). Necesita `az login`.
      ./demos/reset-demo.ps1                 Demo 1: "AIVD Demo Agente MCP" y "AIVD Demo Agente sin MCP" (pide confirmación)
      ./demos/reset-demo.ps1 -Cadena         + Demo 2: los tres "AIVD Cadena …"
      ./demos/reset-demo.ps1 -Cadena -Yes    sin preguntar

    OJO con -Cadena: úsalo solo ANTES del primer ensayo de la Demo 2. Después, tu base de datos del MCP ya
    recuerda lo desplegado; si vacías los workspaces, el siguiente promote verá divergencia donde no la hay.
    Para repetir la Demo 2 no hace falta vaciar nada: vuelve a lanzar los prompts desde el paso 2.  #>
param([switch] $Cadena, [switch] $Yes)
$ErrorActionPreference = "Stop"
$api = "https://api.fabric.microsoft.com/v1"
$token = az account get-access-token --resource https://api.fabric.microsoft.com --query accessToken -o tsv 2>$null
if (-not $token) { throw "Sin sesión de az: ejecuta 'az login'" }
$h = @{ Authorization = "Bearer $token" }
$all = (Invoke-RestMethod "$api/workspaces" -Headers $h).value

$names = @("AIVD Demo Agente MCP", "AIVD Demo Agente sin MCP")
if ($Cadena) { $names += "AIVD Cadena Desarrollo", "AIVD Cadena Integracion", "AIVD Cadena Produccion" }

foreach ($name in $names) {
  $ws = $all | Where-Object displayName -eq $name
  if (-not $ws) { Write-Warning "No existe: $name"; continue }
  $items   = @((Invoke-RestMethod "$api/workspaces/$($ws.id)/items" -Headers $h).value)
  $folders = @((Invoke-RestMethod "$api/workspaces/$($ws.id)/folders" -Headers $h).value)
  if (-not $items -and -not $folders) { Write-Host "$name ya está vacío"; continue }
  $items | ForEach-Object { Write-Host "  $name → [$($_.type)] $($_.displayName)" }
  if ($folders) { Write-Host "  $name → $($folders.Count) carpeta(s)" }
  if (-not $Yes -and (Read-Host "¿Vaciar '$name'? (s/N)") -ne "s") { continue }

  # informes primero: un modelo con informes enlazados no se puede borrar
  $items | Sort-Object { $_.type -ne "Report" } | ForEach-Object {
    Invoke-RestMethod -Method Delete "$api/workspaces/$($ws.id)/items/$($_.id)" -Headers $h | Out-Null
    Write-Host "  ✓ borrado [$($_.type)] $($_.displayName)"
  }
  # carpetas de las hojas hacia la raíz
  while ($folders) {
    $parents = $folders.parentFolderId | Where-Object { $_ }
    $leaves  = $folders | Where-Object { $_.id -notin $parents }
    foreach ($f in $leaves) {
      Invoke-RestMethod -Method Delete "$api/workspaces/$($ws.id)/folders/$($f.id)" -Headers $h | Out-Null
      Write-Host "  ✓ borrada carpeta $($f.displayName)"
    }
    $folders = @($folders | Where-Object { $_.id -notin $leaves.id })
  }
}
