<#  Cambio v3 (MALO, a propósito): 'Ventas netas' pasa a sumar el importe BRUTO.
    El despliegue funciona (el TMDL es válido) pero las cifras de PROD salen infladas
    → excusa perfecta para enseñar el rollback a la versión anterior.
    Uso:  ./demos/cambios/v3-error-ventas-netas.ps1  #>
$ErrorActionPreference = "Stop"
$tmdl = Join-Path $PSScriptRoot "..\..\src\Powerbi\GreatAdventuresVentas.SemanticModel\definition\tables\Ventas.tmdl"
$text = [IO.File]::ReadAllText($tmdl)
$good = "measure 'Ventas netas' = SUM('Ventas'[ImporteLinea])"
$bad  = "measure 'Ventas netas' = SUM('Ventas'[ImporteBruto])"
if ($text.Contains($bad)) { Write-Host "v3 ya aplicado."; exit 0 }
if (-not $text.Contains($good)) { throw "No encuentro la definición original de 'Ventas netas'" }
[IO.File]::WriteAllText($tmdl, $text.Replace($good, $bad), [Text.UTF8Encoding]::new($false))
Write-Host "v3 aplicado: 'Ventas netas' ahora suma ImporteBruto (error intencionado)"
