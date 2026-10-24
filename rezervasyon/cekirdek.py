"""Kampüs Kaynak Rezervasyon Sistemi - rezervasyon modülü.

Bu modül arayüzden bağımsızdır. Hem komut satırı (calistir.py) hem de masaüstü
uygulaması (masaustu.py) aynı RezervasyonSistemi sınıfını kullanır.

Her komut aynı adlı bir metotla karşılanır ve bir sözlük döndürür:
    {"durum": "TAMAM", ...ek alanlar}  veya  {"durum": "RED", "kod": "..."}

Kaynak türleri, roller, kaynaklar, bakım pencereleri, kullanıcılar ve başlangıç
saati başlangıç dosyasından okunur. Aşağıdaki sabitler ise sistemin kural
tanımının (K1-K11, README) kendisidir ve dosyaya bağlı değildir.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from fractions import Fraction

ZAMAN_BICIMI = "%Y-%m-%dT%H:%M"
GUN_BICIMI = "%Y-%m-%d"

# --- Sabit kurallar (K1-K11) -------------------------------------------------
DILIM = timedelta(minutes=15)            # K1, K5: 15 dakikalık adım / dilim
CALISMA_BASI = time(8, 0)                # K1: 08:00
CALISMA_SONU = time(22, 0)               # K1: 22:00
EN_KISA_SURE = timedelta(minutes=30)     # K1
BANT_SURESI_SAAT = 2                     # K5: iki saatlik bantlar
BANT_DAKIKA = BANT_SURESI_SAAT * 60
PIK_BASI, PIK_SONU = 10, 16              # K5: 10:00-16:00
PIK_CARPANI = Fraction(3, 2)             # K5: enerji yoğun türlerde 1,5
ARDISIK_BOSLUK = timedelta(minutes=60)   # K4
GIRIS_ONCE = timedelta(minutes=10)       # K8
GIRIS_SONRA = timedelta(minutes=15)      # K8: giriş penceresi ve GELMEDI
TAM_IADE_SINIRI = timedelta(hours=24)    # K8 iade tablosu
YARI_IADE_SINIRI = timedelta(hours=2)
GUVEN_ESIGI = 50                         # K8: altında ileri gün 1, paket yok
DUSUK_GUVEN_ILERI_GUN = 1
GELMEDI_CEZASI = -15
GEC_IPTAL_CEZASI = -5
TAMAMLAMA_ODULU = 2
PAKET_EN_AZ, PAKET_EN_COK = 2, 4         # K7

# Rezervasyon durumları
ONAYLI = "ONAYLI"
KULLANIMDA = "KULLANIMDA"
TAMAMLANDI = "TAMAMLANDI"
IPTAL = "IPTAL"
GELMEDI = "GELMEDI"

AKTIF_DURUMLAR = (ONAYLI, KULLANIMDA)                  # K3 kesişme, K5 doluluk
HAZIRLIK_DURUMLARI = (ONAYLI, KULLANIMDA, TAMAMLANDI)  # K3 hazırlık, K4 ardışık

# Komut adı -> metoda geçirilecek alanlar
KOMUT_ALANLARI = {
    "saat": ("zaman",),
    "rezervasyon": ("kullanici", "kaynak", "baslangic", "bitis"),
    "paket": ("kullanici", "kalemler"),
    "fiyat": ("kullanici", "kaynak", "baslangic", "bitis"),
    "iptal": ("rezervasyon",),
    "giris": ("rezervasyon",),
    "cikis": ("rezervasyon",),
    "bekleme": ("kullanici", "kaynak", "baslangic", "bitis"),
    "sorgu": ("tur", "id", "gun"),
    "kullanici_ekle": ("id", "ad", "rol", "sertifikalar", "bakiye", "guvenilirlik"),
    "kaynak_ekle": ("id", "ad", "tur", "izinli_roller"),
}


# --- Yardımcılar -------------------------------------------------------------
def zaman_coz(deger) -> datetime:
    if not isinstance(deger, str):
        raise ValueError("zaman metin olmalı")
    return datetime.strptime(deger, ZAMAN_BICIMI)


def zaman_yaz(an: datetime) -> str:
    return an.strftime(ZAMAN_BICIMI)


def gun_coz(deger) -> date:
    if not isinstance(deger, str):
        raise ValueError("gün metin olmalı")
    return datetime.strptime(deger, GUN_BICIMI).date()


def kesisir(b1: datetime, e1: datetime, b2: datetime, e2: datetime) -> bool:
    """Başlangıç dahil, bitiş hariç iki aralık kesişiyor mu?"""
    return b1 < e2 and e1 > b2


def bosluk_ihlali(b: datetime, e: datetime, b2: datetime, e2: datetime, bosluk: timedelta) -> bool:
    """K3/K4 formülü: b < e' + bosluk ve e + bosluk > b'."""
    return b < e2 + bosluk and e + bosluk > b2


def adimda_mi(an: datetime) -> bool:
    return an.minute % 15 == 0 and an.second == 0


def _tam_sayi_mi(deger) -> bool:
    return isinstance(deger, int) and not isinstance(deger, bool)


def _sayi_mi(deger) -> bool:
    return isinstance(deger, (int, float)) and not isinstance(deger, bool)


def _bul(sozluk: dict, anahtar):
    try:
        return sozluk.get(anahtar)
    except TypeError:  # liste gibi hash'lenemeyen bir değer geldiyse
        return None


def _red(kod: str, **ek) -> dict:
    return {"durum": "RED", "kod": kod, **ek}


def _tamam(**ek) -> dict:
    return {"durum": "TAMAM", **ek}


# --- Veri modeli -------------------------------------------------------------
@dataclass
class Kullanici:
    id: str
    ad: str
    rol: str
    sertifikalar: list
    bakiye: int
    guvenilirlik: int


@dataclass
class Kaynak:
    id: str
    ad: str
    tur: str
    izinli_roller: list
    eklenme: int = 0  # eklenme sırası (arayüzde sıralama için)


@dataclass
class BakimPenceresi:
    kaynak: str
    baslangic: datetime
    bitis: datetime


@dataclass
class Rezervasyon:
    no: int
    kullanici: str
    kaynak: str
    baslangic: datetime
    bitis: datetime
    ucret: int
    durum: str = ONAYLI
    paket: str | None = None

    @property
    def id(self) -> str:
        return f"r{self.no}"


@dataclass
class BeklemeKaydi:
    no: int
    kullanici: str
    kaynak: str
    baslangic: datetime
    bitis: datetime
    kayit_saati: datetime

    @property
    def id(self) -> str:
        return f"b{self.no}"


# --- Sistem ------------------------------------------------------------------
class RezervasyonSistemi:
    """Rezervasyon modülü. Tüm durum bellekte tutulur."""

    def __init__(self, baslangic: dict):
        self.simdi: datetime = zaman_coz(baslangic["saat"])
        self.kaynak_turleri: dict[str, dict] = {
            ad: dict(ozellik) for ad, ozellik in baslangic.get("kaynak_turleri", {}).items()
        }
        self.roller: dict[str, dict] = {
            ad: dict(ozellik) for ad, ozellik in baslangic.get("roller", {}).items()
        }
        self.kaynaklar: dict[str, Kaynak] = {}
        for k in baslangic.get("kaynaklar", []):
            self._kaynak_kaydet(k["id"], k.get("ad", ""), k["tur"], k.get("izinli_roller", []))
        self.bakim_pencereleri: list[BakimPenceresi] = [
            BakimPenceresi(b["kaynak"], zaman_coz(b["baslangic"]), zaman_coz(b["bitis"]))
            for b in baslangic.get("bakim_pencereleri", [])
        ]
        self.kullanicilar: dict[str, Kullanici] = {}
        for u in baslangic.get("kullanicilar", []):
            self.kullanicilar[u["id"]] = Kullanici(
                u["id"], u.get("ad", ""), u["rol"], list(u.get("sertifikalar") or []),
                u.get("bakiye", 0), u.get("guvenilirlik", 100),
            )
        self.rezervasyonlar: dict[str, Rezervasyon] = {}
        self.bekleme_kayitlari: dict[str, BeklemeKaydi] = {}
        self._sayaclar = {"r": 0, "b": 0, "p": 0}

    @classmethod
    def dosyadan(cls, yol: str) -> "RezervasyonSistemi":
        with open(yol, encoding="utf-8-sig") as f:
            return cls(json.load(f))

    # --- Komut dağıtıcı ------------------------------------------------------
    def komut_isle(self, komut: dict) -> dict:
        """Bir komut sözlüğünü ilgili metoda yönlendirir. Sonuç komut adını içerir."""
        ad = komut.get("komut") if isinstance(komut, dict) else None
        if ad not in KOMUT_ALANLARI:
            return {"komut": ad, **_red("BILINMEYEN_KOMUT")}
        alanlar = {alan: komut.get(alan) for alan in KOMUT_ALANLARI[ad]}
        try:
            sonuc = getattr(self, ad)(**alanlar)
        except (KeyError, TypeError, ValueError, AttributeError):
            sonuc = _red("GECERSIZ_DEGER")
        return {"komut": ad, **sonuc}

    # --- Okuma yardımcıları (arayüz de kullanır) -----------------------------
    def kota(self, kullanici: Kullanici):
        return self.roller[kullanici.rol]["haftalik_kota"]

    def hazirlik_suresi(self, kaynak_id: str) -> timedelta:
        tur = self.kaynak_turleri[self.kaynaklar[kaynak_id].tur]
        return timedelta(minutes=tur.get("hazirlik_dk", 0))

    def ileri_gun(self, kullanici: Kullanici) -> int:
        if kullanici.guvenilirlik < GUVEN_ESIGI:
            return DUSUK_GUVEN_ILERI_GUN
        return self.roller[kullanici.rol]["ileri_gun"]

    def bekleme_sirasi(self, kaynak_id: str) -> list[BeklemeKaydi]:
        """K9: güvenilirlik yüksek olan, sonra önce kaydolan, sonra numarası küçük olan."""
        kayitlar = [b for b in self.bekleme_kayitlari.values() if b.kaynak == kaynak_id]
        return sorted(kayitlar, key=lambda b: (
            -self.kullanicilar[b.kullanici].guvenilirlik, b.kayit_saati, b.no))

    def tum_sertifikalar(self) -> list[str]:
        sertifikalar = []
        for tur in self.kaynak_turleri.values():
            for s in self._gereken_sertifikalar(tur):
                if s not in sertifikalar:
                    sertifikalar.append(s)
        for k in self.kullanicilar.values():
            for s in k.sertifikalar:
                if s not in sertifikalar:
                    sertifikalar.append(s)
        return sertifikalar

    # --- Komutlar ------------------------------------------------------------
    def kullanici_ekle(self, id=None, ad=None, rol=None, sertifikalar=None,
                       bakiye=None, guvenilirlik=None) -> dict:
        if _bul(self.kullanicilar, id) is not None:
            return _red("ID_MEVCUT")
        if _bul(self.roller, rol) is None:
            return _red("TANIMSIZ_DEGER")
        if (not isinstance(id, str) or not id
                or not _sayi_mi(bakiye) or bakiye < 0 or bakiye > self.roller[rol]["haftalik_kota"]
                or not _tam_sayi_mi(guvenilirlik) or not 0 <= guvenilirlik <= 100
                or (sertifikalar is not None and not isinstance(sertifikalar, list))):
            return _red("GECERSIZ_DEGER")
        self.kullanicilar[id] = Kullanici(id, ad or "", rol, list(sertifikalar or []),
                                          bakiye, guvenilirlik)
        return _tamam()

    def kaynak_ekle(self, id=None, ad=None, tur=None, izinli_roller=None) -> dict:
        if _bul(self.kaynaklar, id) is not None:
            return _red("ID_MEVCUT")
        if (_bul(self.kaynak_turleri, tur) is None or not isinstance(izinli_roller, list)
                or any(_bul(self.roller, r) is None for r in izinli_roller)):
            return _red("TANIMSIZ_DEGER")
        if not isinstance(id, str) or not id:
            return _red("GECERSIZ_DEGER")
        self._kaynak_kaydet(id, ad or "", tur, izinli_roller)
        return _tamam()

    def rezervasyon(self, kullanici=None, kaynak=None, baslangic=None, bitis=None) -> dict:
        kod, ucret, bas, bit = self._talep_dogrula(kullanici, kaynak, baslangic, bitis)
        if kod:
            return _red(kod)
        rez = self._rezervasyon_olustur(kullanici, kaynak, bas, bit, ucret)
        return _tamam(rezervasyon_id=rez.id, ucret=ucret,
                      bakiye=self.kullanicilar[kullanici].bakiye)

    def fiyat(self, kullanici=None, kaynak=None, baslangic=None, bitis=None) -> dict:
        kod, ucret, _, _ = self._talep_dogrula(kullanici, kaynak, baslangic, bitis,
                                               bakiye_kontrolu=False)
        if kod:
            return _red(kod)
        return _tamam(ucret=ucret)

    def paket(self, kullanici=None, kalemler=None) -> dict:
        """K7: ya tüm kalemler alınır ya hiçbiri."""
        kisi = _bul(self.kullanicilar, kullanici)
        if kisi is None:
            return _red("BULUNAMADI", kalemler=[])
        if not isinstance(kalemler, list) or not PAKET_EN_AZ <= len(kalemler) <= PAKET_EN_COK:
            return _red("PAKET_BOYUTU", kalemler=[])
        if kisi.guvenilirlik < GUVEN_ESIGI:
            return _red("GUVENILIRLIK_DUSUK", kalemler=[])

        # Her kalem paketten önceki duruma göre, bakiye dışındaki kurallarla doğrulanır.
        sonuclar, gecerliler = [], []
        for sira, kalem in enumerate(kalemler):
            kalem = kalem if isinstance(kalem, dict) else {}
            kod, ucret, bas, bit = self._talep_dogrula(
                kullanici, kalem.get("kaynak"), kalem.get("baslangic"), kalem.get("bitis"),
                bakiye_kontrolu=False)
            if kod:
                sonuclar.append({"sira": sira, "durum": "RED", "kod": kod})
            else:
                sonuclar.append({"sira": sira, "durum": "TAMAM"})
                gecerliler.append((kalem["kaynak"], bas, bit, ucret))
        if len(gecerliler) != len(kalemler):
            return _red("PAKET_RED", kalemler=sonuclar)

        # Paket içi: aynı kaynaktaki kalemler kesişme, hazırlık ve ardışık kullanım.
        for i in range(len(gecerliler)):
            for j in range(i + 1, len(gecerliler)):
                kaynak_i, bas_i, bit_i, _ = gecerliler[i]
                kaynak_j, bas_j, bit_j, _ = gecerliler[j]
                if kaynak_i != kaynak_j:
                    continue
                bosluk = max(self.hazirlik_suresi(kaynak_i), ARDISIK_BOSLUK)
                if bosluk_ihlali(bas_i, bit_i, bas_j, bit_j, bosluk):
                    return _red("PAKET_ICI_KESISME", kalemler=sonuclar)

        toplam = sum(g[3] for g in gecerliler)
        if toplam > kisi.bakiye:
            return _red("BAKIYE_YETERSIZ", kalemler=sonuclar)

        paket_id = f"p{self._yeni_numara('p')}"
        olusanlar = [self._rezervasyon_olustur(kullanici, k, b, e, u, paket=paket_id)
                     for k, b, e, u in gecerliler]
        return _tamam(paket_id=paket_id, rezervasyonlar=[r.id for r in olusanlar],
                      ucretler=[r.ucret for r in olusanlar], toplam=toplam, bakiye=kisi.bakiye)

    def iptal(self, rezervasyon=None) -> dict:
        rez = _bul(self.rezervasyonlar, rezervasyon)
        if rez is None:
            return _red("BULUNAMADI")
        if rez.durum != ONAYLI:
            return _red("DURUM_HATASI")
        kisi = self.kullanicilar[rez.kullanici]
        kalan = rez.baslangic - self.simdi
        if kalan >= TAM_IADE_SINIRI:
            iade = rez.ucret
        elif kalan >= YARI_IADE_SINIRI:
            iade = rez.ucret // 2
        else:
            iade = 0
            self._guvenilirlik_degistir(kisi, GEC_IPTAL_CEZASI)
        eklenen = self._iade_et(kisi, iade)
        rez.durum = IPTAL
        olaylar = self._bekleme_tara(rez.kaynak)
        return _tamam(iade=eklenen, bakiye=kisi.bakiye, guvenilirlik=kisi.guvenilirlik,
                      olaylar=olaylar)

    def giris(self, rezervasyon=None) -> dict:
        rez = _bul(self.rezervasyonlar, rezervasyon)
        if rez is None:
            return _red("BULUNAMADI")
        if rez.durum != ONAYLI:
            return _red("DURUM_HATASI")
        if not rez.baslangic - GIRIS_ONCE <= self.simdi <= rez.baslangic + GIRIS_SONRA:
            return _red("GIRIS_PENCERESI_DISI")
        rez.durum = KULLANIMDA
        return _tamam(yeni_durum=KULLANIMDA)

    def cikis(self, rezervasyon=None) -> dict:
        rez = _bul(self.rezervasyonlar, rezervasyon)
        if rez is None:
            return _red("BULUNAMADI")
        if rez.durum != KULLANIMDA:
            return _red("DURUM_HATASI")
        # Erken çıkış: bitiş çıkış saati olur, kalan süre serbest kalır, iade ve
        # güvenilirlik değişikliği yoktur.
        rez.bitis = self.simdi
        rez.durum = TAMAMLANDI
        olaylar = self._bekleme_tara(rez.kaynak)
        return _tamam(yeni_durum=TAMAMLANDI,
                      guvenilirlik=self.kullanicilar[rez.kullanici].guvenilirlik,
                      olaylar=olaylar)

    def bekleme(self, kullanici=None, kaynak=None, baslangic=None, bitis=None) -> dict:
        """K9: yalnızca KESISME veya HAZIRLIK_IHLALI ile reddedilen talep beklemeye girer."""
        kod, _, bas, bit = self._talep_dogrula(kullanici, kaynak, baslangic, bitis,
                                               bakiye_kontrolu=False)
        if kod is None:
            return _red("BEKLEME_GEREKSIZ")
        if kod not in ("KESISME", "HAZIRLIK_IHLALI"):
            return _red(kod)
        kayit = BeklemeKaydi(self._yeni_numara("b"), kullanici, kaynak, bas, bit, self.simdi)
        self.bekleme_kayitlari[kayit.id] = kayit
        sira = [b.id for b in self.bekleme_sirasi(kaynak)].index(kayit.id) + 1
        return _tamam(bekleme_id=kayit.id, sira=sira)

    def sorgu(self, tur=None, id=None, gun=None) -> dict:
        if tur == "kullanici":
            kisi = _bul(self.kullanicilar, id)
            if kisi is None:
                return _red("BULUNAMADI")
            rezler = sorted((r for r in self.rezervasyonlar.values() if r.kullanici == id),
                            key=lambda r: (r.baslangic, r.no))
            return _tamam(bakiye=kisi.bakiye, guvenilirlik=kisi.guvenilirlik,
                          rezervasyonlar=[{
                              "id": r.id, "kaynak": r.kaynak,
                              "baslangic": zaman_yaz(r.baslangic), "bitis": zaman_yaz(r.bitis),
                              "durum": r.durum, "ucret": r.ucret,
                          } for r in rezler])
        if tur == "kaynak":
            if _bul(self.kaynaklar, id) is None:
                return _red("BULUNAMADI")
            try:
                gun_basi = datetime.combine(gun_coz(gun), time(0, 0))
            except ValueError:
                return _red("GECERSIZ_DEGER")
            gun_sonu = gun_basi + timedelta(days=1)
            ogeler = []
            for r in self.rezervasyonlar.values():
                if (r.kaynak == id and r.durum in AKTIF_DURUMLAR
                        and kesisir(r.baslangic, r.bitis, gun_basi, gun_sonu)):
                    ogeler.append(((r.baslangic, 1, r.no), {
                        "baslangic": zaman_yaz(r.baslangic), "bitis": zaman_yaz(r.bitis),
                        "tur": "REZERVASYON", "rezervasyon": r.id}))
            for b in self.bakim_pencereleri:
                if b.kaynak == id and kesisir(b.baslangic, b.bitis, gun_basi, gun_sonu):
                    ogeler.append(((b.baslangic, 0, 0), {
                        "baslangic": zaman_yaz(b.baslangic), "bitis": zaman_yaz(b.bitis),
                        "tur": "BAKIM"}))
            ogeler.sort(key=lambda o: o[0])
            return _tamam(doluluk=[o[1] for o in ogeler])
        return _red("GECERSIZ_DEGER")

    def saat(self, zaman=None) -> dict:
        """K11: eski saatten sonraki ve yeni saate kadar (dahil) olaylar sırayla işlenir."""
        try:
            yeni = zaman_coz(zaman)
        except ValueError:
            return _red("GECERSIZ_DEGER")
        if yeni < self.simdi:
            return _red("SAAT_GERI")
        olaylar = []
        while True:
            pazartesi = self._sonraki_pazartesi(self.simdi)
            adaylar = [pazartesi] if pazartesi <= yeni else []
            for r in self.rezervasyonlar.values():
                if r.durum == KULLANIMDA and r.bitis <= yeni:
                    adaylar.append(r.bitis)
                elif r.durum == ONAYLI and r.baslangic + GIRIS_SONRA <= yeni:
                    adaylar.append(r.baslangic + GIRIS_SONRA)
            if not adaylar:
                break
            an = max(min(adaylar), self.simdi)
            self.simdi = an
            self._eski_beklemeleri_sil()
            olaylar.extend(self._olaylari_isle(an, haftalik_sifirlama=(an == pazartesi)))
        self.simdi = yeni
        self._eski_beklemeleri_sil()
        return _tamam(olaylar=olaylar)

    # --- İç işleyiş ----------------------------------------------------------
    def _kaynak_kaydet(self, id, ad, tur, izinli_roller):
        self.kaynaklar[id] = Kaynak(id, ad, tur, list(izinli_roller), len(self.kaynaklar))

    def _yeni_numara(self, on_ek: str) -> int:
        self._sayaclar[on_ek] += 1
        return self._sayaclar[on_ek]

    @staticmethod
    def _gereken_sertifikalar(tur: dict) -> list:
        sertifika = tur.get("sertifika")
        if not sertifika:
            return []
        return list(sertifika) if isinstance(sertifika, list) else [sertifika]

    def _talep_dogrula(self, kullanici_id, kaynak_id, baslangic, bitis, bakiye_kontrolu=True):
        """Metin alanlarla gelen talebi K10 sırasıyla denetler."""
        kisi = _bul(self.kullanicilar, kullanici_id)
        kaynak = _bul(self.kaynaklar, kaynak_id)
        if kisi is None or kaynak is None:
            return "BULUNAMADI", None, None, None
        try:
            bas, bit = zaman_coz(baslangic), zaman_coz(bitis)
        except ValueError:
            return "ZAMAN_ADIMI_HATASI", None, None, None
        kod, ucret = self._kurallari_denetle(kisi, kaynak, bas, bit, bakiye_kontrolu)
        return kod, ucret, bas, bit

    def _kurallari_denetle(self, kisi: Kullanici, kaynak: Kaynak, bas: datetime,
                           bit: datetime, bakiye_kontrolu: bool):
        """K10 adım 2-13. (kod, ucret) döner; talep geçerliyse kod None'dır."""
        if not adimda_mi(bas) or not adimda_mi(bit) or bit <= bas:
            return "ZAMAN_ADIMI_HATASI", None
        if bas < self.simdi:
            return "GECMIS_ZAMAN", None
        if bas.date() != bit.date() or bas.time() < CALISMA_BASI or bit.time() > CALISMA_SONU:
            return "CALISMA_SAATI_DISI", None
        rol = self.roller.get(kisi.rol, {})
        sure = bit - bas
        if sure < EN_KISA_SURE or sure > timedelta(minutes=rol.get("azami_sure_dk", 0)):
            return "SURE_SINIRI", None
        if bas > self.simdi + timedelta(days=self.ileri_gun(kisi)):
            return "ILERI_TARIH_SINIRI", None
        if kisi.rol not in kaynak.izinli_roller:
            return "ROL_IZNI_YOK", None
        tur = self.kaynak_turleri[kaynak.tur]
        if any(s not in kisi.sertifikalar for s in self._gereken_sertifikalar(tur)):
            return "SERTIFIKA_YOK", None
        if any(b.kaynak == kaynak.id and kesisir(bas, bit, b.baslangic, b.bitis)
               for b in self.bakim_pencereleri):
            return "BAKIM", None

        ayni_kaynak = [r for r in self.rezervasyonlar.values() if r.kaynak == kaynak.id]
        if any(r.durum in AKTIF_DURUMLAR and kesisir(bas, bit, r.baslangic, r.bitis)
               for r in ayni_kaynak):
            return "KESISME", None
        hazirlik = timedelta(minutes=tur.get("hazirlik_dk", 0))
        if any(r.durum in HAZIRLIK_DURUMLARI
               and bosluk_ihlali(bas, bit, r.baslangic, r.bitis, hazirlik)
               for r in ayni_kaynak):
            return "HAZIRLIK_IHLALI", None
        if any(r.kullanici == kisi.id and r.durum in HAZIRLIK_DURUMLARI
               and bosluk_ihlali(bas, bit, r.baslangic, r.bitis, ARDISIK_BOSLUK)
               for r in ayni_kaynak):
            return "ARDISIK_KULLANIM", None

        ucret = self._ucret_hesapla(kaynak, bas, bit)
        if bakiye_kontrolu and ucret > kisi.bakiye:
            return "BAKIYE_YETERSIZ", ucret
        return None, ucret

    def _ucret_hesapla(self, kaynak: Kaynak, bas: datetime, bit: datetime) -> int:
        """K5: 15 dakikalık dilimlerin toplamı, en yakın tam sayıya (0,5 yukarı)."""
        tur = self.kaynak_turleri[kaynak.tur]
        temel = Fraction(str(tur["temel_ucret"]))
        enerji_yogun = bool(tur.get("enerji_yogun"))
        kaynak_sayisi = sum(1 for k in self.kaynaklar.values() if k.tur == kaynak.tur)
        bant_doluluk: dict[datetime, int] = {}
        toplam = Fraction(0)
        an = bas
        while an < bit:
            bant_basi = self._bant_basi(an)
            if bant_basi not in bant_doluluk:
                bant_doluluk[bant_basi] = self._dolu_dakika(
                    kaynak.tur, bant_basi, bant_basi + timedelta(hours=BANT_SURESI_SAAT))
            toplam += temel * Fraction(1, 4) * self._bant_carpani(
                bant_doluluk[bant_basi], kaynak_sayisi) * self._pik_carpani(an, enerji_yogun)
            an += DILIM
        return math.floor(toplam + Fraction(1, 2))

    @staticmethod
    def _bant_basi(an: datetime) -> datetime:
        saat = CALISMA_BASI.hour + (an.hour - CALISMA_BASI.hour) // BANT_SURESI_SAAT * BANT_SURESI_SAAT
        return an.replace(hour=saat, minute=0)

    @staticmethod
    def _bant_carpani(dolu_dakika: int, kaynak_sayisi: int) -> Fraction:
        """1 + 0,25 × ⌊4 × doluluk⌋, doluluk = dolu / (kaynak sayısı × 120); en fazla 2,00."""
        adim = min(4, (4 * dolu_dakika) // (kaynak_sayisi * BANT_DAKIKA))
        return 1 + Fraction(adim, 4)

    @staticmethod
    def _pik_carpani(an: datetime, enerji_yogun: bool) -> Fraction:
        if enerji_yogun and PIK_BASI <= an.hour < PIK_SONU:
            return PIK_CARPANI
        return Fraction(1)

    def _dolu_dakika(self, tur: str, bant_basi: datetime, bant_sonu: datetime) -> int:
        dakika = 0
        for r in self.rezervasyonlar.values():
            if r.durum in AKTIF_DURUMLAR and self.kaynaklar[r.kaynak].tur == tur:
                ortak = min(r.bitis, bant_sonu) - max(r.baslangic, bant_basi)
                if ortak > timedelta(0):
                    dakika += int(ortak.total_seconds() // 60)
        return dakika

    def _rezervasyon_olustur(self, kullanici_id, kaynak_id, bas, bit, ucret, paket=None):
        rez = Rezervasyon(self._yeni_numara("r"), kullanici_id, kaynak_id, bas, bit, ucret,
                          paket=paket)
        self.rezervasyonlar[rez.id] = rez
        self.kullanicilar[kullanici_id].bakiye -= ucret
        return rez

    def _iade_et(self, kisi: Kullanici, miktar: int):
        """K6: bakiye haftalık kotayı aşamaz; dönen değer gerçekte eklenen miktardır."""
        eklenen = max(0, min(miktar, self.kota(kisi) - kisi.bakiye))
        kisi.bakiye += eklenen
        return eklenen

    @staticmethod
    def _guvenilirlik_degistir(kisi: Kullanici, fark: int):
        kisi.guvenilirlik = max(0, min(100, kisi.guvenilirlik + fark))

    @staticmethod
    def _sonraki_pazartesi(an: datetime) -> datetime:
        """an'dan kesinlikle sonraki ilk Pazartesi 00:00."""
        gun_basi = datetime.combine(an.date(), time(0, 0))
        aday = gun_basi + timedelta(days=(7 - an.weekday()) % 7)
        if aday <= an:
            aday += timedelta(days=7)
        return aday

    def _eski_beklemeleri_sil(self):
        for kayit in [b for b in self.bekleme_kayitlari.values() if b.baslangic < self.simdi]:
            del self.bekleme_kayitlari[kayit.id]

    def _olaylari_isle(self, an: datetime, haftalik_sifirlama: bool) -> list[dict]:
        """K11 aynı andaki olay sırası: sıfırlama, TAMAMLANDI, GELMEDI, bekleme taraması."""
        zaman = zaman_yaz(an)
        olaylar = []
        if haftalik_sifirlama:
            for kisi in self.kullanicilar.values():
                if kisi.rol in self.roller:
                    kisi.bakiye = self.kota(kisi)
            olaylar.append({"zaman": zaman, "tur": "HAFTALIK_SIFIRLAMA"})

        sirali = sorted(self.rezervasyonlar.values(), key=lambda r: r.no)
        for rez in [r for r in sirali if r.durum == KULLANIMDA and r.bitis <= an]:
            rez.durum = TAMAMLANDI
            kisi = self.kullanicilar[rez.kullanici]
            self._guvenilirlik_degistir(kisi, TAMAMLAMA_ODULU)
            olaylar.append({"zaman": zaman, "tur": TAMAMLANDI, "rezervasyon": rez.id,
                            "kullanici": kisi.id, "guvenilirlik": kisi.guvenilirlik})

        bosalan_kaynaklar = []
        for rez in [r for r in sirali if r.durum == ONAYLI and r.baslangic + GIRIS_SONRA <= an]:
            rez.durum = GELMEDI
            kisi = self.kullanicilar[rez.kullanici]
            self._guvenilirlik_degistir(kisi, GELMEDI_CEZASI)
            olaylar.append({"zaman": zaman, "tur": GELMEDI, "rezervasyon": rez.id,
                            "kullanici": kisi.id, "guvenilirlik": kisi.guvenilirlik})
            if rez.kaynak not in bosalan_kaynaklar:
                bosalan_kaynaklar.append(rez.kaynak)

        for kaynak_id in bosalan_kaynaklar:
            olaylar.extend(self._bekleme_tara(kaynak_id))
        return olaylar

    def _bekleme_tara(self, kaynak_id: str) -> list[dict]:
        """K9: yer boşalınca bekleme kayıtları sırayla K10'un tüm kontrollerinden geçirilir."""
        self._eski_beklemeleri_sil()
        olaylar = []
        kaynak = self.kaynaklar[kaynak_id]
        for kayit in self.bekleme_sirasi(kaynak_id):
            kisi = self.kullanicilar[kayit.kullanici]
            kod, ucret = self._kurallari_denetle(kisi, kaynak, kayit.baslangic, kayit.bitis,
                                                 bakiye_kontrolu=True)
            if kod:
                continue
            rez = self._rezervasyon_olustur(kisi.id, kaynak_id, kayit.baslangic, kayit.bitis,
                                            ucret)
            del self.bekleme_kayitlari[kayit.id]
            olaylar.append({"zaman": zaman_yaz(self.simdi), "tur": "OTOMATIK_ATAMA",
                            "bekleme": kayit.id, "rezervasyon": rez.id, "kullanici": kisi.id,
                            "ucret": ucret, "bakiye": kisi.bakiye})
        return olaylar
