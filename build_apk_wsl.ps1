# PowerShell wrapper para invocar el script de build en WSL
# Uso (desde la raíz del proyecto):
#   .\build_apk_wsl.ps1

$winPath = (Get-Location).Path
$drive = $winPath.Substring(0, 1).ToLower()
$rest = $winPath.Substring(2) -replace '\\', '/'
$wslPath = "/mnt/$drive$rest"

Write-Host "Invocando WSL en: $wslPath"

# Ejecutar script en WSL (requiere que WSL y la distro estén instaladas)
wsl bash -lc "chmod +x '$wslPath/build_apk.sh' && '$wslPath/build_apk.sh'"
exit $LASTEXITCODE
