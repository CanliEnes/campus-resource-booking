"""Test senaryolarını çalıştırır ve beklenen sonuçlarla alan alan karşılaştırır.

Her alt klasörde baslangic.json, komutlar.jsonl ve beklenen.jsonl bulunur.
Karşılaştırma alan alan yapılır: fazladan alan hata sayılmaz; eksik veya farklı alan hata sayılır.

Kullanım: python testler/testleri_calistir.py [klasör ...]
"""

import json
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from rezervasyon import RezervasyonSistemi  # noqa: E402


def farklar(beklenen, gercek, yol="") -> list[str]:
    if isinstance(beklenen, dict):
        if not isinstance(gercek, dict):
            return [f"{yol}: sözlük bekleniyordu, {gercek!r} geldi"]
        sonuc = []
        for anahtar, deger in beklenen.items():
            if anahtar not in gercek:
                sonuc.append(f"{yol}.{anahtar}: eksik")
            else:
                sonuc.extend(farklar(deger, gercek[anahtar], f"{yol}.{anahtar}"))
        return sonuc
    if isinstance(beklenen, list):
        if not isinstance(gercek, list) or len(beklenen) != len(gercek):
            return [f"{yol}: {beklenen!r} bekleniyordu, {gercek!r} geldi"]
        sonuc = []
        for i, (b, g) in enumerate(zip(beklenen, gercek)):
            sonuc.extend(farklar(b, g, f"{yol}[{i}]"))
        return sonuc
    if beklenen != gercek or type(beklenen) is not type(gercek):
        return [f"{yol}: {beklenen!r} bekleniyordu, {gercek!r} geldi"]
    return []


def senaryo_calistir(klasor: Path) -> list[dict]:
    sistem = RezervasyonSistemi.dosyadan(str(klasor / "baslangic.json"))
    sonuclar = []
    satirlar = (klasor / "komutlar.jsonl").read_text(encoding="utf-8-sig").splitlines()
    for satir in filter(str.strip, satirlar):
        sonuclar.append({"no": len(sonuclar) + 1, **sistem.komut_isle(json.loads(satir))})
    return sonuclar


def main(argv: list[str]) -> int:
    klasorler = [Path(a) for a in argv[1:]] or sorted(
        p for p in Path(__file__).resolve().parent.iterdir() if (p / "beklenen.jsonl").exists())
    toplam_hata = 0
    for klasor in klasorler:
        gercekler = senaryo_calistir(klasor)
        beklenenler = [json.loads(s) for s in
                       (klasor / "beklenen.jsonl").read_text(encoding="utf-8-sig").splitlines()
                       if s.strip()]
        hatalar = []
        if len(gercekler) != len(beklenenler):
            hatalar.append(f"satır sayısı: {len(beklenenler)} bekleniyordu, {len(gercekler)} geldi")
        for beklenen, gercek in zip(beklenenler, gercekler):
            for fark in farklar(beklenen, gercek):
                hatalar.append(f"no {beklenen.get('no')}{fark}")
        durum = "GEÇTİ" if not hatalar else f"KALDI ({len(hatalar)} fark)"
        print(f"[{durum}] {klasor.name}: {len(beklenenler)} komut")
        for h in hatalar:
            print("    " + h)
        toplam_hata += len(hatalar)
    return 1 if toplam_hata else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv))
