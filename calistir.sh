#!/bin/sh
# Kullanim: ./calistir.sh baslangic.json komutlar.jsonl > sonuclar.jsonl
DIZIN="$(cd "$(dirname "$0")" && pwd)"
if command -v python3 >/dev/null 2>&1; then PY=python3; else PY=python; fi
exec "$PY" "$DIZIN/main.py" "$@"
