#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/mnt/d/Repartidor"
WSL_WORKDIR="/home/$(whoami)/repartidor"

export PATH="$HOME/.local/bin:$PATH"
export PIP_BREAK_SYSTEM_PACKAGES=1
export PIP_DISABLE_PIP_VERSION_CHECK=1

if ! command -v cmake >/dev/null 2>&1; then
  python3 -m pip install --user --break-system-packages --upgrade cmake
fi

if ! command -v ninja >/dev/null 2>&1; then
  python3 -m pip install --user --break-system-packages --upgrade ninja
fi

if ! python3 - <<'PY' >/dev/null 2>&1
import importlib.util
raise SystemExit(0 if importlib.util.find_spec("buildozer") else 1)
PY
then
  python3 -m pip install --user --break-system-packages --upgrade git+https://github.com/kivy/buildozer.git
fi

mkdir -p "$WSL_WORKDIR"
rsync -a --delete "$PROJECT_ROOT"/ "$WSL_WORKDIR"/

cd "$WSL_WORKDIR"

attempt=1
max_attempts=3
while true; do
  echo "Iniciando buildozer (intento ${attempt}/${max_attempts})..."
  if python3 -m buildozer -v android debug; then
    break
  fi

  if [ "$attempt" -ge "$max_attempts" ]; then
    echo "Build fallido tras ${max_attempts} intentos."
    exit 1
  fi

  attempt=$((attempt + 1))
  echo "Reintentando buildozer por posible fallo transitorio de red..."
done

mkdir -p "$PROJECT_ROOT/bin" "$PROJECT_ROOT/din"
cp -f "$WSL_WORKDIR"/bin/*.apk "$PROJECT_ROOT/bin"/
cp -f "$WSL_WORKDIR"/bin/*.apk "$PROJECT_ROOT/din"/

echo "APK generado en $PROJECT_ROOT/bin y $PROJECT_ROOT/din"
ls -1 "$PROJECT_ROOT/din"/*.apk