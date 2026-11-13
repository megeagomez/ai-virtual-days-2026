<#  Cambio v2 (BUENO): añade la medida 'Margen neto' = Margen bruto - Portes.
    Uso:  ./demos/cambios/v2-margen-neto.ps1     (idempotente)  #>
$ErrorActionPreference = "Stop"
$tmdl = Join-Path $PSScriptRoot "..\..\src\Powerbi\GreatAdventuresVentas.SemanticModel\definition\tables\Ventas.tmdl"
$text = [IO.File]::ReadAllText($tmdl)
if ($text -match "measure 'Margen neto'") { Write-Host "v2 ya aplicado: 'Margen neto' existe."; exit 0 }

$anchor = "`tmeasure 'Margen por pedido'"
$nl = if ($text -match "`r`n") { "`r`n" } else { "`n" }
$measure = @(
  "`t/// Margen bruto menos portes: lo que queda de cada venta tras la logística.",
  "`tmeasure 'Margen neto' = [Margen bruto] - [Portes]",
  "`t`tformatString: \`$#,##0",
  "`t`tdisplayFolder: Rentabilidad",
  "`t`tlineageTag: 3b7c2d9e-6a41-4f0b-9e2d-a1f5c7d84e10",
  "", "") -join $nl
$i = $text.IndexOf("`t/// Margen bruto medio que deja cada pedido.")
if ($i -lt 0) { $i = $text.IndexOf($anchor) }
if ($i -lt 0) { throw "No encuentro dónde insertar la medida en $tmdl" }
[IO.File]::WriteAllText($tmdl, $text.Insert($i, $measure), [Text.UTF8Encoding]::new($false))
Write-Host "v2 aplicado: medida 'Margen neto' añadida a Ventas.tmdl"
