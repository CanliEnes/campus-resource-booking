"""Arayüz ile modül arasındaki ince katman.

Her ekran işlemi burada modülün ilgili fonksiyonunu çağırır, komutu ve dönen
sonucu olay günlüğüne yazar ve ekranların yenilenmesi için sinyal yayar.
Burada hiçbir iş kuralı yoktur; kararları her zaman modül verir.
"""
from PySide6.QtCore import QObject, Signal

from rezervasyon import RezervasyonSistemi


class Oturum(QObject):
    yuklendi = Signal()        # yeni başlangıç dosyası yüklendi
    degisti = Signal()         # modülün durumu değişti -> takvim, panel, saat yenilensin
    gunluk_eklendi = Signal()  # olay günlüğüne satır eklendi / güncellendi

    def __init__(self):
        super().__init__()
        self.sistem: RezervasyonSistemi | None = None
        self.dosya: str | None = None
        self.gunluk: list[dict] = []
        self._no = 0

    def yukle(self, yol: str) -> None:
        self.sistem = RezervasyonSistemi.dosyadan(yol)
        self.dosya = yol
        self.gunluk = []
        self._no = 0
        self.yuklendi.emit()
        self.degisti.emit()
        self.gunluk_eklendi.emit()

    # ------------------------------------------------------------------
    def _kaydet(self, komut: dict, sonuc: dict, onizleme: str | None = None) -> None:
        """Günlüğe yazar. Fiyat önizlemeleri, arka arkaya geldiklerinde aynı form
        satırının eski önizlemesinin yerine geçer (günlük her tuşta dolmasın)."""
        if onizleme:
            for kayit in reversed(self.gunluk):
                if not kayit.get("onizleme"):
                    break
                if kayit["onizleme"] == onizleme:
                    kayit["komut"], kayit["sonuc"] = komut, {"no": kayit["no"], **sonuc}
                    self.gunluk_eklendi.emit()
                    return
        self._no += 1
        self.gunluk.append({"no": self._no, "komut": komut, "sonuc": {"no": self._no, **sonuc},
                            "onizleme": onizleme})
        self.gunluk_eklendi.emit()

    def _calistir(self, komut: dict, fonksiyon, *args) -> dict:
        sonuc = fonksiyon(*args)
        self._kaydet(komut, sonuc)
        if sonuc["durum"] == "TAMAM" and komut["komut"] not in ("fiyat", "sorgu"):
            self.degisti.emit()
        return sonuc

    # ------------------------------------------------------------------
    # Bölüm 5'teki her komutun karşılığı
    # ------------------------------------------------------------------
    def rezervasyon(self, kullanici, kaynak, baslangic, bitis) -> dict:
        return self._calistir({"komut": "rezervasyon", "kullanici": kullanici, "kaynak": kaynak,
                               "baslangic": baslangic, "bitis": bitis},
                              self.sistem.rezervasyon, kullanici, kaynak, baslangic, bitis)

    def fiyat(self, kullanici, kaynak, baslangic, bitis, onizleme: str | None = None) -> dict:
        komut = {"komut": "fiyat", "kullanici": kullanici, "kaynak": kaynak,
                 "baslangic": baslangic, "bitis": bitis}
        sonuc = self.sistem.fiyat(kullanici, kaynak, baslangic, bitis)
        self._kaydet(komut, sonuc, onizleme)
        return sonuc

    def paket(self, kullanici, kalemler: list[dict]) -> dict:
        return self._calistir({"komut": "paket", "kullanici": kullanici, "kalemler": kalemler},
                              self.sistem.paket, kullanici, kalemler)

    def iptal(self, rezervasyon_id) -> dict:
        return self._calistir({"komut": "iptal", "rezervasyon": rezervasyon_id},
                              self.sistem.iptal, rezervasyon_id)

    def giris(self, rezervasyon_id) -> dict:
        return self._calistir({"komut": "giris", "rezervasyon": rezervasyon_id},
                              self.sistem.giris, rezervasyon_id)

    def cikis(self, rezervasyon_id) -> dict:
        return self._calistir({"komut": "cikis", "rezervasyon": rezervasyon_id},
                              self.sistem.cikis, rezervasyon_id)

    def bekleme(self, kullanici, kaynak, baslangic, bitis) -> dict:
        return self._calistir({"komut": "bekleme", "kullanici": kullanici, "kaynak": kaynak,
                               "baslangic": baslangic, "bitis": bitis},
                              self.sistem.bekleme, kullanici, kaynak, baslangic, bitis)

    def saat(self, zaman) -> dict:
        return self._calistir({"komut": "saat", "zaman": zaman}, self.sistem.saat_ilerlet, zaman)

    def kullanici_ekle(self, id, ad, rol, sertifikalar, bakiye, guvenilirlik) -> dict:
        return self._calistir({"komut": "kullanici_ekle", "id": id, "ad": ad, "rol": rol,
                               "sertifikalar": sertifikalar, "bakiye": bakiye,
                               "guvenilirlik": guvenilirlik},
                              self.sistem.kullanici_ekle, id, ad, rol, sertifikalar, bakiye,
                              guvenilirlik)

    def kaynak_ekle(self, id, ad, tur, izinli_roller) -> dict:
        return self._calistir({"komut": "kaynak_ekle", "id": id, "ad": ad, "tur": tur,
                               "izinli_roller": izinli_roller},
                              self.sistem.kaynak_ekle, id, ad, tur, izinli_roller)

    def sorgu_kullanici(self, kullanici_id) -> dict:
        return self._calistir({"komut": "sorgu", "tur": "kullanici", "id": kullanici_id},
                              self.sistem.sorgu, "kullanici", kullanici_id)
