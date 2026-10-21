"""Ekran parçaları: kullanıcı paneli, talep formu, seçili rezervasyon kartı,
olay günlüğü ve ekleme pencereleri.

Hiçbiri bir talebi kendi başına engellemez; her işlem modüle gönderilir ve
modülün verdiği sonuç gösterilir.
"""
import json
import re
from datetime import datetime

from PySide6.QtCore import QDate, QEasingCurve, QEvent, QPropertyAnimation, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDateEdit, QDialog,
                               QFormLayout, QFrame, QGraphicsOpacityEffect, QGridLayout,
                               QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMenu,
                               QPlainTextEdit, QProgressBar, QPushButton, QSizePolicy, QSpinBox,
                               QSplitter, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout,
                               QWidget)

from rezervasyon.mesajlar import aciklama
from . import tema
from .stil import DURUM_AD, aralik_metni, olaylar_html, saat_metni, sonuc_ozeti

SAATLER = [f"{h:02d}:{m:02d}" for h in range(8, 23) for m in (0, 15, 30, 45) if h < 22 or m == 0]

# Tema değişince ikonları yeniden boyamak için: (düğme, ikon adı, renk anahtarı)
_IKONLU: list = []


def ikonla(dugme, ad: str, renk_anahtari: str = "yazi2"):
    dugme.setIcon(tema.ikon(ad, renk_anahtari))
    _IKONLU.append((dugme, ad, renk_anahtari))
    return dugme


def ikonlari_yenile():
    for kayit in list(_IKONLU):
        dugme, ad, renk_anahtari = kayit
        try:
            dugme.setIcon(tema.ikon(ad, renk_anahtari))
        except RuntimeError:  # pencere kapanmış
            _IKONLU.remove(kayit)


def ozellik(w, ad: str, deger) -> None:
    """Stil sayfasındaki [tur="..."] gibi seçiciler için özellik atar."""
    if w.property(ad) != deger:
        w.setProperty(ad, deger)
        tema.yeniden_cilala(w)


def belir(w, sure: int = 180) -> None:
    """Sonuçlar bir anda değil, kısa bir solmayla belirir (animasyon açıksa)."""
    if not tema.yonetici.animasyon:
        return
    efekt = QGraphicsOpacityEffect(w)
    w.setGraphicsEffect(efekt)
    anim = QPropertyAnimation(efekt, b"opacity", w)
    anim.setDuration(sure)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.finished.connect(lambda: w.setGraphicsEffect(None))
    anim.start(QPropertyAnimation.DeleteWhenStopped)


def bolum_basligi(metin: str) -> QLabel:
    etiket = QLabel(metin)
    etiket.setObjectName("bolumBaslik")
    return etiket


def ikincil(metin: str = "", ad: str = "ikincil") -> QLabel:
    etiket = QLabel(metin)
    etiket.setObjectName(ad)
    return etiket


def zaman_birlestir(gun: QDate, metin: str) -> str:
    """Seçilen gün ve yazılan saati modülün zaman biçimine çevirir.
    Saat hatalıysa olduğu gibi gönderilir; reddi modül verir."""
    metin = metin.strip()
    m = re.fullmatch(r"(\d{1,2})[:.](\d{2})", metin)
    if m:
        metin = f"{int(m[1]):02d}:{m[2]}"
    return f"{gun.toString('yyyy-MM-dd')}T{metin}"


class SaatKutusu(QComboBox):
    """15 dakikalık adımlardan seçilir; istenirse elle başka saat de yazılabilir."""

    def __init__(self, varsayilan: str):
        super().__init__()
        self.setEditable(True)
        self.addItems(SAATLER)
        self.setMaxVisibleItems(14)
        self.setCurrentText(varsayilan)
        self.setMinimumWidth(84)


class GunKutusu(QDateEdit):
    def __init__(self):
        super().__init__()
        self.setCalendarPopup(True)
        self.setDisplayFormat("dd.MM.yyyy ddd")
        self.setMinimumWidth(128)
        self.calendarWidget().setGridVisible(False)
        self.calendarWidget().setVerticalHeaderFormat(self.calendarWidget().VerticalHeaderFormat.NoVerticalHeader)


def tablo(basliklar, esnek: int = 2) -> QTableWidget:
    t = QTableWidget(0, len(basliklar))
    t.setHorizontalHeaderLabels(basliklar)
    t.verticalHeader().hide()
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setSelectionMode(QAbstractItemView.SingleSelection)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setShowGrid(False)
    t.setFocusPolicy(Qt.NoFocus)
    t.verticalHeader().setDefaultSectionSize(26)
    t.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    t.setWordWrap(False)
    baslik = t.horizontalHeader()
    baslik.setHighlightSections(False)
    baslik.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    baslik.setSectionResizeMode(QHeaderView.ResizeToContents)
    baslik.setSectionResizeMode(esnek, QHeaderView.Stretch)
    return t


def durum_rengi(durum: str) -> QColor:
    t = tema.aktif()
    if durum == "ONAYLI":
        return QColor(t["vurgu_yazi"])
    if durum == "KULLANIMDA":
        return QColor(t["basari"])
    if durum == "TAMAMLANDI":
        return QColor(t["yazi3"])
    return QColor(t["durum"].get(durum, ("", "", t["yazi"]))[2])


