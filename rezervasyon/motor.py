"""Kampüs Kaynak Rezervasyon Sistemi - rezervasyon modülü.

Bu dosya arayüzden bağımsızdır. Hem komut satırı (calistir.bat / calistir.sh)
hem de masaüstü uygulaması aynı RezervasyonSistemi sınıfını kullanır.
Yorumlardaki K1..K11 numaraları ödev metnindeki kural numaralarıdır.

Kaynak türleri, roller, kaynaklar, bakım pencereleri, kullanıcılar ve simüle
saat başlangıç dosyasından okunur; burada sabit olarak yazılmaz. Aşağıdaki
sabitler ise ödev metninde herkes için aynı tanımlanan kurallardır.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from fractions import Fraction

# ---------------------------------------------------------------------------
# Kural sabitleri
# ---------------------------------------------------------------------------
ZAMAN_BICIMI = "%Y-%m-%dT%H:%M"
GUN_BICIMI = "%Y-%m-%d"

DILIM_DK = 15                    # K1, K5: zaman adımı ve ücret dilimi
CALISMA_BASLANGIC_SAAT = 8       # K1: 08:00
CALISMA_BITIS_SAAT = 22          # K1: 22:00
EN_KISA_SURE_DK = 30             # K1
BANT_SAAT = 2                    # K5: iki saatlik bantlar
PIK_BASLANGIC_SAAT = 10          # K5: 10:00-16:00 pik saat
PIK_BITIS_SAAT = 16
PIK_CARPANI = Fraction(3, 2)     # K5: 1,5
ARDISIK_BOSLUK_DK = 60           # K4
GIRIS_ONCE_DK = 10               # K8: giriş penceresi başlangıçtan 10 dk önce
GIRIS_SONRA_DK = 15              # K8: ... 15 dk sonrasına kadar, sonra GELMEDI
DUSUK_GUVENILIRLIK_SINIRI = 50   # K8: altındaysa ileri tarih 1 gün, paket yok
DUSUK_GUVENILIRLIK_ILERI_GUN = 1
PAKET_EN_AZ, PAKET_EN_COK = 2, 4  # K7
GUV_GELMEDI = -15                # K8
GUV_GEC_IPTAL = -5
GUV_ZAMANINDA_TAMAMLANDI = 2
TAM_IADE_SAAT = 24               # K8: iade tablosu
YARIM_IADE_SAAT = 2

# Rezervasyon durumları
ONAYLI = "ONAYLI"
KULLANIMDA = "KULLANIMDA"
TAMAMLANDI = "TAMAMLANDI"
IPTAL = "IPTAL"
GELMEDI = "GELMEDI"

AKTIF_DURUMLAR = (ONAYLI, KULLANIMDA)                    # K3 kesişme, K5 doluluk
HAZIRLIK_DURUMLARI = (ONAYLI, KULLANIMDA, TAMAMLANDI)    # K3 hazırlık, K4

TAMAM = "TAMAM"
RED = "RED"


# ---------------------------------------------------------------------------
# Yardımcı fonksiyonlar
# ---------------------------------------------------------------------------
def zaman_coz(metin: str) -> datetime:
    """'2027-03-08T11:00' biçimindeki metni datetime nesnesine çevirir."""
    if not isinstance(metin, str):
        raise ValueError("zaman metin olmalı")
    return datetime.strptime(metin, ZAMAN_BICIMI)


def zaman_yaz(an: datetime) -> str:
    return an.strftime(ZAMAN_BICIMI)


def dk(sayi: int) -> timedelta:
    return timedelta(minutes=sayi)


def kesisir(b1: datetime, e1: datetime, b2: datetime, e2: datetime) -> bool:
    """Başlangıç dahil, bitiş hariç iki aralık kesişiyor mu?"""
    return b1 < e2 and e1 > b2


def adima_oturur(an: datetime) -> bool:
    return an.minute % DILIM_DK == 0 and an.second == 0


def yuvarla(deger: Fraction) -> int:
    """En yakın tam sayıya yuvarlar; kesirli kısım tam 0,5 ise yukarı (K5)."""
    return math.floor(deger + Fraction(1, 2))


def tam_sayi_mi(deger) -> bool:
    if isinstance(deger, bool):
        return False
    if isinstance(deger, int):
        return True
    return isinstance(deger, float) and deger.is_integer()


def sayi_mi(deger) -> bool:
    return isinstance(deger, (int, float)) and not isinstance(deger, bool)


# ---------------------------------------------------------------------------
# Veri sınıfları
# ---------------------------------------------------------------------------
@dataclass
class Rezervasyon:
    id: str
    no: int                 # sıralama için: r12 -> 12
    kullanici: str
    kaynak: str
    baslangic: datetime
    bitis: datetime
    ucret: int
    durum: str = ONAYLI
    paket: str | None = None

    def sozluk(self) -> dict:
        veri = {
            "id": self.id,
            "kullanici": self.kullanici,
            "kaynak": self.kaynak,
            "baslangic": zaman_yaz(self.baslangic),
            "bitis": zaman_yaz(self.bitis),
            "ucret": self.ucret,
            "durum": self.durum,
        }
        if self.paket:
            veri["paket"] = self.paket
        return veri


@dataclass
class BeklemeKaydi:
    id: str
    no: int
    kullanici: str
    kaynak: str
    baslangic: datetime
    bitis: datetime
    kayit_saati: datetime

    def sozluk(self) -> dict:
        return {
            "id": self.id,
            "kullanici": self.kullanici,
            "kaynak": self.kaynak,
            "baslangic": zaman_yaz(self.baslangic),
            "bitis": zaman_yaz(self.bitis),
            "kayit_saati": zaman_yaz(self.kayit_saati),
        }


@dataclass
class Kontrol:
    """K10 doğrulamasının sonucu. kod None ise talep geçerlidir."""
    kod: str | None
    ucret: int | None = None
    baslangic: datetime | None = None
    bitis: datetime | None = None


def _tamam(komut: str, **alanlar) -> dict:
    return {"komut": komut, "durum": TAMAM, **alanlar}


def _red(komut: str, kod: str, **alanlar) -> dict:
    return {"komut": komut, "durum": RED, "kod": kod, **alanlar}


# ---------------------------------------------------------------------------
# Rezervasyon sistemi
# ---------------------------------------------------------------------------
class RezervasyonSistemi:
    """Bütün kuralların uygulandığı modül.

    Her public fonksiyon, Bölüm 5'teki sonuç satırının karşılığı olan bir
    sözlük döndürür (no alanı hariç; onu komut satırı ekler).
    """

    def __init__(self, baslangic: dict):
        self.saat: datetime = zaman_coz(baslangic["saat"])
        self.turler: dict[str, dict] = dict(baslangic["kaynak_turleri"])
        self.roller: dict[str, dict] = dict(baslangic["roller"])

        # Sözlükler eklenme sırasını korur; takvimde kaynaklar bu sırayla çizilir.
        self.kaynaklar: dict[str, dict] = {}
        for k in baslangic.get("kaynaklar", []):
            self.kaynaklar[k["id"]] = {
                "id": k["id"], "ad": k.get("ad", k["id"]), "tur": k["tur"],
                "izinli_roller": list(k.get("izinli_roller", [])),
            }

        self.bakimlar: list[dict] = []
        for b in baslangic.get("bakim_pencereleri", []):
            self.bakimlar.append({
                "kaynak": b["kaynak"],
                "baslangic": zaman_coz(b["baslangic"]),
                "bitis": zaman_coz(b["bitis"]),
            })

        self.kullanicilar: dict[str, dict] = {}
        for u in baslangic.get("kullanicilar", []):
            self.kullanicilar[u["id"]] = {
                "id": u["id"], "ad": u.get("ad", u["id"]), "rol": u["rol"],
                "sertifikalar": list(u.get("sertifikalar", [])),
                "bakiye": u["bakiye"], "guvenilirlik": int(u["guvenilirlik"]),
            }

        self.rezervasyonlar: dict[str, Rezervasyon] = {}
        self.beklemeler: dict[str, BeklemeKaydi] = {}
        self._r_sayac = 0
        self._b_sayac = 0
        self._p_sayac = 0

    @classmethod
    def dosyadan(cls, yol: str) -> "RezervasyonSistemi":
        with open(yol, encoding="utf-8-sig") as f:
            return cls(json.load(f))

    # ------------------------------------------------------------------
    # Komut dağıtıcı (komut dosyasındaki bir satırı ilgili fonksiyona verir)
    # ------------------------------------------------------------------
    def komut_isle(self, komut: dict) -> dict:
        ad = komut.get("komut") if isinstance(komut, dict) else None
        try:
            if ad == "saat":
                return self.saat_ilerlet(komut.get("zaman"))
            if ad == "rezervasyon":
                return self.rezervasyon(komut.get("kullanici"), komut.get("kaynak"),
                                        komut.get("baslangic"), komut.get("bitis"))
            if ad == "fiyat":
                return self.fiyat(komut.get("kullanici"), komut.get("kaynak"),
                                  komut.get("baslangic"), komut.get("bitis"))
            if ad == "paket":
                return self.paket(komut.get("kullanici"), komut.get("kalemler"))
            if ad == "iptal":
                return self.iptal(komut.get("rezervasyon"))
            if ad == "giris":
                return self.giris(komut.get("rezervasyon"))
            if ad == "cikis":
                return self.cikis(komut.get("rezervasyon"))
            if ad == "bekleme":
                return self.bekleme(komut.get("kullanici"), komut.get("kaynak"),
                                    komut.get("baslangic"), komut.get("bitis"))
            if ad == "sorgu":
                return self.sorgu(komut.get("tur"), komut.get("id"), komut.get("gun"))
            if ad == "kullanici_ekle":
                return self.kullanici_ekle(komut.get("id"), komut.get("ad"), komut.get("rol"),
                                           komut.get("sertifikalar"), komut.get("bakiye"),
                                           komut.get("guvenilirlik"))
            if ad == "kaynak_ekle":
                return self.kaynak_ekle(komut.get("id"), komut.get("ad"), komut.get("tur"),
                                        komut.get("izinli_roller"))
        except Exception:  # Beklenmeyen girdi programı durdurmasın; satır sayısı korunur.
            return _red(ad, "GECERSIZ_KOMUT")
        return _red(ad, "BILINMEYEN_KOMUT")

    # ------------------------------------------------------------------
    # K10: Rezervasyon talebinin doğrulanması
    # ------------------------------------------------------------------
    def _dogrula(self, kullanici_id, kaynak_id, baslangic, bitis,
                 bakiye_kontrol: bool = True) -> Kontrol:
        kul = self.kullanicilar.get(kullanici_id)
        kay = self.kaynaklar.get(kaynak_id)
        # 1
        if kul is None or kay is None:
            return Kontrol("BULUNAMADI")
        # 2 (çözülemeyen zaman da adım hatası sayılır)
        try:
            b = baslangic if isinstance(baslangic, datetime) else zaman_coz(baslangic)
            e = bitis if isinstance(bitis, datetime) else zaman_coz(bitis)
        except ValueError:
            return Kontrol("ZAMAN_ADIMI_HATASI")
        if not adima_oturur(b) or not adima_oturur(e) or e <= b:
            return Kontrol("ZAMAN_ADIMI_HATASI")
        # 3
        if b < self.saat:
            return Kontrol("GECMIS_ZAMAN")
        # 4
        gun_basi = datetime(b.year, b.month, b.day)
        if (e.date() != b.date()
                or b < gun_basi + timedelta(hours=CALISMA_BASLANGIC_SAAT)
                or e > gun_basi + timedelta(hours=CALISMA_BITIS_SAAT)):
            return Kontrol("CALISMA_SAATI_DISI")
        # 5
        rol = self.roller[kul["rol"]]
        sure_dk = (e - b) // dk(1)
        if sure_dk < EN_KISA_SURE_DK or sure_dk > rol["azami_sure_dk"]:
            return Kontrol("SURE_SINIRI")
        # 6
        if b > self.saat + timedelta(days=self._ileri_gun(kul)):
            return Kontrol("ILERI_TARIH_SINIRI")
        # 7
        if kul["rol"] not in kay["izinli_roller"]:
            return Kontrol("ROL_IZNI_YOK")
        # 8
        tur = self.turler[kay["tur"]]
        sertifika = tur.get("sertifika")
        if sertifika and sertifika not in kul["sertifikalar"]:
            return Kontrol("SERTIFIKA_YOK")
        # 9 (K2)
        for bakim in self.bakimlar:
            if bakim["kaynak"] == kaynak_id and kesisir(b, e, bakim["baslangic"], bakim["bitis"]):
                return Kontrol("BAKIM")
        # 10, 11 (K3)
        h = dk(tur.get("hazirlik_dk", 0))
        ayni_kaynak = [r for r in self.rezervasyonlar.values() if r.kaynak == kaynak_id]
        for r in ayni_kaynak:
            if r.durum in AKTIF_DURUMLAR and kesisir(b, e, r.baslangic, r.bitis):
                return Kontrol("KESISME")
        for r in ayni_kaynak:
            if r.durum in HAZIRLIK_DURUMLARI and kesisir(b, e + h, r.baslangic, r.bitis + h):
                return Kontrol("HAZIRLIK_IHLALI")
        # 12 (K4)
        a = dk(ARDISIK_BOSLUK_DK)
        for r in ayni_kaynak:
            if (r.kullanici == kullanici_id and r.durum in HAZIRLIK_DURUMLARI
                    and kesisir(b, e + a, r.baslangic, r.bitis + a)):
                return Kontrol("ARDISIK_KULLANIM")
        # 13 (K5, K6)
        ucret = self._ucret_hesapla(kay["tur"], b, e)
        if bakiye_kontrol and ucret > kul["bakiye"]:
            return Kontrol("BAKIYE_YETERSIZ", ucret, b, e)
        return Kontrol(None, ucret, b, e)

    def _ileri_gun(self, kul: dict) -> int:
        if kul["guvenilirlik"] < DUSUK_GUVENILIRLIK_SINIRI:
            return DUSUK_GUVENILIRLIK_ILERI_GUN
        return self.roller[kul["rol"]]["ileri_gun"]

    # ------------------------------------------------------------------
    # K5: Ücretlendirme
    # ------------------------------------------------------------------
    def _ucret_hesapla(self, tur_adi: str, b: datetime, e: datetime) -> int:
        tur = self.turler[tur_adi]
        temel = Fraction(str(tur["temel_ucret"]))
        enerji_yogun = bool(tur.get("enerji_yogun"))
        bant_carpanlari: dict[datetime, Fraction] = {}
        toplam = Fraction(0)
        an = b
        while an < e:
            bant_bas = self._bant_baslangici(an)
            if bant_bas not in bant_carpanlari:
                bant_carpanlari[bant_bas] = self._bant_carpani(tur_adi, bant_bas)
            pik = (PIK_CARPANI if enerji_yogun and PIK_BASLANGIC_SAAT <= an.hour < PIK_BITIS_SAAT
                   else Fraction(1))
            toplam += temel * Fraction(DILIM_DK, 60) * bant_carpanlari[bant_bas] * pik
            an += dk(DILIM_DK)
        return yuvarla(toplam)

    @staticmethod
    def _bant_baslangici(an: datetime) -> datetime:
        saat = CALISMA_BASLANGIC_SAAT + (an.hour - CALISMA_BASLANGIC_SAAT) // BANT_SAAT * BANT_SAAT
        return datetime(an.year, an.month, an.day, saat)

    def doluluk(self, tur_adi: str, bant_bas: datetime) -> Fraction:
        """Bir bantta aynı türdeki kaynakların dolu oranı (0..1)."""
        bant_bit = bant_bas + timedelta(hours=BANT_SAAT)
        kaynak_sayisi = sum(1 for k in self.kaynaklar.values() if k["tur"] == tur_adi)
        if kaynak_sayisi == 0:
            return Fraction(0)
        dolu_dk = 0
        for r in self.rezervasyonlar.values():
            if r.durum not in AKTIF_DURUMLAR or self.kaynaklar[r.kaynak]["tur"] != tur_adi:
                continue
            ortak = min(r.bitis, bant_bit) - max(r.baslangic, bant_bas)
            if ortak > timedelta(0):
                dolu_dk += ortak // dk(1)
        return Fraction(dolu_dk, kaynak_sayisi * BANT_SAAT * 60)

    def _bant_carpani(self, tur_adi: str, bant_bas: datetime) -> Fraction:
        oran = self.doluluk(tur_adi, bant_bas)
        return 1 + Fraction(1, 4) * math.floor(4 * oran)

    # ------------------------------------------------------------------
    # Ortak işlemler
    # ------------------------------------------------------------------
    def _rezervasyon_olustur(self, kullanici_id, kaynak_id, b, e, ucret, paket=None) -> Rezervasyon:
        self._r_sayac += 1
        r = Rezervasyon(f"r{self._r_sayac}", self._r_sayac, kullanici_id, kaynak_id,
                        b, e, ucret, ONAYLI, paket)
        self.rezervasyonlar[r.id] = r
        self.kullanicilar[kullanici_id]["bakiye"] -= ucret
        return r

    def _bakiye_ekle(self, kul: dict, miktar: int) -> int:
        """K6: İade bakiyeye eklenir ama kota aşılamaz. Gerçekte eklenen miktarı döndürür."""
        kota = self.roller[kul["rol"]]["haftalik_kota"]
        yeni = min(kota, kul["bakiye"] + miktar)
        eklenen = max(0, yeni - kul["bakiye"])
        kul["bakiye"] += eklenen
        return eklenen

    @staticmethod
    def _guvenilirlik_degistir(kul: dict, fark: int) -> None:
        kul["guvenilirlik"] = max(0, min(100, kul["guvenilirlik"] + fark))

    # ------------------------------------------------------------------
    # Komutlar
    # ------------------------------------------------------------------
    def rezervasyon(self, kullanici, kaynak, baslangic, bitis) -> dict:
        k = self._dogrula(kullanici, kaynak, baslangic, bitis)
        if k.kod:
            return _red("rezervasyon", k.kod)
        r = self._rezervasyon_olustur(kullanici, kaynak, k.baslangic, k.bitis, k.ucret)
        return _tamam("rezervasyon", rezervasyon_id=r.id, ucret=r.ucret,
                      bakiye=self.kullanicilar[kullanici]["bakiye"])

    def fiyat(self, kullanici, kaynak, baslangic, bitis) -> dict:
        k = self._dogrula(kullanici, kaynak, baslangic, bitis, bakiye_kontrol=False)
        if k.kod:
            return _red("fiyat", k.kod)
        return _tamam("fiyat", ucret=k.ucret)

    def paket(self, kullanici, kalemler) -> dict:
        """K7: Ya tüm kalemler alınır ya da hiçbiri."""
        kul = self.kullanicilar.get(kullanici)
        if kul is None:
            return _red("paket", "BULUNAMADI", kalemler=[])
        if not isinstance(kalemler, list) or not PAKET_EN_AZ <= len(kalemler) <= PAKET_EN_COK:
            return _red("paket", "PAKET_BOYUTU", kalemler=[])
        if kul["guvenilirlik"] < DUSUK_GUVENILIRLIK_SINIRI:
            return _red("paket", "GUVENILIRLIK_DUSUK", kalemler=[])

        # Her kalem, paketten önceki duruma göre ve bakiye hariç doğrulanır.
        kontroller = [
            self._dogrula(kullanici, kalem.get("kaynak"), kalem.get("baslangic"),
                          kalem.get("bitis"), bakiye_kontrol=False)
            if isinstance(kalem, dict) else Kontrol("BULUNAMADI")
            for kalem in kalemler
        ]
        if any(k.kod for k in kontroller):
            sonuclar = []
            for i, k in enumerate(kontroller):
                satir = {"sira": i, "durum": RED if k.kod else TAMAM}
                if k.kod:
                    satir["kod"] = k.kod
                sonuclar.append(satir)
            return _red("paket", "PAKET_RED", kalemler=sonuclar)

        hepsi_tamam = [{"sira": i, "durum": TAMAM} for i in range(len(kalemler))]
        if self._paket_ici_cakisma(kalemler, kontroller):
            return _red("paket", "PAKET_ICI_KESISME", kalemler=hepsi_tamam)

        toplam = sum(k.ucret for k in kontroller)
        if toplam > kul["bakiye"]:
            return _red("paket", "BAKIYE_YETERSIZ", kalemler=hepsi_tamam)

        self._p_sayac += 1
        paket_id = f"p{self._p_sayac}"
        olusan = [self._rezervasyon_olustur(kullanici, kalem["kaynak"], k.baslangic, k.bitis,
                                            k.ucret, paket_id)
                  for kalem, k in zip(kalemler, kontroller)]
        return _tamam("paket", paket_id=paket_id, rezervasyonlar=[r.id for r in olusan],
                      ucretler=[r.ucret for r in olusan], toplam=toplam, bakiye=kul["bakiye"])

    def _paket_ici_cakisma(self, kalemler: list, kontroller: list[Kontrol]) -> bool:
        """Aynı kaynaktaki kalemler kesişiyor, hazırlık veya art arda kuralını ihlal ediyor mu?"""
        a = dk(ARDISIK_BOSLUK_DK)
        for i in range(len(kalemler)):
            for j in range(i + 1, len(kalemler)):
                if kalemler[i]["kaynak"] != kalemler[j]["kaynak"]:
                    continue
                tur = self.turler[self.kaynaklar[kalemler[i]["kaynak"]]["tur"]]
                h = dk(tur.get("hazirlik_dk", 0))
                b1, e1 = kontroller[i].baslangic, kontroller[i].bitis
                b2, e2 = kontroller[j].baslangic, kontroller[j].bitis
                # Aynı kullanıcı olduğundan en geniş boşluk şartı yeterlidir;
                # üçü ayrı yazıldı ki kuralla birebir eşleşsin.
                if (kesisir(b1, e1, b2, e2) or kesisir(b1, e1 + h, b2, e2 + h)
                        or kesisir(b1, e1 + a, b2, e2 + a)):
                    return True
        return False

    def iptal(self, rezervasyon_id) -> dict:
        r = self.rezervasyonlar.get(rezervasyon_id)
        if r is None:
            return _red("iptal", "BULUNAMADI")
        if r.durum != ONAYLI:
            return _red("iptal", "DURUM_HATASI")
        kul = self.kullanicilar[r.kullanici]
        kalan = r.baslangic - self.saat
        if kalan >= timedelta(hours=TAM_IADE_SAAT):
            iade = r.ucret
        elif kalan >= timedelta(hours=YARIM_IADE_SAAT):
            iade = r.ucret // 2
        else:
            iade = 0
            self._guvenilirlik_degistir(kul, GUV_GEC_IPTAL)
        r.durum = IPTAL
        eklenen = self._bakiye_ekle(kul, iade)
        olaylar = self._bekleme_tara(r.kaynak)
        return _tamam("iptal", iade=eklenen, bakiye=kul["bakiye"],
                      guvenilirlik=kul["guvenilirlik"], olaylar=olaylar)

    def giris(self, rezervasyon_id) -> dict:
        r = self.rezervasyonlar.get(rezervasyon_id)
        if r is None:
            return _red("giris", "BULUNAMADI")
        if r.durum != ONAYLI:
            return _red("giris", "DURUM_HATASI")
        if not (r.baslangic - dk(GIRIS_ONCE_DK) <= self.saat <= r.baslangic + dk(GIRIS_SONRA_DK)):
            return _red("giris", "GIRIS_PENCERESI_DISI")
        r.durum = KULLANIMDA
        return _tamam("giris", yeni_durum=KULLANIMDA)

    def cikis(self, rezervasyon_id) -> dict:
        r = self.rezervasyonlar.get(rezervasyon_id)
        if r is None:
            return _red("cikis", "BULUNAMADI")
        if r.durum != KULLANIMDA:
            return _red("cikis", "DURUM_HATASI")
        kul = self.kullanicilar[r.kullanici]
        # Erken çıkış: bitiş çıkış saati olur, iade yok, güvenilirlik değişmez.
        if self.saat < r.bitis:
            r.bitis = max(self.saat, r.baslangic)
        r.durum = TAMAMLANDI
        olaylar = self._bekleme_tara(r.kaynak)
        return _tamam("cikis", yeni_durum=TAMAMLANDI, guvenilirlik=kul["guvenilirlik"],
                      olaylar=olaylar)

    def bekleme(self, kullanici, kaynak, baslangic, bitis) -> dict:
        """K9: Yalnızca KESISME veya HAZIRLIK_IHLALI ile reddedilen talep için açılır."""
        k = self._dogrula(kullanici, kaynak, baslangic, bitis, bakiye_kontrol=False)
        if k.kod is None:
            return _red("bekleme", "BEKLEME_GEREKSIZ")
        if k.kod not in ("KESISME", "HAZIRLIK_IHLALI"):
            return _red("bekleme", k.kod)
        self._b_sayac += 1
        kayit = BeklemeKaydi(f"b{self._b_sayac}", self._b_sayac, kullanici, kaynak,
                             zaman_coz(baslangic), zaman_coz(bitis), self.saat)
        self.beklemeler[kayit.id] = kayit
        sira = [x.id for x in self.kaynak_beklemeleri(kaynak)].index(kayit.id) + 1
        return _tamam("bekleme", bekleme_id=kayit.id, sira=sira)

    def sorgu(self, tur, id, gun=None) -> dict:
        if tur == "kullanici":
            kul = self.kullanicilar.get(id)
            if kul is None:
                return _red("sorgu", "BULUNAMADI")
            liste = sorted((r for r in self.rezervasyonlar.values() if r.kullanici == id),
                           key=lambda r: (r.baslangic, r.no))
            return _tamam("sorgu", bakiye=kul["bakiye"], guvenilirlik=kul["guvenilirlik"],
                          rezervasyonlar=[{
                              "id": r.id, "kaynak": r.kaynak,
                              "baslangic": zaman_yaz(r.baslangic), "bitis": zaman_yaz(r.bitis),
                              "durum": r.durum, "ucret": r.ucret,
                          } for r in liste])
        if tur == "kaynak":
            if id not in self.kaynaklar:
                return _red("sorgu", "BULUNAMADI")
            try:
                gun_basi = datetime.strptime(gun, GUN_BICIMI)
            except (TypeError, ValueError):
                return _red("sorgu", "GECERSIZ_DEGER")
            gun_sonu = gun_basi + timedelta(days=1)
            satirlar = []
            for b in self.bakimlar:
                if b["kaynak"] == id and kesisir(b["baslangic"], b["bitis"], gun_basi, gun_sonu):
                    satirlar.append(((b["baslangic"], 0, 0), {
                        "baslangic": zaman_yaz(b["baslangic"]), "bitis": zaman_yaz(b["bitis"]),
                        "tur": "BAKIM"}))
            for r in self.rezervasyonlar.values():
                if (r.kaynak == id and r.durum in AKTIF_DURUMLAR
                        and kesisir(r.baslangic, r.bitis, gun_basi, gun_sonu)):
                    satirlar.append(((r.baslangic, 1, r.no), {
                        "baslangic": zaman_yaz(r.baslangic), "bitis": zaman_yaz(r.bitis),
                        "tur": "REZERVASYON", "rezervasyon": r.id}))
            satirlar.sort(key=lambda s: s[0])
            return _tamam("sorgu", doluluk=[s[1] for s in satirlar])
        return _red("sorgu", "TANIMSIZ_DEGER")

    def kullanici_ekle(self, id, ad, rol, sertifikalar, bakiye, guvenilirlik) -> dict:
        if id in self.kullanicilar:
            return _red("kullanici_ekle", "ID_MEVCUT")
        if rol not in self.roller:
            return _red("kullanici_ekle", "TANIMSIZ_DEGER")
        kota = self.roller[rol]["haftalik_kota"]
        if not sayi_mi(bakiye) or bakiye < 0 or bakiye > kota:
            return _red("kullanici_ekle", "GECERSIZ_DEGER")
        if not tam_sayi_mi(guvenilirlik) or not 0 <= guvenilirlik <= 100:
            return _red("kullanici_ekle", "GECERSIZ_DEGER")
        self.kullanicilar[id] = {
            "id": id, "ad": ad or id, "rol": rol, "sertifikalar": list(sertifikalar or []),
            "bakiye": bakiye, "guvenilirlik": int(guvenilirlik),
        }
        return _tamam("kullanici_ekle")

    def kaynak_ekle(self, id, ad, tur, izinli_roller) -> dict:
        if id in self.kaynaklar:
            return _red("kaynak_ekle", "ID_MEVCUT")
        roller = izinli_roller if isinstance(izinli_roller, list) else [izinli_roller]
        if tur not in self.turler or any(r not in self.roller for r in roller):
            return _red("kaynak_ekle", "TANIMSIZ_DEGER")
        self.kaynaklar[id] = {"id": id, "ad": ad or id, "tur": tur, "izinli_roller": list(roller)}
        return _tamam("kaynak_ekle")

    # ------------------------------------------------------------------
    # K11: Saat ilerletme ve olaylar
    # ------------------------------------------------------------------
    def saat_ilerlet(self, zaman) -> dict:
        try:
            yeni = zaman_coz(zaman)
        except ValueError:
            return _red("saat", "GECERSIZ_DEGER")
        if yeni < self.saat:
            return _red("saat", "SAAT_GERI")
        olaylar = []
        while True:
            pazartesi = self._sonraki_pazartesi(self.saat)
            adaylar = [pazartesi]
            adaylar += [r.bitis for r in self.rezervasyonlar.values() if r.durum == KULLANIMDA]
            adaylar += [r.baslangic + dk(GIRIS_SONRA_DK)
                        for r in self.rezervasyonlar.values() if r.durum == ONAYLI]
            t = min(adaylar)
            if t > yeni:
                break
            self.saat = max(self.saat, t)
            olaylar += self._olaylari_isle(sifirla=(t == pazartesi))
        self.saat = yeni
        self._eski_beklemeleri_sil()
        return _tamam("saat", olaylar=olaylar)

    @staticmethod
    def _sonraki_pazartesi(an: datetime) -> datetime:
        """an'dan kesinlikle sonraki ilk Pazartesi 00:00."""
        gun_basi = datetime(an.year, an.month, an.day)
        aday = gun_basi + timedelta(days=(7 - an.weekday()) % 7)
        if aday <= an:
            aday += timedelta(days=7)
        return aday

    def _olaylari_isle(self, sifirla: bool) -> list[dict]:
        """Şu anki saatte gerçekleşen olayları K11'deki sırayla işler."""
        t = self.saat
        olaylar = []
        self._eski_beklemeleri_sil()
        # 1. Haftalık sıfırlama
        if sifirla:
            for kul in self.kullanicilar.values():
                kul["bakiye"] = self.roller[kul["rol"]]["haftalik_kota"]
            olaylar.append({"zaman": zaman_yaz(t), "tur": "HAFTALIK_SIFIRLAMA"})
        sirali = sorted(self.rezervasyonlar.values(), key=lambda r: r.no)
        # 2. Bitiş saatinde tamamlananlar
        for r in sirali:
            if r.durum == KULLANIMDA and r.bitis <= t:
                r.durum = TAMAMLANDI
                kul = self.kullanicilar[r.kullanici]
                self._guvenilirlik_degistir(kul, GUV_ZAMANINDA_TAMAMLANDI)
                olaylar.append({"zaman": zaman_yaz(r.bitis), "tur": TAMAMLANDI,
                                "rezervasyon": r.id, "kullanici": r.kullanici,
                                "guvenilirlik": kul["guvenilirlik"]})
        # 3. Gelmeyenler
        bosalan: list[str] = []
        for r in sirali:
            if r.durum == ONAYLI and r.baslangic + dk(GIRIS_SONRA_DK) <= t:
                r.durum = GELMEDI
                kul = self.kullanicilar[r.kullanici]
                self._guvenilirlik_degistir(kul, GUV_GELMEDI)
                olaylar.append({"zaman": zaman_yaz(r.baslangic + dk(GIRIS_SONRA_DK)),
                                "tur": GELMEDI, "rezervasyon": r.id, "kullanici": r.kullanici,
                                "guvenilirlik": kul["guvenilirlik"]})
                if r.kaynak not in bosalan:
                    bosalan.append(r.kaynak)
        # 4. Boşalan kaynaklar için bekleme listesi taraması
        for kaynak_id in bosalan:
            olaylar += self._bekleme_tara(kaynak_id)
        return olaylar

    # ------------------------------------------------------------------
    # K9: Bekleme listesi
    # ------------------------------------------------------------------
    def kaynak_beklemeleri(self, kaynak_id) -> list[BeklemeKaydi]:
        """Bir kaynağın bekleme listesi, öncelik sırasıyla."""
        return sorted((b for b in self.beklemeler.values() if b.kaynak == kaynak_id),
                      key=lambda b: (-self.kullanicilar[b.kullanici]["guvenilirlik"],
                                     b.kayit_saati, b.no))

    def kullanici_beklemeleri(self, kullanici_id) -> list[BeklemeKaydi]:
        return sorted((b for b in self.beklemeler.values() if b.kullanici == kullanici_id),
                      key=lambda b: (b.baslangic, b.no))

    def _bekleme_tara(self, kaynak_id) -> list[dict]:
        olaylar = []
        for kayit in self.kaynak_beklemeleri(kaynak_id):
            k = self._dogrula(kayit.kullanici, kayit.kaynak, kayit.baslangic, kayit.bitis)
            if k.kod:
                continue  # geçemeyen kayıt listede kalır
            r = self._rezervasyon_olustur(kayit.kullanici, kayit.kaynak, k.baslangic,
                                          k.bitis, k.ucret)
            del self.beklemeler[kayit.id]
            olaylar.append({"zaman": zaman_yaz(self.saat), "tur": "OTOMATIK_ATAMA",
                            "bekleme": kayit.id, "rezervasyon": r.id,
                            "kullanici": kayit.kullanici, "ucret": r.ucret,
                            "bakiye": self.kullanicilar[kayit.kullanici]["bakiye"]})
        return olaylar

    def _eski_beklemeleri_sil(self) -> None:
        for kayit in list(self.beklemeler.values()):
            if kayit.baslangic < self.saat:
                del self.beklemeler[kayit.id]

    # ------------------------------------------------------------------
    # Arayüz için salt okunur yardımcılar (durum değiştirmez, kural içermez)
    # ------------------------------------------------------------------
    def hazirlik_araliklari(self, kaynak_id, gun: date) -> list[tuple[datetime, datetime]]:
        """Takvimde gösterilecek hazırlık süreleri: K3'te sayılan rezervasyonların ardından."""
        h = dk(self.turler[self.kaynaklar[kaynak_id]["tur"]].get("hazirlik_dk", 0))
        if h <= timedelta(0):
            return []
        return [(r.bitis, r.bitis + h) for r in self.rezervasyonlar.values()
                if r.kaynak == kaynak_id and r.durum in HAZIRLIK_DURUMLARI
                and r.baslangic.date() == gun]

    def sertifika_listesi(self) -> list[str]:
        """Başlangıç dosyasında geçen bütün sertifikalar."""
        kume = {t["sertifika"] for t in self.turler.values() if t.get("sertifika")}
        for u in self.kullanicilar.values():
            kume.update(u["sertifikalar"])
        return sorted(kume)
