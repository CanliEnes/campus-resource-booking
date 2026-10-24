#!/usr/bin/env sh
# Kullanım: ./calistir.sh baslangic.json komutlar.jsonl > sonuclar.jsonl
DIZIN="$(cd "$(dirname "$0")" && pwd)"
# Önce Python 3.11+ aranır; yoksa bulunan Python 3 kullanılır (modül 3.9+ ile de çalışır).
for SURUM in 11 9; do
    for PY in python3 python3.13 python3.12 python3.11 python; do
        if "$PY" -c "import sys; sys.exit(sys.version_info < (3, $SURUM))" >/dev/null 2>&1; then
            exec "$PY" "$DIZIN/calistir.py" "$@"
        fi
    done
done
if command -v py >/dev/null 2>&1; then
    exec py -3 "$DIZIN/calistir.py" "$@"
fi
echo "Python 3 bulunamadı." >&2
exit 1
