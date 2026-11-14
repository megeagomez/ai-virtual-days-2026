<#  Cambio v4 (LENTO): reemplaza 'Margen bruto' por una versión
    equivalente pero lenta (SUMX fila a fila con transición de contexto).
    Los visuales de 'Resumen ejecutivo' y 'Producto y rentabilidad' que
    usan Margen bruto o % Margen bruto tardarán ≥ 2× al medirse con
    executeQueries, lo que dispara la puerta de rendimiento (perf-gate).

    Uso:  ./demos/cambios/v4-medida-lenta.ps1          (aplica cambio)
          ./demos/cambios/v4-medida-lenta.ps1 -Deshacer (revierte)     #>
param([switch]$Deshacer)
$ErrorActionPreference = "Stop"

$tmdl = Join-Path $PSScriptRoot "..\..\src\Powerbi\GreatAdventuresVentas.SemanticModel\definition\tables\Ventas.tmdl"
$text = [IO.File]::ReadAllText($tmdl, [Text.Encoding]::UTF8)
$nl   = if ($text -match "`r`n") { "`r`n" } else { "`n" }

# La definición original (una línea)
$fast = "`tmeasure 'Margen bruto' = [Ventas netas] - [Coste]"

# La versión lenta: SUMX fila a fila con transición de contexto (CALCULATE)
# Es matemáticamente equivalente pero itera cada fila de la tabla de hechos
$slow = (
    "`tmeasure 'Margen bruto' =" + $nl +
    "`t`t`tSUMX(" + $nl +
    "`t`t`t`t'Ventas'," + $nl +
    "`t`t`t`tCALCULATE(SUM('Ventas'[ImporteLinea])) - CALCULATE(SUM('Ventas'[Importe de coste]))" + $nl +
    "`t`t`t)"
)

if ($Deshacer) {
    if (-not $text.Contains($slow)) {
        if ($text.Contains($fast)) { Write-Host "v4 no estaba aplicado."; exit 0 }
        Write-Host "ADVERTENCIA: estado inconsistente. Revierte con: git checkout src/Powerbi"
        exit 1
    }
    $nuevo = $text.Replace($slow, $fast)
    [IO.File]::WriteAllText($tmdl, $nuevo, [Text.UTF8Encoding]::new($false))
    Write-Host "v4 deshecho: 'Margen bruto' restaurada a [Ventas netas] - [Coste]."
    exit 0
}

if (-not $text.Contains($fast)) {
    if ($text.Contains($slow)) { Write-Host "v4 ya aplicado."; exit 0 }
    throw "No encuentro el anchor 'measure ''Margen bruto'' = [Ventas netas] - [Coste]' en $tmdl"
}

$nuevo = $text.Replace($fast, $slow)
[IO.File]::WriteAllText($tmdl, $nuevo, [Text.UTF8Encoding]::new($false))
Write-Host "v4 aplicado: 'Margen bruto' reemplazada por versión SUMX lenta."
Write-Host "Despliega en DEV para medir: ./ci/deploy.ps1 -Workspace 'AIVD Ventas DEV' ..."
