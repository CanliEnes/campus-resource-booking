"""Örnek senaryonun 19 işlemini arayüzün kendi form, düğme ve diyaloglarıyla yapar ve
olay günlüğündeki sonuçları beklenen.jsonl ile karşılaştırır.

Kullanım: python testler/arayuz_senaryo_testi.py [--bekle]
--bekle verilirse pencere test bittikten sonra açık kalır.
"""

import json
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from arayuz.diyaloglar import KaynakEkle, KullaniciEkle  # noqa: E402
from arayuz.uygulama import Uygulama  # noqa: E402
from testleri_calistir import farklar  # noqa: E402

SENARYO = KOK / "testler" / "01_ornek_senaryo"


def tek_talep(u, kullanici, kaynak, tarih, bas, bit):
    u.kullanici_sec(kullanici)
    u.v_mod.set("tek")
    u._mod_degisti()
    u.v_kaynak.set(u._kaynak_metni(kaynak))
    u.v_tarih.set(tarih)
    u.v_bas.set(bas)
    u.v_bit.set(bit)


def kullanici_ekle(u, id, ad, rol, bakiye, guven):
    d = KullaniciEkle(u)
    d.v_id.set(id)
    d.v_ad.set(ad)
    d.v_rol.set(rol)
    d.v_bakiye.set(str(bakiye))
    d.v_guven.set(str(guven))
    d.ekle()


def kaynak_ekle(u, id, ad, tur, roller):
    d = KaynakEkle(u)
    d.v_tur.set(tur)
    d.v_id.set(id)
    d.v_ad.set(ad)
    for rol, degisken in d.roller.items():
        degisken.set(rol in roller)
    d.ekle()


def senaryo(u):
    g = "2027-03-08"
    kullanici_ekle(u, "u1", "Ayşe Kaya", "OGRENCI", 120, 80)
    kullanici_ekle(u, "u2", "Mehmet Demir", "OGRENCI", 120, 80)
    kaynak_ekle(u, "YAZ-1", "3B Yazıcı 1", "YAZICI", ["OGRENCI"])
    kaynak_ekle(u, "LAB-1", "Laboratuvar 1", "LAB", ["OGRENCI", "ARASTIRMACI", "TEKNISYEN"])
    for kisi, kaynak, bas, bit in [("u1", "YAZ-1", "11:00", "13:00"),
                                   ("u2", "YAZ-2", "10:00", "12:00"),
                                   ("u2", "YAZ-2", "12:30", "13:30"),
                                   ("u2", "LAB-1", "14:00", "15:00"),
                                   ("u1", "YAZ-1", "13:10", "14:00"),
                                   ("u1", "YAZ-1", "13:15", "14:00")]:
        tek_talep(u, kisi, kaynak, g, bas, bit)
        u.talep_gonder()
    tek_talep(u, "u3", "CIH-1", g, "14:00", "16:00")
    u.fiyat_sor()
    u.v_mod.set("paket")
    u._mod_degisti()
    for kalem, (kaynak, bas, bit) in zip(u.kalemler, [("CIH-1", "14:00", "16:00"),
                                                      ("ODA-1", "14:00", "16:00")]):
        kalem["v_kaynak"].set(kaynak)
        kalem["v_tarih"].set(g)
        kalem["v_bas"].set(bas)
        kalem["v_bit"].set(bit)
    u.talep_gonder()
    tek_talep(u, "u1", "CIH-1", g, "16:30", "17:30")
    u.talep_gonder()
    tek_talep(u, "u1", "ODA-2", "2027-03-16", "09:00", "10:00")
    u.talep_gonder()
    tek_talep(u, "u2", "YAZ-1", g, "12:00", "13:00")
    u.talep_gonder()                       # KESISME: günlüğe yazılır, ama örnekte 15. komut bekleme
    u.gunluk.pop()                         # örnek dosyada bu deneme yok; yalnızca düğmeyi sınıyoruz
    u.gunluk_agaci.delete(u.gunluk_agaci.get_children()[-1])
    u.talep_sonucu.dugme.invoke()          # "Bu talep için bekleme kaydı aç"
    u.v_hedef_tarih.set(g)
    u.v_hedef_saat.set("11:20")
    u.saati_hedefe_al()
    u.eylem("giris", "r1")
    u.eylem("iptal", "r4")
    u.kullanici_sec("u2")
    u.kullanici_sorgula()


def main():
    u = Uygulama(str(SENARYO / "baslangic.json"))
    u.update()

    def calis():
        senaryo(u)
        u.update()
        beklenen = [json.loads(s) for s in
                    (SENARYO / "beklenen.jsonl").read_text(encoding="utf-8").splitlines() if s]
        gercek = [satir for _, satir in u.gunluk]
        hatalar = [] if len(beklenen) == len(gercek) else [f"{len(gercek)} satır üretildi"]
        for b, g in zip(beklenen, gercek):
            hatalar += [f"no {b['no']}{f}" for f in farklar(b, g)]
        print("ARAYÜZ SENARYOSU:", "GEÇTİ" if not hatalar else "KALDI", f"({len(gercek)} işlem)")
        for h in hatalar:
            print("   ", h)
        u.rezervasyon_sec("r5")
        if "--bekle" not in sys.argv:
            u.after(300, u.destroy)
        u.exitcode = 1 if hatalar else 0

    u.after(500, calis)
    u.mainloop()
    return getattr(u, "exitcode", 1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