# ---------------------------------------------------------------------------
# Sonuç kutusu: işlemin sonucu yapıldığı yerin hemen altında
# ---------------------------------------------------------------------------
class SonucKutusu(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("sonucKutusu")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(8)
        self.ikon = QLabel()
        self.ikon.setFixedSize(18, 18)
        lay.addWidget(self.ikon, 0, Qt.AlignTop)
        sag = QVBoxLayout()
        sag.setSpacing(2)
        self.baslik = QLabel()
        self.baslik.setObjectName("sonucBaslik")
        self.baslik.setWordWrap(True)
        self.metin = QLabel()
        self.metin.setObjectName("sonucMetin")
        self.metin.setWordWrap(True)
        self.metin.setTextFormat(Qt.RichText)
        sag.addWidget(self.baslik)
        sag.addWidget(self.metin)
        self.dugme = QPushButton()
        self.dugme.setObjectName("kucuk")
        ikonla(self.dugme, "kum", "vurgu_yazi")
        self.dugme.hide()
        sag.addWidget(self.dugme, 0, Qt.AlignLeft)
        lay.addLayout(sag, 1)
        self._tur = "bilgi"
        self._baglanti = None
        tema.yonetici.degisti.connect(self._ikon_ciz)
        self.hide()

    def _ikon_ciz(self):
        ad, renk = {"tamam": ("tamam", "basari"), "hata": ("hata", "hata")}.get(self._tur, ("bilgi", "vurgu"))
        self.ikon.setPixmap(tema.ikon_pixmap(ad, tema.aktif()[renk], 18))

    def goster(self, tur: str, baslik: str, metin: str = "", dugme: tuple | None = None):
        self._tur = tur
        ozellik(self, "tur", tur)
        self._ikon_ciz()
        self.baslik.setText(baslik)
        self.metin.setText(metin)
        self.metin.setVisible(bool(metin))
        if self._baglanti is not None:
            self.dugme.clicked.disconnect(self._baglanti)
            self._baglanti = None
        if dugme:
            self.dugme.setText(dugme[0])
            self._baglanti = dugme[1]
            self.dugme.clicked.connect(self._baglanti)
            self.dugme.show()
        else:
            self.dugme.hide()
        self.show()
        belir(self)

    def hata(self, kod: str, dugme: tuple | None = None):
        self.goster("hata", kod, aciklama(kod), dugme)

    def temizle(self):
        self.hide()


# ---------------------------------------------------------------------------
# Kullanıcı paneli
# ---------------------------------------------------------------------------
class SayacEtiket(QLabel):
    """Sayı değişince eski değerden yenisine kısa sürede sayarak geçer."""

    def __init__(self):
        super().__init__("—")
        self.setObjectName("buyukDeger")
        self._deger = None
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(420)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(lambda v: self.setText(str(int(round(v)))))

    def ayarla(self, deger, animasyonlu: bool):
        if animasyonlu and tema.yonetici.animasyon and self._deger is not None and self._deger != deger:
            self._anim.stop()
            self._anim.setStartValue(float(self._deger))
            self._anim.setEndValue(float(deger))
            self._anim.start()
        else:
            self._anim.stop()
            self.setText(str(deger))
        self._deger = deger


class AkiciCubuk(QProgressBar):
    def __init__(self):
        super().__init__()
        self.setTextVisible(False)
        self._anim = QPropertyAnimation(self, b"value", self)
        self._anim.setDuration(450)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def ayarla(self, deger: int, animasyonlu: bool):
        if animasyonlu and tema.yonetici.animasyon:
            self._anim.stop()
            self._anim.setStartValue(self.value())
            self._anim.setEndValue(deger)
            self._anim.start()
        else:
            self._anim.stop()
            self.setValue(deger)


class KullaniciPaneli(QFrame):
    kullanici_degisti = Signal(str)
    rezervasyon_secildi = Signal(str)
    eylem_istendi = Signal(str, str)
    yeni_uye_istendi = Signal()

    def __init__(self, oturum):
        super().__init__()
        self.oturum = oturum
        self.setObjectName("panel")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)

        ust = QHBoxLayout()
        ust.addWidget(bolum_basligi("Kullanıcı"))
        ust.addStretch()
        yeni = ikonla(QPushButton("Yeni üye"), "uye")
        yeni.setObjectName("hayalet")
        yeni.clicked.connect(self.yeni_uye_istendi)
        ust.addWidget(yeni)
        lay.addLayout(ust)

        self.secim = QComboBox()
        self.secim.currentIndexChanged.connect(self._secim_degisti)
        self.secim.activated.connect(self._elle_secildi)
        lay.addWidget(self.secim)

        self.bilgi = ikincil()
        self.bilgi.setWordWrap(True)
        lay.addWidget(self.bilgi)

        izgara = QGridLayout()
        izgara.setHorizontalSpacing(18)
        izgara.setVerticalSpacing(3)
        self.bakiye = SayacEtiket()
        self.guven = SayacEtiket()
        self.bakiye_birim = ikincil("", "birim")
        self.guven_birim = ikincil("/ 100", "birim")
        for sutun, (ad, deger, birim) in enumerate((("Bakiye", self.bakiye, self.bakiye_birim),
                                                    ("Güvenilirlik", self.guven, self.guven_birim))):
            izgara.addWidget(ikincil(ad, "etiket"), 0, sutun)
            satir = QHBoxLayout()
            satir.setSpacing(4)
            satir.addWidget(deger, 0, Qt.AlignBottom)
            satir.addWidget(birim, 0, Qt.AlignBottom)
            satir.addStretch()
            izgara.addLayout(satir, 1, sutun)
        self.bakiye_cubuk = AkiciCubuk()
        self.guven_cubuk = AkiciCubuk()
        self.guven_cubuk.setRange(0, 100)
        izgara.addWidget(self.bakiye_cubuk, 2, 0)
        izgara.addWidget(self.guven_cubuk, 2, 1)
        lay.addLayout(izgara)

        lay.addSpacing(6)
        lay.addWidget(bolum_basligi("Rezervasyonlar"))
        self.tablo = tablo(["No", "Kaynak", "Zaman", "KP", "Durum"])
        self.tablo.itemSelectionChanged.connect(self._satir_secildi)
        self.tablo.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tablo.customContextMenuRequested.connect(self._menu)
        self.tablo_bos = ikincil("Henüz rezervasyon yok. Takvimde boş bir alana sürükleyerek başlayın.")
        self.tablo_bos.setWordWrap(True)
        lay.addWidget(self.tablo, 3)
        lay.addWidget(self.tablo_bos)

        lay.addSpacing(4)
        lay.addWidget(bolum_basligi("Bekleme kayıtları"))
        self.bekleme_tablo = tablo(["No", "Kaynak", "Zaman", "Sıra"])
        self.bekleme_bos = ikincil("Bekleme kaydı yok. Dolu bir aralık reddedilince form size bekleme önerir.")
        self.bekleme_bos.setWordWrap(True)
        lay.addWidget(self.bekleme_tablo, 1)
        lay.addWidget(self.bekleme_bos)
        lay.addStretch(0)
        self._yukleniyor = False
        self._gosterilen = None

    @property
    def kullanici_id(self) -> str | None:
        return self.secim.currentData()

    def kullanicilari_yenile(self, secilecek: str | None = None):
        s = self.oturum.sistem
        onceki = secilecek or self.kullanici_id
        self._yukleniyor = True
        self.secim.clear()
        for u in s.kullanicilar.values():
            self.secim.addItem(f"{u['id']} — {u['ad']}  ·  {u['rol']}", u["id"])
        indeks = self.secim.findData(onceki)
        self.secim.setCurrentIndex(indeks if indeks >= 0 else 0)
        self._yukleniyor = False
        self._secim_degisti()

    def _elle_secildi(self, _):
        # Listeden elle seçmek "sorgu kullanici" komutunun karşılığıdır; günlüğe yazılır.
        if self.kullanici_id:
            self.oturum.sorgu_kullanici(self.kullanici_id)

    def _secim_degisti(self):
        if self._yukleniyor:
            return
        self.yenile()
        if self.kullanici_id:
            self.kullanici_degisti.emit(self.kullanici_id)

    def yenile(self):
        s = self.oturum.sistem
        if s and [self.secim.itemData(i) for i in range(self.secim.count())] != list(s.kullanicilar):
            self.kullanicilari_yenile()   # üye eklenmiş: liste hemen güncellensin
            return
        kul = s.kullanicilar.get(self.kullanici_id) if s else None
        self.tablo.setRowCount(0)
        self.bekleme_tablo.setRowCount(0)
        if kul is None:
            return
        ayni = self._gosterilen == kul["id"]
        self._gosterilen = kul["id"]
        rol = s.roller[kul["rol"]]
        sertifika = ", ".join(kul["sertifikalar"]) or "yok"
        self.bilgi.setText(f"{kul['rol']}  ·  Sertifika: {sertifika}  ·  En uzun {rol['azami_sure_dk']} dk  ·  "
                           f"{rol['ileri_gun']} gün ileri")
        self.bakiye.ayarla(kul["bakiye"], ayni)
        self.bakiye_birim.setText(f"/ {rol['haftalik_kota']} KP")
        self.bakiye_cubuk.setRange(0, max(1, int(rol["haftalik_kota"])))
        self.bakiye_cubuk.ayarla(int(kul["bakiye"]), ayni)
        self.guven.ayarla(kul["guvenilirlik"], ayni)
        ozellik(self.guven_cubuk, "tur", "dusuk" if kul["guvenilirlik"] < 50 else "iyi")
        self.guven_cubuk.ayarla(kul["guvenilirlik"], ayni)

        # Liste ve sıralama modülün sorgu sonucundan gelir.
        rezler = s.sorgu("kullanici", kul["id"])["rezervasyonlar"]
        for r in rezler:
            satir = self.tablo.rowCount()
            self.tablo.insertRow(satir)
            b, e = datetime.fromisoformat(r["baslangic"]), datetime.fromisoformat(r["bitis"])
            degerler = [r["id"], r["kaynak"], self._zaman(b, e), str(r["ucret"]),
                        DURUM_AD.get(r["durum"], r["durum"])]
            for sutun, deger in enumerate(degerler):
                hucre = QTableWidgetItem(deger)
                hucre.setData(Qt.UserRole, r["id"])
                if sutun == 4:
                    hucre.setForeground(durum_rengi(r["durum"]))
                if sutun == 3:
                    hucre.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.tablo.setItem(satir, sutun, hucre)
        self.tablo.setVisible(bool(rezler))
        self.tablo_bos.setVisible(not rezler)

        beklemeler = s.kullanici_beklemeleri(kul["id"])
        for b in beklemeler:
            satir = self.bekleme_tablo.rowCount()
            self.bekleme_tablo.insertRow(satir)
            sira = [x.id for x in s.kaynak_beklemeleri(b.kaynak)].index(b.id) + 1
            for sutun, deger in enumerate([b.id, b.kaynak, self._zaman(b.baslangic, b.bitis), str(sira)]):
                self.bekleme_tablo.setItem(satir, sutun, QTableWidgetItem(deger))
        self.bekleme_tablo.setVisible(bool(beklemeler))
        self.bekleme_tablo.setMaximumHeight(30 + 26 * max(1, len(beklemeler)))
        self.bekleme_bos.setVisible(not beklemeler)

    def _zaman(self, b: datetime, e: datetime) -> str:
        """Simüle gündeki kayıtlarda yalnızca saat; başka günlerde tarih de yazılır."""
        if b.date() == self.oturum.sistem.saat.date():
            return f"{saat_metni(b)}–{saat_metni(e)}"
        return aralik_metni(b, e)

    def rezervasyonu_sec(self, rid: str | None):
        self.tablo.blockSignals(True)
        self.tablo.clearSelection()
        for satir in range(self.tablo.rowCount()):
            if self.tablo.item(satir, 0).text() == rid:
                self.tablo.selectRow(satir)
                break
        self.tablo.blockSignals(False)

    def _satir_secildi(self):
        hucreler = self.tablo.selectedItems()
        if hucreler:
            self.rezervasyon_secildi.emit(hucreler[0].data(Qt.UserRole))

    def _menu(self, konum):
        hucre = self.tablo.itemAt(konum)
        if not hucre:
            return
        rid = hucre.data(Qt.UserRole)
        menu = QMenu(self)
        for eylem, ad in (("giris", "Giriş yap"), ("cikis", "Çıkış yap"), ("iptal", "İptal et")):
            menu.addAction(tema.ikon(eylem), ad, lambda e=eylem: self.eylem_istendi.emit(e, rid))
        menu.exec(self.tablo.viewport().mapToGlobal(konum))


