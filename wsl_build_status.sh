#!/usr/bin/env bash
set -eu

echo "== BUILD PROCESSES =="
ps -ef | grep buildozer | grep -v grep || true

echo "== TOOLS =="
echo "$PATH"
command -v cmake || true
command -v ninja || true
ls -lah /home/$(whoami)/.local/bin/cmake 2>/dev/null || true
ls -lah /home/$(whoami)/.local/lib/python3.14/site-packages/cmake/data/bin/cmake 2>/dev/null || true

echo "== WSL APK DIR =="
ls -lah /home/$(whoami)/repartidor/bin 2>/dev/null || true
ls -1 /home/$(whoami)/repartidor/bin/*.apk 2>/dev/null || true

echo "== WIN APK DIR =="
ls -lah /mnt/d/Repartidor/bin 2>/dev/null || true
ls -1 /mnt/d/Repartidor/bin/*.apk 2>/dev/null || true