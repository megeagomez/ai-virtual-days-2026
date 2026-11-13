<#
  PLAN B de la demo "sin MCP": lo que un agente tiene que descubrir y escribir él solo
  para publicar un PBIP con la API REST de Fabric (sin PowerBiDeploymentMCP).

  Úsalo solo si el agente en directo se atasca, o para enseñar en pantalla todo lo que
  el MCP te ahorra. Necesita `az login` con una cuenta con acceso al workspace.

  ./demos/sin-mcp/deploy-rest.ps1 -Workspace "AIVD Demo Agente sin MCP" -PbipDir src/Powerbi -Name GreatAdventuresVentas
#>
param(
  [Parameter(Mandatory)] [string] $Workspace,
  [Parameter(Mandatory)] [string] $PbipDir,
  [Parameter(Mandatory)] [string] $Name
)
$ErrorActionPreference = "Stop"
$api = "https://api.fabric.microsoft.com/v1"

# 1. Token de Fabric a partir de la sesión de az
$token = az account get-access-token --resource https://api.fabric.microsoft.com --query accessToken -o tsv 2>$null
if (-not $token) { throw "Sin sesión de az: ejecuta 'az login'" }
$h = @{ Authorization = "Bearer $token" }

function Invoke-Fabric([string]$Method, [string]$Url, $Body) {
  $p = @{ Method = $Method; Uri = $Url; Headers = $h; ContentType = "application/json"; SkipHttpErrorCheck = $true; ResponseHeadersVariable = "rh"; StatusCodeVariable = "sc" }
  if ($Body) { $p.Body = ($Body | ConvertTo-Json -Depth 10 -Compress) }
  $r = Invoke-RestMethod @p
  if ($sc -eq 202) {                                   # 2. Operación larga (LRO): hay que sondear
    $op = $rh.Location[0]
    do {
      $wait = [int](@($rh.'Retry-After')[0]); if ($wait -lt 1) { $wait = 2 }
      Start-Sleep -Seconds $wait
      $st = Invoke-RestMethod -Uri $op -Headers $h -ResponseHeadersVariable rh
      Write-Host "    LRO: $($st.status)"
    } while ($st.status -in "NotStarted", "Running")
    if ($st.status -ne "Succeeded") { throw "LRO falló: $($st | ConvertTo-Json -Depth 5)" }
    try { return Invoke-RestMethod -Uri "$op/result" -Headers $h } catch { return $null }
  }
  if ($sc -ge 400) { throw "$Method $Url → HTTP $sc`n$($r | ConvertTo-Json -Depth 6)" }
  return $r
}

# 3. Empaquetar una carpeta PBIP como "parts" en base64 (sin .platform ni .pbi/)
function Get-Parts([string]$Folder, [scriptblock]$Patch) {
  $root = (Get-Item -LiteralPath $Folder).FullName.TrimEnd("\")   # FullName, no Resolve-Path: rutas 8.3
  Get-ChildItem $root -Recurse -File | Where-Object {
    $rel = $_.FullName.Substring($root.Length + 1).Replace("\", "/")
    $rel -ne ".platform" -and -not $rel.StartsWith(".pbi/")
  } | ForEach-Object {
    $rel = $_.FullName.Substring($root.Length + 1).Replace("\", "/")
    $bytes = [IO.File]::ReadAllBytes($_.FullName)
    if ($Patch) { $bytes = & $Patch $rel $bytes }
    @{ path = $rel; payload = [Convert]::ToBase64String($bytes); payloadType = "InlineBase64" }
  }
}

function Publish-Item([string]$WsId, [string]$Type, [string]$DisplayName, $Parts) {
  $existing = (Invoke-Fabric GET "$api/workspaces/$WsId/items?type=$Type").value | Where-Object displayName -eq $DisplayName
  if ($existing) {
    Write-Host "  → $Type '$DisplayName' existe: updateDefinition"
    Invoke-Fabric POST "$api/workspaces/$WsId/items/$($existing.id)/updateDefinition" @{ definition = @{ parts = @($Parts) } } | Out-Null
    return $existing.id
  }
  Write-Host "  → $Type '$DisplayName' no existe: create"
  $null = Invoke-Fabric POST "$api/workspaces/$WsId/items" @{ displayName = $DisplayName; type = $Type; definition = @{ parts = @($Parts) } }
  return ((Invoke-Fabric GET "$api/workspaces/$WsId/items?type=$Type").value | Where-Object displayName -eq $DisplayName).id
}

$ws = (Invoke-Fabric GET "$api/workspaces").value | Where-Object displayName -eq $Workspace
if (-not $ws) { throw "Workspace no encontrado: $Workspace" }
Write-Host "Workspace: $Workspace ($($ws.id))"

# 4. Modelo
$modelId = Publish-Item $ws.id "SemanticModel" $Name (Get-Parts "$PbipDir/$Name.SemanticModel")
Write-Host "  ✓ Modelo: $modelId"

# 5. Informe: reescribir definition.pbir de byPath → byConnection (si no, el servicio lo rechaza)
$rebind = {
  param($rel, $bytes)
  if ($rel -ne "definition.pbir") { return $bytes }
  $pbir = [Text.Encoding]::UTF8.GetString($bytes) | ConvertFrom-Json -AsHashtable
  $pbir.datasetReference = @{ byConnection = @{ connectionString = "semanticmodelid=$modelId" } }
  return [Text.Encoding]::UTF8.GetBytes(($pbir | ConvertTo-Json -Depth 10))
}.GetNewClosure()
$reportId = Publish-Item $ws.id "Report" $Name (Get-Parts "$PbipDir/$Name.Report" $rebind)
Write-Host "  ✓ Informe: $reportId (enlazado a $modelId)"
Write-Host "Ojo: sin MCP no queda NINGÚN registro de qué se desplegó, cuándo ni desde dónde."
