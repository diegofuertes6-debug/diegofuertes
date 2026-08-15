# PowerShell wrapper para invocar el script de build en WSL
# Uso (desde la raíz del proyecto):
#   .\build_apk_wsl.ps1

$ErrorActionPreference = 'Stop'

$projectRoot = $PSScriptRoot
$drive = $projectRoot.Substring(0, 1).ToLower()
$rest = $projectRoot.Substring(2) -replace '\\', '/'
$wslPath = "/mnt/$drive$rest"

Write-Host "Invocando WSL en: $wslPath"

# Ejecutar script en WSL (requiere que WSL y la distro estén instaladas)
wsl.exe -d Ubuntu bash -lc "cd '$wslPath' && sed -i 's/\r$//' ./build_apk.sh && chmod +x ./build_apk.sh && ./build_apk.sh"