# ---------------------------------------------------------------------------
# Seçili rezervasyon kartı (takvimin altında): ayrıntılar + giriş/çıkış/iptal
# ---------------------------------------------------------------------------
class SeciliKart(QFrame):
    # Durumdaki olası sonraki adım vurgulanır; diğer düğmeler de basılabilir
    # (karar modülündedir, arayüz engellemez).
    ONERILEN = {"ONAYLI": "giris", "KULLANIMDA": "cikis"}

    def __init__(self, oturum):
        super().__init__()
        self.oturum = oturum
        self.rid: str | None = None
        self.setObjectName("panel")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(10)
        sol = QVBoxLayout()
        sol.setSpacing(3)
        ust = QHBoxLayout()
        ust.setSpacing(8)
        self.baslik = QLabel()
        self.baslik.setObjectName("bolumBaslik")
        self.hap = QLabel()
        self.hap.setObjectName("durumHap")
        self.paket = ikincil()
        ust.addWidget(self.baslik)
        ust.addWidget(self.hap)
        ust.addWidget(self.paket)
        ust.addStretch()
        sol.addLayout(ust)
        self.ayrinti = ikincil("", "etiket")
        self.ayrinti.setWordWrap(True)
        sol.addWidget(self.ayrinti)
        lay.addLayout(sol, 1)
        self.dugmeler: dict[str, QPushButton] = {}
        for eylem, ad in (("giris", "Giriş"), ("cikis", "Çıkış"), ("iptal", "İptal")):
            d = QPushButton(ad)
            d.clicked.connect(lambda _=False, e=eylem: self.eylem(e))
            lay.addWidget(d, 0, Qt.AlignVCenter)
            self.dugmeler[eylem] = d
        self.sonuc = SonucKutusu()
        self.sonuc.setMinimumWidth(300)
        self.sonuc.setMaximumWidth(460)
        self.sonuc.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        lay.addWidget(self.sonuc, 1)
        tema.yonetici.degisti.connect(lambda: self.goster(self.rid, sonucu_koru=True))
        self.goster(None)

    def goster(self, rid: str | None, sonucu_koru: bool = False):
        self.rid = rid
        s = self.oturum.sistem
        r = s.rezervasyonlar.get(rid) if (s and rid) else None
        for d in self.dugmeler.values():
            d.setVisible(r is not None)
        self.hap.setVisible(r is not None)
        if not sonucu_koru:
            self.sonuc.temizle()
        if r is None:
            self.baslik.setText("Seçili rezervasyon yok")
            self.paket.setText("")
            self.ayrinti.setText("Takvimde bir kutuya ya da soldaki listeye tıklayın; boş alana "
                                 "sürüklerseniz talep formu dolar.")
            return
        t = tema.aktif()
        dolgu, kenar, yazi = t["durum"][r.durum]
        self.hap.setText(DURUM_AD.get(r.durum, r.durum))
        self.hap.setStyleSheet(f"background:{dolgu}; color:{yazi}; border:1px solid {kenar};")
        kul = s.kullanicilar.get(r.kullanici, {})
        self.baslik.setText(r.id)
        self.paket.setText(f"paket {r.paket}" if r.paket else "")
        self.ayrinti.setText(f"{r.kullanici} {kul.get('ad', '')}  ·  {r.kaynak}  ·  "
                             f"{aralik_metni(r.baslangic, r.bitis)}  ·  {r.ucret} KP")
        onerilen = self.ONERILEN.get(r.durum)
        for eylem, d in self.dugmeler.items():
            ad = "birincil" if eylem == onerilen else ("tehlike" if eylem == "iptal" else "")
            if d.objectName() != ad:
                d.setObjectName(ad)
                tema.yeniden_cilala(d)
            renk = "#ffffff" if ad == "birincil" else (t["hata"] if eylem == "iptal" else t["yazi2"])
            d.setIcon(tema.QIcon(tema.ikon_pixmap(eylem, renk)))

    def eylem(self, eylem: str, rid: str | None = None):
        rid = rid or self.rid
        if not rid:
            return
        sonuc = getattr(self.oturum, eylem)(rid)
        self.goster(rid, sonucu_koru=True)
        if sonuc["durum"] == "RED":
            self.sonuc.hata(sonuc["kod"])
            return
        if eylem == "giris":
            self.sonuc.goster("tamam", "Giriş yapıldı", f"{rid} artık kullanımda.")
        elif eylem == "cikis":
            metin = f"{rid} tamamlandı, güvenilirlik {sonuc['guvenilirlik']}."
            if sonuc["olaylar"]:
                metin += "<br>" + olaylar_html(sonuc["olaylar"])
            self.sonuc.goster("tamam", "Çıkış yapıldı", metin)
        else:
            metin = (f"İade <b>{sonuc['iade']} KP</b>  ·  bakiye {sonuc['bakiye']}  ·  "
                     f"güvenilirlik {sonuc['guvenilirlik']}")
            if sonuc["olaylar"]:
                metin += "<br>" + olaylar_html(sonuc["olaylar"])
            self.sonuc.goster("tamam", "İptal edildi", metin)


