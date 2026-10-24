"""Komut satırı girişi.

Kullanım: python calistir.py baslangic.json komutlar.jsonl > sonuclar.jsonl
"""

import json
import sys

from rezervasyon import RezervasyonSistemi


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("Kullanım: calistir baslangic.json komutlar.jsonl > sonuclar.jsonl", file=sys.stderr)
        return 2
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    sistem = RezervasyonSistemi.dosyadan(argv[1])
    no = 0
    with open(argv[2], encoding="utf-8-sig") as komutlar:
        for satir in komutlar:
            if not satir.strip():
                continue
            no += 1
            try:
                komut = json.loads(satir)
            except json.JSONDecodeError:
                komut = {}
            sonuc = sistem.komut_isle(komut)
            print(json.dumps({"no": no, **sonuc}, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
