#!/usr/bin/env bash
set -Eeuo pipefail

# Script para construir la APK con buildozer desde un directorio Linux nativo
# para evitar problemas de permisos con WSL + filesystem montado de Windows.
# Uso: ./build_apk.sh

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LINUX_WORKDIR="/home/$(whoami)/repartidor"
STAGING_DIR="/tmp/repartidor-build-src"
VENV_DIR="$LINUX_WORKDIR/.venv"

mkdir -p "$PROJECT_ROOT/bin"

rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR"
cp -a "$PROJECT_ROOT"/. "$STAGING_DIR"/

rm -rf "$LINUX_WORKDIR"
mkdir -p "$LINUX_WORKDIR"
rsync -a --ignore-existing "$STAGING_DIR"/ "$LINUX_WORKDIR"/

cd "$LINUX_WORKDIR"

export PATH="$HOME/.local/bin:$PATH"
export PIP_BREAK_SYSTEM_PACKAGES=1
export PIP_DISABLE_PIP_VERSION_CHECK=1

if [ ! -x "$VENV_DIR/bin/python" ]; then
  python3 -m venv "$VENV_DIR"
fi

VENV_PYTHON="$VENV_DIR/bin/python"

# Instalar Buildozer en el entorno virtual local de Ubuntu
"$VENV_PYTHON" -m pip install --upgrade pip setuptools wheel
"$VENV_PYTHON" -m pip install --upgrade cython buildozer

echo "Iniciando buildozer (android debug) en $LINUX_WORKDIR usando entorno virtual..."
"$VENV_PYTHON" -m buildozer -v android debug

mkdir -p "$PROJECT_ROOT/bin" "$PROJECT_ROOT/din"
find "$LINUX_WORKDIR/bin" -maxdepth 1 -type f \( -name '*.apk' -o -name '*.aab' \) -exec cp -f {} "$PROJECT_ROOT/bin"/ \;
find "$LINUX_WORKDIR/bin" -maxdepth 1 -type f \( -name '*.apk' -o -name '*.aab' \) -exec cp -f {} "$PROJECT_ROOT/din"/ \;

apk_path=""
for f in "$PROJECT_ROOT"/bin/*.apk "$PROJECT_ROOT"/din/*.apk; do
  if [ -f "$f" ]; then
    apk_path="$f"
    break
  fi
done

if [ -n "$apk_path" ]; then
  echo "APK generado: $apk_path"
else
  echo "No se encontró APK en din/ ni en bin/. Revisa la salida de buildozer para errores."
  exit 3
fi