# ---------------------------------------------------------------------------
# Talep formu: tek rezervasyon veya paket
# ---------------------------------------------------------------------------
class KalemSatiri(QFrame):
    degisti = Signal()
    silinmek_istendi = Signal(object)
    odaklandi = Signal(object)
    _sayac = 0

    def __init__(self, oturum):
        super().__init__()
        KalemSatiri._sayac += 1
        self.anahtar = f"paket-{KalemSatiri._sayac}"
        self.oturum = oturum
        self.fiyat = None
        self.setObjectName("kalem")
        lay = QGridLayout(self)
        lay.setContentsMargins(8, 6, 6, 6)
        lay.setHorizontalSpacing(6)
        lay.setVerticalSpacing(5)
        self.numara = ikincil()
        self.kaynak = QComboBox()
        self.gun = GunKutusu()
        self.bas = SaatKutusu("10:00")
        self.bit = SaatKutusu("11:00")
        self.sil = ikonla(QPushButton(), "kapat", "yazi3")
        self.sil.setObjectName("hayalet")
        self.sil.setToolTip("Kalemi çıkar")
        self.sil.setFixedWidth(30)
        self.durum = QLabel()
        self.durum.setObjectName("kalemDurum")
        self.durum.setWordWrap(True)
        lay.addWidget(self.numara, 0, 0, 1, 3)
        lay.addWidget(self.sil, 0, 3, Qt.AlignRight)
        lay.addWidget(self.kaynak, 1, 0, 1, 2)
        lay.addWidget(self.gun, 1, 2, 1, 2)
        lay.addWidget(self.bas, 2, 0)
        lay.addWidget(self.bit, 2, 1)
        lay.addWidget(self.durum, 2, 2, 1, 2)
        lay.setColumnStretch(2, 1)
        self.sil.clicked.connect(lambda: self.silinmek_istendi.emit(self))
        for w in (self.kaynak, self.bas, self.bit):
            w.currentTextChanged.connect(self.degisti)
        self.gun.dateChanged.connect(self.degisti)
        for w in (self.kaynak, self.gun, self.bas, self.bit):
            w.installEventFilter(self)

    def eventFilter(self, nesne, olay):
        if olay.type() in (QEvent.Type.FocusIn, QEvent.Type.MouseButtonPress):
            self.odaklandi.emit(self)
        return False

    def durum_yaz(self, tur: str, metin: str, ipucu: str = ""):
        ozellik(self.durum, "tur", tur)
        self.durum.setText(metin)
        self.durum.setToolTip(ipucu)

    def kalem(self) -> dict:
        return {"kaynak": self.kaynak.currentData(),
                "baslangic": zaman_birlestir(self.gun.date(), self.bas.currentText()),
                "bitis": zaman_birlestir(self.gun.date(), self.bit.currentText())}


