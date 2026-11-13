# Envuelve `pbi_cli.py promote` para CI.
# Motivo: ante drift y sin --yes, el CLI imprime "Promoción cancelada" pero termina con código 0,
# así que la pipeline quedaría en verde sin haber promocionado nada. Aquí lo convertimos en un fallo.
param(
  [Parameter(Mandatory)] [string] $Project,
  [Parameter(Mandatory)] [string] $Environment,
  [switch] $ConfirmDrift
)
[Console]::OutputEncoding = [Text.UTF8Encoding]::new()
$cliArgs = @('tools/pbimcp/pbi_cli.py', 'promote', $Project, $Environment)
if ($ConfirmDrift) { $cliArgs += '--yes' }
$lines = & python @cliArgs 2>&1 | Tee-Object -Variable captured
$code = $LASTEXITCODE
$text = ($captured | Out-String)
if ($text -match 'Promoci.n cancelada') {
  "### ⛔ Drift detectado en $Environment" >> $env:GITHUB_STEP_SUMMARY
  '```' >> $env:GITHUB_STEP_SUMMARY; $text >> $env:GITHUB_STEP_SUMMARY; '```' >> $env:GITHUB_STEP_SUMMARY
  'Revisa qué se cambió fuera de la cadena y relanza con `confirm_drift = true` si procede.' >> $env:GITHUB_STEP_SUMMARY
  exit 3
}
if ($code -ne 0) { exit $code }
"### ✅ $Project promocionado a $Environment" >> $env:GITHUB_STEP_SUMMARY
