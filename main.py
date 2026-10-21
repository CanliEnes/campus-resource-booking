"""Komut satırı: python main.py baslangic.json komutlar.jsonl > sonuclar.jsonl"""
import json
import sys

from rezervasyon import RezervasyonSistemi


def calistir(baslangic_yolu: str, komut_yolu: str, cikti=sys.stdout) -> None:
    sistem = RezervasyonSistemi.dosyadan(baslangic_yolu)
    no = 0
    with open(komut_yolu, encoding="utf-8-sig") as f:
        for satir in f:
            satir = satir.strip()
            if not satir:
                continue
            no += 1
            try:
                komut = json.loads(satir)
            except json.JSONDecodeError:
                sonuc = {"komut": None, "durum": "RED", "kod": "GECERSIZ_KOMUT"}
            else:
                sonuc = sistem.komut_isle(komut)
            cikti.write(json.dumps({"no": no, **sonuc}, ensure_ascii=False,
                                   separators=(",", ":")) + "\n")


def main() -> int:
    if len(sys.argv) != 3:
        print("Kullanım: calistir baslangic.json komutlar.jsonl > sonuclar.jsonl", file=sys.stderr)
        return 2
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    calistir(sys.argv[1], sys.argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main())
