#!/usr/bin/env bash
set -euo pipefail

# Script para construir la APK con buildozer desde un directorio Linux nativo
# para evitar problemas de permisos con WSL + filesystem montado de Windows.
# Uso: ./build_apk.sh

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LINUX_WORKDIR="/home/$(whoami)/repartidor"
STAGING_DIR="/tmp/repartidor-build-src"

rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR"
cp -a "$PROJECT_ROOT"/. "$STAGING_DIR"/

rm -rf "$LINUX_WORKDIR"
mkdir -p "$LINUX_WORKDIR"
rsync -a --ignore-existing "$STAGING_DIR"/ "$LINUX_WORKDIR"/

cd "$LINUX_WORKDIR"

export PATH="$HOME/.local/bin:$PATH"

echo "Iniciando buildozer (android debug) en $LINUX_WORKDIR..."
if ! python3 - <<'PY' >/dev/null 2>&1
import importlib.util
raise SystemExit(0 if importlib.util.find_spec('buildozer') else 1)
PY
then
  echo "Buildozer no está instalado; lo instalamos automáticamente..."
  python3 -m pip install --user --upgrade pip setuptools wheel Cython==0.29.33
  python3 -m pip install --user buildozer==1.5.0
fi

python3 -m buildozer -v android debug

mkdir -p "$PROJECT_ROOT/bin"
cp -f "$LINUX_WORKDIR/bin"/*.apk "$PROJECT_ROOT/bin"/ 2>/dev/null || true

apk_path=""
for f in "$PROJECT_ROOT"/bin/*.apk; do
  if [ -f "$f" ]; then
    apk_path="$f"
    break
  fi
done

if [ -n "$apk_path" ]; then
  echo "APK generado: $apk_path"
else
  echo "No se encontró APK en bin/. Revisa la salida de buildozer para errores."
  exit 3
fi
