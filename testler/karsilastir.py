"""Üretilen sonuçları beklenen sonuçlarla alan alan karşılaştırır.

Kullanım: python testler/karsilastir.py            (bütün senaryolar)
Her senaryo klasöründe baslangic.json, komutlar.jsonl, sonuclar.jsonl bulunur.
Fazladan alan hata sayılmaz; eksik veya farklı alan hata sayılır (Bölüm 5).
"""
import io
import json
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))
from main import calistir  # noqa: E402


def kapsar(beklenen, uretilen) -> bool:
    if isinstance(beklenen, dict):
        return isinstance(uretilen, dict) and all(
            k in uretilen and kapsar(v, uretilen[k]) for k, v in beklenen.items())
    if isinstance(beklenen, list):
        return (isinstance(uretilen, list) and len(beklenen) == len(uretilen)
                and all(kapsar(a, b) for a, b in zip(beklenen, uretilen)))
    return beklenen == uretilen


def senaryo_calistir(klasor: Path) -> int:
    tampon = io.StringIO()
    calistir(str(klasor / "baslangic.json"), str(klasor / "komutlar.jsonl"), tampon)
    uretilen = [json.loads(s) for s in tampon.getvalue().splitlines() if s.strip()]
    beklenen = [json.loads(s) for s in (klasor / "sonuclar.jsonl").read_text("utf-8").splitlines()
                if s.strip()]
    hata = 0
    if len(uretilen) != len(beklenen):
        print(f"  satir sayisi farkli: beklenen {len(beklenen)}, uretilen {len(uretilen)}")
        hata += 1
    for b, u in zip(beklenen, uretilen):
        if not kapsar(b, u):
            hata += 1
            print(f"  no {b.get('no')} FARKLI\n    beklenen: {json.dumps(b, ensure_ascii=False)}"
                  f"\n    uretilen: {json.dumps(u, ensure_ascii=False)}")
    print(f"{'GECTI' if hata == 0 else 'KALDI'}  {klasor.relative_to(KOK)}  ({len(beklenen)} satir)")
    return hata


def main() -> int:
    klasorler = [KOK / "ornek"] + sorted(p for p in (KOK / "testler").iterdir()
                                         if p.is_dir() and (p / "komutlar.jsonl").exists())
    toplam = sum(senaryo_calistir(k) for k in klasorler)
    print(f"\nToplam hatali satir: {toplam}")
    return 1 if toplam else 0


if __name__ == "__main__":
    sys.exit(main())