class TalepFormu(QFrame):
    def __init__(self, oturum):
        super().__init__()
        self.oturum = oturum
        self.kullanici_id: str | None = None
        self._dokunuldu = False   # kullanıcı forma dokunmadan fiyat sorulmaz (günlük temiz kalsın)
        self._kurulum = True
        self.setObjectName("panel")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)
        lay.addWidget(bolum_basligi("Talep formu"))
        self.talep_eden = ikincil("", "etiket")
        self.talep_eden.setTextFormat(Qt.RichText)
        lay.addWidget(self.talep_eden)
        self.sekmeler = QTabWidget()
        self.sekmeler.currentChanged.connect(lambda _: self._dokunuldu and self._onizle_aktif_sekme())
        lay.addWidget(self.sekmeler, 1)

        # --- Tek rezervasyon
        tek = QWidget()
        f = QFormLayout(tek)
        f.setContentsMargins(0, 10, 0, 0)
        f.setVerticalSpacing(9)
        f.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.kaynak = QComboBox()
        self.gun = GunKutusu()
        self.bas = SaatKutusu("10:00")
        self.bit = SaatKutusu("11:00")
        saatler = QHBoxLayout()
        saatler.setSpacing(6)
        saatler.addWidget(self.bas)
        saatler.addWidget(ikincil("–", "etiket"))
        saatler.addWidget(self.bit)
        saatler.addStretch()
        f.addRow(ikincil("Kaynak", "etiket"), self.kaynak)
        f.addRow(ikincil("Gün", "etiket"), self.gun)
        f.addRow(ikincil("Saat", "etiket"), saatler)
        self.fiyat_etiket = QLabel()
        self.fiyat_etiket.setObjectName("fiyat")
        self.fiyat_etiket.setWordWrap(True)
        f.addRow(ikincil("Ücret", "etiket"), self.fiyat_etiket)
        dugmeler = QHBoxLayout()
        self.gonder = QPushButton("Rezervasyon yap")
        self.gonder.setObjectName("birincil")
        self.gonder.clicked.connect(self._tek_gonder)
        self.bekle = ikonla(QPushButton("Bekleme kaydı aç"), "kum")
        self.bekle.clicked.connect(lambda: self._bekleme(self._tek_alanlar()))
        dugmeler.addWidget(self.gonder)
        dugmeler.addWidget(self.bekle)
        dugmeler.addStretch()
        f.addRow(dugmeler)
        self.tek_sonuc = SonucKutusu()
        f.addRow(self.tek_sonuc)
        for w in (self.kaynak, self.bas, self.bit):
            w.currentTextChanged.connect(self._alan_degisti)
        self.gun.dateChanged.connect(self._alan_degisti)
        self.sekmeler.addTab(tek, "Tek rezervasyon")

        # --- Paket
        paket = QWidget()
        p = QVBoxLayout(paket)
        p.setContentsMargins(0, 10, 0, 0)
        p.setSpacing(6)
        aciklama_etiket = ikincil("Ya hepsi alınır ya hiçbiri. Takvimde sürüklediğiniz aralık seçili kaleme yazılır.")
        aciklama_etiket.setWordWrap(True)
        p.addWidget(aciklama_etiket)
        self.kalem_kutusu = QVBoxLayout()
        self.kalem_kutusu.setSpacing(4)
        p.addLayout(self.kalem_kutusu)
        self.kalemler: list[KalemSatiri] = []
        self.aktif_kalem: KalemSatiri | None = None
        alt = QHBoxLayout()
        ekle = ikonla(QPushButton("Kalem ekle"), "arti")
        ekle.setObjectName("hayalet")
        ekle.clicked.connect(lambda: self._kalem_ekle())
        alt.addWidget(ekle)
        alt.addStretch()
        self.paket_toplam = QLabel()
        self.paket_toplam.setObjectName("fiyat")
        alt.addWidget(self.paket_toplam)
        p.addLayout(alt)
        self.paket_gonder = QPushButton("Paketi gönder")
        self.paket_gonder.setObjectName("birincil")
        self.paket_gonder.clicked.connect(self._paket_gonder)
        p.addWidget(self.paket_gonder, 0, Qt.AlignLeft)
        self.paket_sonuc = SonucKutusu()
        p.addWidget(self.paket_sonuc)
        p.addStretch()
        self.sekmeler.addTab(paket, "Paket")

    # ------------------------------------------------------------------
    def sifirla(self):
        """Yeni başlangıç dosyası yüklenince formu ilk haline getirir."""
        self._kurulum = True
        self._dokunuldu = False
        for k in list(self.kalemler):
            self._kalem_sil(k, onizle=False)
        gun = self.oturum.sistem.saat.date()
        self.gun.setDate(QDate(gun.year, gun.month, gun.day))
        self.kaynaklari_yenile()
        self._kalem_ekle(onizle=False)
        self._kalem_ekle(onizle=False)
        self.tek_sonuc.temizle()
        self.paket_sonuc.temizle()
        self._fiyat_bos("Takvimde sürükleyin ya da alanları seçin")
        self._kurulum = False

    def _fiyat_bos(self, metin: str):
        ozellik(self.fiyat_etiket, "tur", "bos")
        self.fiyat_etiket.setText(metin)
        self.paket_toplam.setText("")

    def kaynaklari_yenile(self):
        for kutu in [self.kaynak] + [k.kaynak for k in self.kalemler]:
            onceki = kutu.currentData()
            kutu.blockSignals(True)
            kutu.clear()
            for k in self.oturum.sistem.kaynaklar.values():
                kutu.addItem(f"{k['id']} — {k['ad']}", k["id"])
            i = kutu.findData(onceki)
            kutu.setCurrentIndex(i if i >= 0 else 0)
            kutu.blockSignals(False)

    def kullanici_ayarla(self, kullanici_id: str):
        self.kullanici_id = kullanici_id
        kul = self.oturum.sistem.kullanicilar.get(kullanici_id, {})
        self.talep_eden.setText(f"Talep eden: <b>{kullanici_id}</b> {kul.get('ad', '')}")
        self.tek_sonuc.temizle()
        self.paket_sonuc.temizle()
        if self._dokunuldu and not self._kurulum:
            self._onizle_aktif_sekme()

    def aralik_doldur(self, kaynak_id: str, bas: datetime, bit: datetime):
        """Takvimde seçilen aralığı forma yazar."""
        qgun = QDate(bas.year, bas.month, bas.day)
        if self.sekmeler.currentIndex() == 1 and self.kalemler:
            k = self.aktif_kalem if self.aktif_kalem in self.kalemler else self.kalemler[0]
            hedef = (k.kaynak, k.gun, k.bas, k.bit)
        else:
            hedef = (self.kaynak, self.gun, self.bas, self.bit)
        for w in hedef:
            w.blockSignals(True)
        hedef[0].setCurrentIndex(max(0, hedef[0].findData(kaynak_id)))
        hedef[1].setDate(qgun)
        hedef[2].setCurrentText(saat_metni(bas))
        hedef[3].setCurrentText(saat_metni(bit))
        for w in hedef:
            w.blockSignals(False)
        self._dokunuldu = True
        self._onizle_aktif_sekme()
        belir(self.fiyat_etiket if self.sekmeler.currentIndex() == 0 else self.paket_toplam, 220)

    def durum_degisti(self):
        """Modülün durumu değişince eski önizleme geçersizdir. Yeniden hesaplanmaz;
        kullanıcı bir alanı değiştirdiğinde zaten hesaplanacak."""
        if self._dokunuldu:
            self._fiyat_bos("Alan değiştirince yeniden hesaplanır")
        for k in self.kalemler:
            k.fiyat = None
            if k.durum.property("tur") == "fiyat":
                k.durum_yaz("fiyat", "")

    def _onizle_aktif_sekme(self):
        if self.sekmeler.currentIndex() == 0:
            self._tek_onizle()
        else:
            self._paket_onizle()

    # ------------------------------------------------------------------
    def _alan_degisti(self, *_):
        if self._kurulum:
            return
        self._dokunuldu = True
        self._tek_onizle()

    def _tek_alanlar(self) -> tuple:
        return (self.kullanici_id, self.kaynak.currentData(),
                zaman_birlestir(self.gun.date(), self.bas.currentText()),
                zaman_birlestir(self.gun.date(), self.bit.currentText()))

    def _tek_onizle(self):
        if self._kurulum or not self.kullanici_id:
            return
        sonuc = self.oturum.fiyat(*self._tek_alanlar(), onizleme="tek")
        if sonuc["durum"] == "TAMAM":
            ozellik(self.fiyat_etiket, "tur", "tutar")
            self.fiyat_etiket.setText(f"{sonuc['ucret']} KP")
        else:
            ozellik(self.fiyat_etiket, "tur", "hata")
            self.fiyat_etiket.setText(sonuc["kod"])
            self.fiyat_etiket.setToolTip(aciklama(sonuc["kod"]))

    def _tek_gonder(self):
        alanlar = self._tek_alanlar()
        sonuc = self.oturum.rezervasyon(*alanlar)
        if sonuc["durum"] == "TAMAM":
            self.tek_sonuc.goster("tamam", f"{sonuc['rezervasyon_id']} oluşturuldu",
                                  f"Ücret {sonuc['ucret']} KP  ·  yeni bakiye <b>{sonuc['bakiye']} KP</b>")
        elif sonuc["kod"] in ("KESISME", "HAZIRLIK_IHLALI"):
            self.tek_sonuc.hata(sonuc["kod"], ("Bu aralık için bekleme kaydı aç", lambda: self._bekleme(alanlar)))
        else:
            self.tek_sonuc.hata(sonuc["kod"])

    def _bekleme(self, alanlar: tuple):
        sonuc = self.oturum.bekleme(*alanlar)
        if sonuc["durum"] == "TAMAM":
            self.tek_sonuc.goster("tamam", f"Bekleme kaydı {sonuc['bekleme_id']} açıldı",
                                  f"{alanlar[1]} listesinde sıra <b>{sonuc['sira']}</b>. "
                                  "Yer boşalınca kurallara uyuyorsa otomatik atanır.")
        else:
            self.tek_sonuc.hata(sonuc["kod"])

    # ------------------------------------------------------------------
    def _kalem_ekle(self, onizle: bool = True):
        k = KalemSatiri(self.oturum)
        for kay in self.oturum.sistem.kaynaklar.values():
            k.kaynak.addItem(f"{kay['id']} — {kay['ad']}", kay["id"])
        k.gun.setDate(self.gun.date())
        k.degisti.connect(lambda k=k: self._kalem_degisti(k))
        k.silinmek_istendi.connect(self._kalem_sil)
        k.odaklandi.connect(self._kalem_odak)
        self.kalemler.append(k)
        self.kalem_kutusu.addWidget(k)
        self._numarala()
        self._kalem_odak(k)
        if onizle:
            belir(k, 200)
            if self._dokunuldu:
                self._kalem_onizle(k)

    def _numarala(self):
        for i, k in enumerate(self.kalemler):
            k.numara.setText(f"Kalem {i + 1}")

    def _kalem_odak(self, k):
        self.aktif_kalem = k
        for x in self.kalemler:
            ozellik(x, "aktif", x is k)

    def _kalem_sil(self, k, onizle: bool = True):
        self.kalemler.remove(k)
        k.setParent(None)
        k.deleteLater()
        self._numarala()
        if onizle:
            self._paket_toplam_yaz()

    def _kalem_degisti(self, k):
        if self._kurulum:
            return
        self._dokunuldu = True
        self._kalem_onizle(k)

    def _kalem_onizle(self, k: KalemSatiri):
        if self._kurulum or not self.kullanici_id:
            return
        kalem = k.kalem()
        sonuc = self.oturum.fiyat(self.kullanici_id, kalem["kaynak"], kalem["baslangic"], kalem["bitis"],
                                  onizleme=k.anahtar)
        k.fiyat = sonuc.get("ucret")
        if sonuc["durum"] == "TAMAM":
            k.durum_yaz("fiyat", f"{sonuc['ucret']} KP")
        else:
            k.durum_yaz("hata", sonuc["kod"], aciklama(sonuc["kod"]))
        self._paket_toplam_yaz()

    def _paket_onizle(self):
        for k in self.kalemler:
            self._kalem_onizle(k)

    def _paket_toplam_yaz(self):
        fiyatlar = [k.fiyat for k in self.kalemler]
        if fiyatlar and all(f is not None for f in fiyatlar):
            ozellik(self.paket_toplam, "tur", "tutar")
            self.paket_toplam.setText(f"Toplam {sum(fiyatlar)} KP")
        else:
            self.paket_toplam.setText("")

    def _paket_gonder(self):
        kalemler = [k.kalem() for k in self.kalemler]
        sonuc = self.oturum.paket(self.kullanici_id, kalemler)
        if sonuc["durum"] == "TAMAM":
            for k, rid, ucret in zip(self.kalemler, sonuc["rezervasyonlar"], sonuc["ucretler"]):
                k.durum_yaz("tamam", f"{rid} · {ucret} KP")
            self.paket_sonuc.goster("tamam", f"Paket {sonuc['paket_id']} oluşturuldu",
                                    f"{', '.join(sonuc['rezervasyonlar'])}  ·  toplam {sonuc['toplam']} KP  ·  "
                                    f"yeni bakiye <b>{sonuc['bakiye']} KP</b>")
            return
        # Her kalemin sonucu kendi satırında
        for k, kalem_sonuc in zip(self.kalemler, sonuc.get("kalemler", [])):
            if kalem_sonuc["durum"] == "TAMAM":
                k.durum_yaz("tamam", "Geçti")
            else:
                k.durum_yaz("hata", kalem_sonuc["kod"], aciklama(kalem_sonuc["kod"]))
            belir(k.durum, 200)
        self.paket_sonuc.hata(sonuc["kod"])


