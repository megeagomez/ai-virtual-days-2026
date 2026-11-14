<#  Demo «publicar hablando» (diapo 10): la copia «después» sin abrir Desktop.
    Añade la medida 'Margen %' al PBIP de demos/Powerbi/Ventas.
      ./demos/Powerbi/margen-pct.ps1             añade la medida (idempotente)
      ./demos/Powerbi/margen-pct.ps1 -Deshacer   la quita (para volver a ensayar)
    Si Desktop tiene abierto Ventas.pbip, ciérralo antes: Desktop sobrescribe el TMDL al guardar.  #>
param([switch] $Deshacer)
$ErrorActionPreference = "Stop"
$tmdl = Join-Path $PSScriptRoot "Ventas\Ventas.SemanticModel\definition\tables\Ventas.tmdl"
$text = [IO.File]::ReadAllText($tmdl)
$nl = if ($text -match "`r`n") { "`r`n" } else { "`n" }
$block = @(
  "`t/// Margen sobre ventas netas, añadido en directo en la demo.",
  "`tmeasure 'Margen %' = DIVIDE([Ventas netas] - [Coste], [Ventas netas])",
  "`t`tformatString: 0.0%",
  "`t`tdisplayFolder: Rentabilidad",
  "`t`tlineageTag: 9d2e4f61-7c3a-4b8e-a5d1-2f6c8e0b7a93",
  "", "") -join $nl

if ($Deshacer) {
  if (-not $text.Contains($block)) { Write-Host "No estaba aplicada: nada que deshacer."; exit 0 }
  [IO.File]::WriteAllText($tmdl, $text.Replace($block, ""), [Text.UTF8Encoding]::new($false))
  Write-Host "Medida 'Margen %' eliminada."; exit 0
}
if ($text -match "measure 'Margen %'") { Write-Host "Ya existe 'Margen %'."; exit 0 }
$i = $text.IndexOf("`t/// Margen bruto medio que deja cada pedido.")
if ($i -lt 0) { throw "No encuentro dónde insertar la medida en $tmdl" }
[IO.File]::WriteAllText($tmdl, $text.Insert($i, $block), [Text.UTF8Encoding]::new($false))
Write-Host "Medida 'Margen %' añadida a Ventas.tmdl (carpeta Rentabilidad)."
