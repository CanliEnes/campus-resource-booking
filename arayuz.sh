#!/usr/bin/env sh
# Masaüstü uygulamasını başlatır. İsteğe bağlı: ./arayuz.sh baslangic.json
DIZIN="$(cd "$(dirname "$0")" && pwd)"
# Önce Python 3.11+ aranır; yoksa tkinter'lı bulunan Python 3 kullanılır.
for SURUM in 11 9; do
    for PY in python3 python3.13 python3.12 python3.11 python; do
        if "$PY" -c "import sys, tkinter; sys.exit(sys.version_info < (3, $SURUM))" >/dev/null 2>&1; then
            exec "$PY" "$DIZIN/masaustu.py" "$@"
        fi
    done
done
exec py -3 "$DIZIN/masaustu.py" "$@"