# ---------------------------------------------------------------------------
# Olay günlüğü
# ---------------------------------------------------------------------------
class OlayGunlugu(QFrame):
    daraltildi = Signal(bool)

    def __init__(self, oturum):
        super().__init__()
        self.oturum = oturum
        self.setObjectName("panel")
        dis = QVBoxLayout(self)
        dis.setContentsMargins(14, 8, 14, 10)
        dis.setSpacing(6)
        ust = QHBoxLayout()
        ust.addWidget(bolum_basligi("Olay günlüğü"))
        self.sayi = ikincil()
        ust.addWidget(self.sayi)
        ust.addStretch()
        ust.addWidget(ikincil("Bir satır seçince komut ve sonuç JSON olarak görünür"))
        self.daralt = QPushButton()
        self.daralt.setObjectName("hayalet")
        self.daralt.clicked.connect(self._daralt)
        ust.addWidget(self.daralt)
        dis.addLayout(ust)
        self.govde = QWidget()
        lay = QHBoxLayout(self.govde)
        lay.setContentsMargins(0, 0, 0, 0)
        self.tablo = tablo(["No", "Komut", "Durum", "Özet"], esnek=3)
        self.tablo.setFocusPolicy(Qt.StrongFocus)
        self.tablo.itemSelectionChanged.connect(self._secildi)
        lay.addWidget(self.tablo, 3)
        bolme = QSplitter(Qt.Horizontal)
        self.komut_metni = QPlainTextEdit(); self.komut_metni.setReadOnly(True)
        self.sonuc_metni = QPlainTextEdit(); self.sonuc_metni.setReadOnly(True)
        for baslik, w in (("Komut", self.komut_metni), ("Sonuç", self.sonuc_metni)):
            kutu = QWidget()
            k = QVBoxLayout(kutu)
            k.setContentsMargins(0, 0, 0, 0)
            k.setSpacing(3)
            k.addWidget(ikincil(baslik, "etiket"))
            k.addWidget(w)
            bolme.addWidget(kutu)
        lay.addWidget(bolme, 4)
        dis.addWidget(self.govde, 1)
        self._acik = True
        self._dugme_yaz()
        tema.yonetici.degisti.connect(self.yenile)
        tema.yonetici.degisti.connect(self._dugme_yaz)

    def _dugme_yaz(self):
        self.daralt.setText("Gizle" if self._acik else "Göster")
        self.daralt.setIcon(tema.ikon("asagi" if self._acik else "yukari"))

    def _daralt(self):
        self._acik = not self._acik
        self.govde.setVisible(self._acik)
        self._dugme_yaz()
        self.daraltildi.emit(not self._acik)

    def yenile(self):
        g = self.oturum.gunluk
        t = tema.aktif()
        secili = self.tablo.selectionModel().selectedRows()
        sonda = not secili or secili[0].row() >= self.tablo.rowCount() - 1
        self.tablo.blockSignals(True)
        self.tablo.setRowCount(len(g))
        for satir, kayit in enumerate(g):
            sonuc = kayit["sonuc"]
            komut_adi = kayit["komut"]["komut"] + (" · önizleme" if kayit.get("onizleme") else "")
            degerler = [str(kayit["no"]), komut_adi, sonuc["durum"], sonuc_ozeti(sonuc)]
            for sutun, deger in enumerate(degerler):
                hucre = QTableWidgetItem(deger)
                if kayit.get("onizleme"):
                    hucre.setForeground(QColor(t["yazi3"]))
                elif sutun == 2:
                    hucre.setForeground(QColor(t["basari"] if deger == "TAMAM" else t["hata"]))
                self.tablo.setItem(satir, sutun, hucre)
        self.tablo.blockSignals(False)
        self.sayi.setText(f"{sum(1 for k in g if not k.get('onizleme'))} işlem")
        if g and sonda:
            self.tablo.selectRow(len(g) - 1)
            self.tablo.scrollToBottom()
        elif not g:
            self.komut_metni.clear()
            self.sonuc_metni.clear()

    def _secildi(self):
        satirlar = self.tablo.selectionModel().selectedRows()
        if not satirlar:
            return
        kayit = self.oturum.gunluk[satirlar[0].row()]
        self.komut_metni.setPlainText(json.dumps(kayit["komut"], ensure_ascii=False, indent=2))
        self.sonuc_metni.setPlainText(json.dumps(kayit["sonuc"], ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# Yeni üye / yeni kaynak pencereleri
# ---------------------------------------------------------------------------
class _EklemePenceresi(QDialog):
    def __init__(self, oturum, baslik: str, parent=None):
        super().__init__(parent)
        self.oturum = oturum
        self.setWindowTitle(baslik)
        self.setMinimumWidth(420)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(18, 16, 18, 16)
        self.lay.setSpacing(12)
        self.lay.addWidget(bolum_basligi(baslik))
        self.form = QFormLayout()
        self.form.setVerticalSpacing(9)
        self.lay.addLayout(self.form)
        self.sonuc = SonucKutusu()
        self.lay.addWidget(self.sonuc)
        alt = QHBoxLayout()
        alt.addStretch()
        vazgec = QPushButton("Vazgeç")
        vazgec.setObjectName("hayalet")
        vazgec.clicked.connect(self.reject)
        self.ekle = QPushButton("Ekle")
        self.ekle.setObjectName("birincil")
        self.ekle.setDefault(True)
        self.ekle.clicked.connect(self._ekle)
        alt.addWidget(vazgec)
        alt.addWidget(self.ekle)
        self.lay.addLayout(alt)
        self.eklenen_id: str | None = None

    def satir(self, ad: str, w):
        self.form.addRow(ikincil(ad, "etiket"), w)

    @staticmethod
    def _onay_listesi(degerler, secili=()) -> tuple[QWidget, list[QCheckBox]]:
        kutu = QWidget()
        lay = QHBoxLayout(kutu)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        kutular = []
        for d in degerler:
            c = QCheckBox(d)
            c.setChecked(d in secili)
            lay.addWidget(c)
            kutular.append(c)
        if not degerler:
            lay.addWidget(ikincil("Başlangıç dosyasında tanımlı değer yok"))
        lay.addStretch()
        return kutu, kutular

    def _sonuc_isle(self, sonuc: dict, yeni_id: str):
        if sonuc["durum"] == "TAMAM":
            self.eklenen_id = yeni_id
            self.accept()
        else:
            self.sonuc.hata(sonuc["kod"])


def _siradaki_id(var_olanlar, onek: str) -> str:
    n = 1
    while f"{onek}{n}" in var_olanlar:
        n += 1
    return f"{onek}{n}"


class YeniUyePenceresi(_EklemePenceresi):
    def __init__(self, oturum, parent=None):
        super().__init__(oturum, "Yeni üye ekle", parent)
        s = oturum.sistem
        self.kimlik = QLineEdit(_siradaki_id(s.kullanicilar, "u"))
        self.ad = QLineEdit()
        self.ad.setPlaceholderText("Ad Soyad")
        self.rol = QComboBox()
        self.rol.addItems(list(s.roller))
        kutu, self.sertifikalar = self._onay_listesi(s.sertifika_listesi())
        self.bakiye = QSpinBox()
        self.bakiye.setRange(-100000, 100000)
        self.bakiye.setSuffix(" KP")
        self.guven = QSpinBox()
        self.guven.setRange(-1000, 1000)
        self.guven.setValue(80)
        self.rol.currentTextChanged.connect(self._rol_degisti)
        self._rol_degisti(self.rol.currentText())
        self.satir("Kimlik", self.kimlik)
        self.satir("Ad", self.ad)
        self.satir("Rol", self.rol)
        self.satir("Sertifikalar", kutu)
        self.satir("Bakiye", self.bakiye)
        self.satir("Güvenilirlik", self.guven)
        self.form.addRow(ikincil("Bakiye, seçilen rolün haftalık kotasıyla başlar."))
        self.ad.setFocus()

    def _rol_degisti(self, rol: str):
        rol_bilgi = self.oturum.sistem.roller.get(rol)
        if rol_bilgi:
            self.bakiye.setValue(int(rol_bilgi["haftalik_kota"]))

    def _ekle(self):
        kimlik = self.kimlik.text().strip()
        sonuc = self.oturum.kullanici_ekle(kimlik, self.ad.text().strip() or kimlik, self.rol.currentText(),
                                           [c.text() for c in self.sertifikalar if c.isChecked()],
                                           self.bakiye.value(), self.guven.value())
        self._sonuc_isle(sonuc, kimlik)


class YeniKaynakPenceresi(_EklemePenceresi):
    def __init__(self, oturum, parent=None):
        super().__init__(oturum, "Yeni kaynak ekle", parent)
        s = oturum.sistem
        self.tur = QComboBox()
        self.tur.addItems(list(s.turler))
        self.kimlik = QLineEdit()
        self.ad = QLineEdit()
        self.ad.setPlaceholderText("Görünen ad")
        kutu, self.roller = self._onay_listesi(list(s.roller), list(s.roller))
        self.tur.currentTextChanged.connect(self._tur_degisti)
        self._tur_degisti(self.tur.currentText())
        self.satir("Tür", self.tur)
        self.satir("Kimlik", self.kimlik)
        self.satir("Ad", self.ad)
        self.satir("İzinli roller", kutu)
        self.ad.setFocus()

    def _tur_degisti(self, tur: str):
        # Aynı türdeki mevcut kimliklerin ön ekinden öneri üretir (ör. YAZ-2 -> YAZ-1).
        s = self.oturum.sistem
        onekler = [k["id"].rsplit("-", 1)[0] + "-" for k in s.kaynaklar.values()
                   if k["tur"] == tur and "-" in k["id"]]
        onek = onekler[0] if onekler else tur[:3].upper() + "-"
        self.kimlik.setText(_siradaki_id(s.kaynaklar, onek))

    def _ekle(self):
        kimlik = self.kimlik.text().strip()
        sonuc = self.oturum.kaynak_ekle(kimlik, self.ad.text().strip() or kimlik, self.tur.currentText(),
                                        [c.text() for c in self.roller if c.isChecked()])
        self._sonuc_isle(sonuc, kimlik)
