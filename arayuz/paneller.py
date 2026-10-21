"""Ekran parçaları: kullanıcı paneli, talep formu, seçili rezervasyon kartı,
olay günlüğü ve ekleme pencereleri.

Hiçbiri bir talebi kendi başına engellemez; her işlem modüle gönderilir ve
modülün verdiği sonuç gösterilir.
"""
import json
import re
from datetime import datetime, timedelta

from PySide6.QtCore import QDate, QEvent, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDateEdit, QDialog,
                               QFormLayout, QFrame, QGridLayout, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QMenu, QPlainTextEdit, QProgressBar,
                               QPushButton, QSizePolicy, QSpinBox, QSplitter, QTableWidget,
                               QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from .stil import (BASARI_RENK, DURUM_AD, DURUM_RENK, HATA_RENK, aralik_metni, hata_html,
                   olay_metni, saat_metni, sonuc_ozeti, zaman_metinden)

SAATLER = [f"{h:02d}:{m:02d}" for h in range(8, 23) for m in (0, 15, 30, 45) if h < 22 or m == 0]


def bolum_basligi(metin: str) -> QLabel:
    etiket = QLabel(metin)
    etiket.setObjectName("bolumBaslik")
    return etiket


def ikincil(metin: str = "") -> QLabel:
    etiket = QLabel(metin)
    etiket.setObjectName("ikincil")
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
        self.setMaxVisibleItems(16)
        self.setCurrentText(varsayilan)
        self.setMinimumWidth(78)


class GunKutusu(QDateEdit):
    def __init__(self):
        super().__init__()
        self.setCalendarPopup(True)
        self.setDisplayFormat("dd.MM.yyyy ddd")
        self.setMinimumWidth(120)


class SonucKutusu(QFrame):
    """İşlemin sonucunu yapıldığı yerin hemen altında gösterir."""

    def __init__(self):
        super().__init__()
        self.setObjectName("sonucKutusu")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        self.etiket = QLabel()
        self.etiket.setWordWrap(True)
        self.etiket.setTextFormat(Qt.RichText)
        lay.addWidget(self.etiket)
        self.dugme = QPushButton()
        self.dugme.hide()
        lay.addWidget(self.dugme, 0, Qt.AlignLeft)
        self._baglanti = None
        self.hide()

    def goster(self, html: str, basarili: bool | None, dugme: tuple[str, object] | None = None):
        renk = {True: ("#f0fdf4", "#bbf7d0"), False: ("#fef2f2", "#fecaca"),
                None: ("#f8fafc", "#e2e8f0")}[basarili]
        self.setStyleSheet(f"#sonucKutusu {{ background:{renk[0]}; border:1px solid {renk[1]}; }}")
        self.etiket.setText(html)
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

    def temizle(self):
        self.hide()


def olaylar_html(olaylar: list[dict]) -> str:
    if not olaylar:
        return ""
    return "<br>" + "<br>".join(f"• {olay_metni(o)}" for o in olaylar)


# ---------------------------------------------------------------------------
# Kullanıcı paneli
# ---------------------------------------------------------------------------
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
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)

        ust = QHBoxLayout()
        ust.addWidget(bolum_basligi("Kullanıcı"))
        ust.addStretch()
        yeni = QPushButton("+ Yeni üye")
        yeni.setObjectName("kucuk")
        yeni.clicked.connect(self.yeni_uye_istendi)
        ust.addWidget(yeni)
        lay.addLayout(ust)

        self.secim = QComboBox()
        self.secim.currentIndexChanged.connect(self._secim_degisti)
        lay.addWidget(self.secim)

        self.bilgi = ikincil()
        self.bilgi.setWordWrap(True)
        lay.addWidget(self.bilgi)

        izgara = QGridLayout()
        izgara.setHorizontalSpacing(14)
        izgara.addWidget(ikincil("Bakiye"), 0, 0)
        izgara.addWidget(ikincil("Güvenilirlik"), 0, 1)
        self.bakiye = QLabel("—"); self.bakiye.setObjectName("buyukDeger")
        self.guven = QLabel("—"); self.guven.setObjectName("buyukDeger")
        izgara.addWidget(self.bakiye, 1, 0)
        izgara.addWidget(self.guven, 1, 1)
        self.bakiye_cubuk = QProgressBar(); self.bakiye_cubuk.setTextVisible(False)
        self.guven_cubuk = QProgressBar(); self.guven_cubuk.setTextVisible(False)
        self.guven_cubuk.setRange(0, 100)
        izgara.addWidget(self.bakiye_cubuk, 2, 0)
        izgara.addWidget(self.guven_cubuk, 2, 1)
        lay.addLayout(izgara)

        lay.addSpacing(4)
        lay.addWidget(bolum_basligi("Rezervasyonlar"))
        self.tablo = self._tablo(["No", "Kaynak", "Aralık", "KP", "Durum"])
        self.tablo.itemSelectionChanged.connect(self._satir_secildi)
        self.tablo.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tablo.customContextMenuRequested.connect(self._menu)
        lay.addWidget(self.tablo, 3)

        lay.addWidget(bolum_basligi("Bekleme kayıtları"))
        self.bekleme_tablo = self._tablo(["No", "Kaynak", "Aralık", "Sıra"])
        lay.addWidget(self.bekleme_tablo, 1)
        self._yukleniyor = False

    @staticmethod
    def _tablo(basliklar, esnek: int = 2) -> QTableWidget:
        t = QTableWidget(0, len(basliklar))
        t.setHorizontalHeaderLabels(basliklar)
        t.verticalHeader().hide()
        t.setSelectionBehavior(QAbstractItemView.SelectRows)
        t.setSelectionMode(QAbstractItemView.SingleSelection)
        t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        t.setShowGrid(False)
        t.verticalHeader().setDefaultSectionSize(24)
        t.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        t.setWordWrap(False)
        baslik = t.horizontalHeader()
        baslik.setSectionResizeMode(QHeaderView.ResizeToContents)
        baslik.setSectionResizeMode(esnek, QHeaderView.Stretch)
        return t

    @property
    def kullanici_id(self) -> str | None:
        return self.secim.currentData()

    def kullanicilari_yenile(self, secilecek: str | None = None):
        s = self.oturum.sistem
        onceki = secilecek or self.kullanici_id
        self._yukleniyor = True
        self.secim.clear()
        for u in s.kullanicilar.values():
            self.secim.addItem(f"{u['id']} — {u['ad']}  ({u['rol']})", u["id"])
        indeks = self.secim.findData(onceki)
        self.secim.setCurrentIndex(indeks if indeks >= 0 else 0)
        self._yukleniyor = False
        self._secim_degisti()

    def _secim_degisti(self):
        if self._yukleniyor:
            return
        if self.kullanici_id:
            self.oturum.sorgu_kullanici(self.kullanici_id)
        self.yenile()
        if self.kullanici_id:
            self.kullanici_degisti.emit(self.kullanici_id)

    def yenile(self):
        s = self.oturum.sistem
        kul = s.kullanicilar.get(self.kullanici_id) if s else None
        self.tablo.setRowCount(0)
        self.bekleme_tablo.setRowCount(0)
        if kul is None:
            return
        rol = s.roller[kul["rol"]]
        sertifika = ", ".join(kul["sertifikalar"]) or "yok"
        self.bilgi.setText(f"{kul['rol']} · Sertifika: {sertifika} · Azami süre {rol['azami_sure_dk']} dk · "
                           f"İleri tarih {rol['ileri_gun']} gün")
        self.bakiye.setText(f"{kul['bakiye']} <span style='font-size:9pt;color:#64748b'>/ {rol['haftalik_kota']} KP</span>")
        self.bakiye_cubuk.setRange(0, max(1, int(rol["haftalik_kota"])))
        self.bakiye_cubuk.setValue(int(kul["bakiye"]))
        dusuk = kul["guvenilirlik"] < 50
        self.guven.setText(f"<span style='color:{HATA_RENK if dusuk else '#0f172a'}'>{kul['guvenilirlik']}</span>"
                           "<span style='font-size:9pt;color:#64748b'> / 100</span>")
        self.guven_cubuk.setValue(kul["guvenilirlik"])
        self.guven_cubuk.setStyleSheet(f"QProgressBar::chunk {{ background: {HATA_RENK if dusuk else BASARI_RENK}; }}")

        # Sıralama ve içerik modülün sorgu sonucundan gelir.
        rezler = s.sorgu("kullanici", kul["id"])["rezervasyonlar"]
        for r in rezler:
            satir = self.tablo.rowCount()
            self.tablo.insertRow(satir)
            b, e = datetime.fromisoformat(r["baslangic"]), datetime.fromisoformat(r["bitis"])
            degerler = [r["id"], r["kaynak"], aralik_metni(b, e), str(r["ucret"]), DURUM_AD.get(r["durum"], r["durum"])]
            for sutun, deger in enumerate(degerler):
                hucre = QTableWidgetItem(deger)
                hucre.setData(Qt.UserRole, r["id"])
                if sutun == 4:
                    dolgu, kenar, yazi = DURUM_RENK.get(r["durum"], ("#fff", "#000", "#000"))
                    hucre.setForeground(QColor(kenar if r["durum"] != "TAMAMLANDI" else "#475569"))
                self.tablo.setItem(satir, sutun, hucre)
        for b in s.kullanici_beklemeleri(kul["id"]):
            satir = self.bekleme_tablo.rowCount()
            self.bekleme_tablo.insertRow(satir)
            sira = [x.id for x in s.kaynak_beklemeleri(b.kaynak)].index(b.id) + 1
            for sutun, deger in enumerate([b.id, b.kaynak, aralik_metni(b.baslangic, b.bitis), str(sira)]):
                self.bekleme_tablo.setItem(satir, sutun, QTableWidgetItem(deger))

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
            menu.addAction(ad, lambda e=eylem: self.eylem_istendi.emit(e, rid))
        menu.exec(self.tablo.viewport().mapToGlobal(konum))


# ---------------------------------------------------------------------------
# Seçili rezervasyon kartı (takvimin altında): ayrıntılar + giriş/çıkış/iptal
# ---------------------------------------------------------------------------
class SeciliKart(QFrame):
    def __init__(self, oturum):
        super().__init__()
        self.oturum = oturum
        self.rid: str | None = None
        self.setObjectName("panel")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        sol = QVBoxLayout()
        self.baslik = QLabel()
        self.baslik.setTextFormat(Qt.RichText)
        self.ayrinti = ikincil()
        sol.addWidget(self.baslik)
        sol.addWidget(self.ayrinti)
        lay.addLayout(sol, 1)
        self.dugmeler = []
        for eylem, ad, ad_nesne in (("giris", "Giriş", "birincil"), ("cikis", "Çıkış", ""),
                                    ("iptal", "İptal", "tehlike")):
            d = QPushButton(ad)
            if ad_nesne:
                d.setObjectName(ad_nesne)
            d.clicked.connect(lambda _=False, e=eylem: self.eylem(e))
            lay.addWidget(d)
            self.dugmeler.append(d)
        self.sonuc = SonucKutusu()
        self.sonuc.setMinimumWidth(280)
        self.sonuc.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        lay.addWidget(self.sonuc, 1)
        self.goster(None)

    def goster(self, rid: str | None, sonucu_koru: bool = False):
        self.rid = rid
        s = self.oturum.sistem
        r = s.rezervasyonlar.get(rid) if (s and rid) else None
        for d in self.dugmeler:
            d.setVisible(r is not None)
        if not sonucu_koru:
            self.sonuc.temizle()
        if r is None:
            self.baslik.setText("<b>Seçili rezervasyon yok</b>")
            self.ayrinti.setText("Takvimde bir kutuya ya da kullanıcının rezervasyon listesine tıklayın. "
                                 "Boş alana sürükleyerek talep formunu doldurabilirsiniz.")
            return
        dolgu, kenar, yazi = DURUM_RENK.get(r.durum, ("#fff", "#000", "#000"))
        kul = s.kullanicilar.get(r.kullanici, {})
        self.baslik.setText(f"<b style='font-size:11pt'>{r.id}</b> &nbsp;"
                            f"<span style='background:{dolgu};color:{yazi};border:1px solid {kenar};'>"
                            f"&nbsp;{DURUM_AD.get(r.durum, r.durum)}&nbsp;</span>"
                            + (f" &nbsp;<span style='color:#64748b'>paket {r.paket}</span>" if r.paket else ""))
        self.ayrinti.setText(f"{r.kullanici} {kul.get('ad', '')} · {r.kaynak} · "
                             f"{aralik_metni(r.baslangic, r.bitis)} · {r.ucret} KP")

    def eylem(self, eylem: str, rid: str | None = None):
        rid = rid or self.rid
        if not rid:
            return
        sonuc = getattr(self.oturum, eylem)(rid)
        self.goster(rid, sonucu_koru=True)
        if sonuc["durum"] == "RED":
            self.sonuc.goster(hata_html(sonuc["kod"]), False)
            return
        if eylem == "giris":
            html = f"<b style='color:{BASARI_RENK}'>✓ Giriş yapıldı</b> — {rid} artık KULLANIMDA"
        elif eylem == "cikis":
            html = (f"<b style='color:{BASARI_RENK}'>✓ Çıkış yapıldı</b> — {rid} TAMAMLANDI · "
                    f"güvenilirlik {sonuc['guvenilirlik']}" + olaylar_html(sonuc["olaylar"]))
        else:
            html = (f"<b style='color:{BASARI_RENK}'>✓ İptal edildi</b> — iade {sonuc['iade']} KP · "
                    f"bakiye {sonuc['bakiye']} · güvenilirlik {sonuc['guvenilirlik']}"
                    + olaylar_html(sonuc["olaylar"]))
        self.sonuc.goster(html, True)


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
        lay.setContentsMargins(8, 4, 0, 4)
        lay.setHorizontalSpacing(6)
        self.kaynak = QComboBox()
        self.gun = GunKutusu()
        self.bas = SaatKutusu("10:00")
        self.bit = SaatKutusu("11:00")
        self.sil = QPushButton("✕")
        self.sil.setObjectName("kucuk")
        self.sil.setFixedWidth(28)
        self.durum = QLabel()
        self.durum.setTextFormat(Qt.RichText)
        self.durum.setWordWrap(True)
        lay.addWidget(self.kaynak, 0, 0, 1, 2)
        lay.addWidget(self.gun, 0, 2)
        lay.addWidget(self.sil, 0, 3)
        lay.addWidget(self.bas, 1, 0)
        lay.addWidget(self.bit, 1, 1)
        lay.addWidget(self.durum, 1, 2, 1, 2)
        self.sil.clicked.connect(lambda: self.silinmek_istendi.emit(self))
        for w in (self.kaynak, self.bas, self.bit):
            w.currentTextChanged.connect(self.degisti)
        self.gun.dateChanged.connect(self.degisti)
        for w in (self.kaynak, self.gun, self.bas, self.bit):
            w.installEventFilter(self)

    def eventFilter(self, nesne, olay):
        if olay.type() == QEvent.Type.FocusIn:
            self.odaklandi.emit(self)
        return False

    def kalem(self) -> dict:
        return {"kaynak": self.kaynak.currentData(),
                "baslangic": zaman_birlestir(self.gun.date(), self.bas.currentText()),
                "bitis": zaman_birlestir(self.gun.date(), self.bit.currentText())}


class TalepFormu(QFrame):
    def __init__(self, oturum):
        super().__init__()
        self.oturum = oturum
        self.kullanici_id: str | None = None
        self._son_red: tuple | None = None
        self.setObjectName("panel")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)
        lay.addWidget(bolum_basligi("Talep formu"))
        self.talep_eden = ikincil()
        lay.addWidget(self.talep_eden)
        self.sekmeler = QTabWidget()
        lay.addWidget(self.sekmeler, 1)

        # --- Tek rezervasyon
        tek = QWidget()
        f = QFormLayout(tek)
        f.setContentsMargins(0, 8, 0, 0)
        f.setLabelAlignment(Qt.AlignLeft)
        self.kaynak = QComboBox()
        self.gun = GunKutusu()
        self.bas = SaatKutusu("10:00")
        self.bit = SaatKutusu("11:00")
        saatler = QHBoxLayout()
        saatler.addWidget(self.bas)
        saatler.addWidget(QLabel("→"))
        saatler.addWidget(self.bit)
        saatler.addStretch()
        f.addRow("Kaynak", self.kaynak)
        f.addRow("Gün", self.gun)
        f.addRow("Saat", saatler)
        self.fiyat_etiket = QLabel()
        self.fiyat_etiket.setTextFormat(Qt.RichText)
        self.fiyat_etiket.setWordWrap(True)
        f.addRow("Ücret", self.fiyat_etiket)
        dugmeler = QHBoxLayout()
        self.gonder = QPushButton("Rezervasyon yap")
        self.gonder.setObjectName("birincil")
        self.gonder.clicked.connect(self._tek_gonder)
        self.bekle = QPushButton("Bekleme kaydı aç")
        self.bekle.clicked.connect(lambda: self._bekleme(self._tek_alanlar()))
        dugmeler.addWidget(self.gonder)
        dugmeler.addWidget(self.bekle)
        dugmeler.addStretch()
        f.addRow(dugmeler)
        self.tek_sonuc = SonucKutusu()
        f.addRow(self.tek_sonuc)
        for w in (self.kaynak, self.bas, self.bit):
            w.currentTextChanged.connect(self._tek_onizle)
        self.gun.dateChanged.connect(self._tek_onizle)
        self.sekmeler.addTab(tek, "Tek rezervasyon")

        # --- Paket
        paket = QWidget()
        p = QVBoxLayout(paket)
        p.setContentsMargins(0, 8, 0, 0)
        p.addWidget(ikincil("Ya hepsi alınır ya hiçbiri. Takvimde sürüklediğiniz aralık seçili kaleme yazılır."))
        self.kalem_kutusu = QVBoxLayout()
        self.kalem_kutusu.setSpacing(0)
        p.addLayout(self.kalem_kutusu)
        self.kalemler: list[KalemSatiri] = []
        self.aktif_kalem: KalemSatiri | None = None
        alt = QHBoxLayout()
        ekle = QPushButton("+ Kalem")
        ekle.setObjectName("kucuk")
        ekle.clicked.connect(lambda: self._kalem_ekle())
        alt.addWidget(ekle)
        alt.addStretch()
        self.paket_toplam = QLabel()
        self.paket_toplam.setTextFormat(Qt.RichText)
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
        self._kurulum = True

    # ------------------------------------------------------------------
    def sifirla(self):
        """Yeni başlangıç dosyası yüklenince formu ilk haline getirir."""
        self._kurulum = True
        for k in list(self.kalemler):
            self._kalem_sil(k, onizle=False)
        gun = self.oturum.sistem.saat.date()
        self.gun.setDate(QDate(gun.year, gun.month, gun.day))
        self.kaynaklari_yenile()
        self._kalem_ekle(onizle=False)
        self._kalem_ekle(onizle=False)
        self.tek_sonuc.temizle()
        self.paket_sonuc.temizle()
        self.fiyat_etiket.setText(ikincil_html("Alanları seçince hesaplanır"))
        self.paket_toplam.setText("")
        self._kurulum = False

    def kaynaklari_yenile(self):
        kutular = [self.kaynak] + [k.kaynak for k in self.kalemler]
        for kutu in kutular:
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
        self.talep_eden.setText(f"Talep eden: <b>{kullanici_id}</b> {kul.get('ad', '')} "
                                "(soldaki listeden değiştirilir)")
        self.tek_sonuc.temizle()
        self.paket_sonuc.temizle()
        if not self._kurulum:
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
        self._onizle_aktif_sekme()

    def durum_degisti(self):
        """Modülün durumu değişince eski önizleme geçersizdir; yeniden hesaplanmaz,
        çünkü kullanıcı yeni bir alan seçtiğinde zaten hesaplanacak."""
        self.fiyat_etiket.setText(ikincil_html("Alanları seçince yeniden hesaplanır"))
        for k in self.kalemler:
            k.durum.setText("")
        self.paket_toplam.setText("")

    def _onizle_aktif_sekme(self):
        if self.sekmeler.currentIndex() == 0:
            self._tek_onizle()
        else:
            self._paket_onizle()

    # ------------------------------------------------------------------
    def _tek_alanlar(self) -> tuple:
        return (self.kullanici_id, self.kaynak.currentData(),
                zaman_birlestir(self.gun.date(), self.bas.currentText()),
                zaman_birlestir(self.gun.date(), self.bit.currentText()))

    def _tek_onizle(self, *_):
        if self._kurulum or not self.kullanici_id:
            return
        sonuc = self.oturum.fiyat(*self._tek_alanlar(), onizleme="tek")
        if sonuc["durum"] == "TAMAM":
            self.fiyat_etiket.setText(f"<b style='font-size:12pt'>{sonuc['ucret']} KP</b>")
        else:
            self.fiyat_etiket.setText(hata_html(sonuc["kod"]))

    def _tek_gonder(self):
        alanlar = self._tek_alanlar()
        sonuc = self.oturum.rezervasyon(*alanlar)
        if sonuc["durum"] == "TAMAM":
            self.tek_sonuc.goster(
                f"<b style='color:{BASARI_RENK}'>✓ {sonuc['rezervasyon_id']} oluşturuldu</b><br>"
                f"Ücret {sonuc['ucret']} KP · Yeni bakiye <b>{sonuc['bakiye']} KP</b>", True)
        elif sonuc["kod"] in ("KESISME", "HAZIRLIK_IHLALI"):
            self.tek_sonuc.goster(hata_html(sonuc["kod"]), False,
                                  ("Bu aralık için bekleme kaydı aç", lambda: self._bekleme(alanlar)))
        else:
            self.tek_sonuc.goster(hata_html(sonuc["kod"]), False)

    def _bekleme(self, alanlar: tuple):
        sonuc = self.oturum.bekleme(*alanlar)
        if sonuc["durum"] == "TAMAM":
            self.tek_sonuc.goster(f"<b style='color:{BASARI_RENK}'>✓ Bekleme kaydı {sonuc['bekleme_id']} açıldı</b>"
                                  f" — {alanlar[1]} listesinde sıra {sonuc['sira']}. Yer boşalınca otomatik atanır.",
                                  True)
        else:
            self.tek_sonuc.goster(hata_html(sonuc["kod"]), False)

    # ------------------------------------------------------------------
    def _kalem_ekle(self, onizle: bool = True):
        k = KalemSatiri(self.oturum)
        for kutu_hedef in (k.kaynak,):
            for kay in self.oturum.sistem.kaynaklar.values():
                kutu_hedef.addItem(f"{kay['id']} — {kay['ad']}", kay["id"])
        k.gun.setDate(self.gun.date())
        k.degisti.connect(lambda k=k: self._kalem_onizle(k))
        k.silinmek_istendi.connect(self._kalem_sil)
        k.odaklandi.connect(self._kalem_odak)
        self.kalemler.append(k)
        self.kalem_kutusu.addWidget(k)
        self._kalem_odak(k)
        if onizle:
            self._kalem_onizle(k)

    def _kalem_odak(self, k):
        self.aktif_kalem = k
        for x in self.kalemler:
            x.setStyleSheet("#kalem { border-left: 3px solid transparent; }")
        k.setStyleSheet("#kalem { border-left: 3px solid #2563eb; }")

    def _kalem_sil(self, k, onizle: bool = True):
        self.kalemler.remove(k)
        k.setParent(None)
        k.deleteLater()
        if onizle:
            self._paket_toplam_yaz()

    def _kalem_onizle(self, k: KalemSatiri):
        if self._kurulum or not self.kullanici_id:
            return
        kalem = k.kalem()
        sonuc = self.oturum.fiyat(self.kullanici_id, kalem["kaynak"], kalem["baslangic"], kalem["bitis"],
                                  onizleme=k.anahtar)
        k.fiyat = sonuc.get("ucret")
        if sonuc["durum"] == "TAMAM":
            k.durum.setText(f"<span style='color:#475569'>{sonuc['ucret']} KP</span>")
        else:
            k.durum.setText(f"<span style='color:{HATA_RENK}'>✗ {sonuc['kod']}</span>")
        self._paket_toplam_yaz()

    def _paket_onizle(self):
        for k in self.kalemler:
            self._kalem_onizle(k)

    def _paket_toplam_yaz(self):
        fiyatlar = [getattr(k, "fiyat", None) for k in self.kalemler]
        if fiyatlar and all(f is not None for f in fiyatlar):
            self.paket_toplam.setText(f"Toplam <b>{sum(fiyatlar)} KP</b>")
        else:
            self.paket_toplam.setText("")

    def _paket_gonder(self):
        kalemler = [k.kalem() for k in self.kalemler]
        sonuc = self.oturum.paket(self.kullanici_id, kalemler)
        if sonuc["durum"] == "TAMAM":
            for k, rid, ucret in zip(self.kalemler, sonuc["rezervasyonlar"], sonuc["ucretler"]):
                k.durum.setText(f"<b style='color:{BASARI_RENK}'>✓ {rid} · {ucret} KP</b>")
            self.paket_sonuc.goster(
                f"<b style='color:{BASARI_RENK}'>✓ Paket {sonuc['paket_id']} oluşturuldu</b><br>"
                f"{', '.join(sonuc['rezervasyonlar'])} · Toplam {sonuc['toplam']} KP · "
                f"Yeni bakiye <b>{sonuc['bakiye']} KP</b>", True)
            return
        # Her kalemin sonucu kendi satırında
        for k, kalem_sonuc in zip(self.kalemler, sonuc.get("kalemler", [])):
            if kalem_sonuc["durum"] == "TAMAM":
                k.durum.setText(f"<b style='color:{BASARI_RENK}'>✓ geçti</b>")
            else:
                k.durum.setText(f"<span style='color:{HATA_RENK}'><b>✗ {kalem_sonuc['kod']}</b></span>")
                k.durum.setToolTip(hata_html(kalem_sonuc["kod"]))
        self.paket_sonuc.goster(hata_html(sonuc["kod"]), False)


def ikincil_html(metin: str) -> str:
    return f"<span style='color:#94a3b8'>{metin}</span>"


# ---------------------------------------------------------------------------
# Olay günlüğü
# ---------------------------------------------------------------------------
class OlayGunlugu(QFrame):
    def __init__(self, oturum):
        super().__init__()
        self.oturum = oturum
        self.setObjectName("panel")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        sol = QVBoxLayout()
        sol.addWidget(bolum_basligi("Olay günlüğü"))
        self.tablo = KullaniciPaneli._tablo(["No", "Komut", "Durum", "Özet"], esnek=3)
        self.tablo.itemSelectionChanged.connect(self._secildi)
        sol.addWidget(self.tablo)
        lay.addLayout(sol, 3)
        bolme = QSplitter(Qt.Horizontal)
        self.komut_metni = QPlainTextEdit(); self.komut_metni.setReadOnly(True)
        self.sonuc_metni = QPlainTextEdit(); self.sonuc_metni.setReadOnly(True)
        for baslik, w in (("Komut (JSON)", self.komut_metni), ("Sonuç (JSON)", self.sonuc_metni)):
            kutu = QWidget()
            k = QVBoxLayout(kutu)
            k.setContentsMargins(0, 0, 0, 0)
            k.addWidget(ikincil(baslik))
            k.addWidget(w)
            bolme.addWidget(kutu)
        lay.addWidget(bolme, 4)

    def yenile(self):
        g = self.oturum.gunluk
        self.tablo.blockSignals(True)
        self.tablo.setRowCount(len(g))
        for satir, kayit in enumerate(g):
            sonuc = kayit["sonuc"]
            komut_adi = kayit["komut"]["komut"] + (" (önizleme)" if kayit.get("onizleme") else "")
            degerler = [str(kayit["no"]), komut_adi, sonuc["durum"], sonuc_ozeti(sonuc)]
            for sutun, deger in enumerate(degerler):
                hucre = QTableWidgetItem(deger)
                if sutun == 2:
                    hucre.setForeground(QColor(BASARI_RENK if deger == "TAMAM" else HATA_RENK))
                if kayit.get("onizleme"):
                    hucre.setForeground(QColor("#94a3b8"))
                self.tablo.setItem(satir, sutun, hucre)
        self.tablo.blockSignals(False)
        if g:
            self.tablo.selectRow(len(g) - 1)
            self.tablo.scrollToBottom()
        else:
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
        self.setMinimumWidth(380)
        self.lay = QVBoxLayout(self)
        self.form = QFormLayout()
        self.lay.addLayout(self.form)
        self.sonuc = SonucKutusu()
        self.lay.addWidget(self.sonuc)
        alt = QHBoxLayout()
        alt.addStretch()
        vazgec = QPushButton("Vazgeç")
        vazgec.clicked.connect(self.reject)
        self.ekle = QPushButton("Ekle")
        self.ekle.setObjectName("birincil")
        self.ekle.setDefault(True)
        self.ekle.clicked.connect(self._ekle)
        alt.addWidget(vazgec)
        alt.addWidget(self.ekle)
        self.lay.addLayout(alt)
        self.eklenen_id: str | None = None

    @staticmethod
    def _onay_listesi(degerler, secili=()) -> tuple[QWidget, list[QCheckBox]]:
        kutu = QWidget()
        lay = QHBoxLayout(kutu)
        lay.setContentsMargins(0, 0, 0, 0)
        kutular = []
        for d in degerler:
            c = QCheckBox(d)
            c.setChecked(d in secili)
            lay.addWidget(c)
            kutular.append(c)
        lay.addStretch()
        return kutu, kutular

    def _sonuc_isle(self, sonuc: dict, yeni_id: str):
        if sonuc["durum"] == "TAMAM":
            self.eklenen_id = yeni_id
            self.accept()
        else:
            self.sonuc.goster(hata_html(sonuc["kod"]), False)


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
        self.form.addRow("Kimlik", self.kimlik)
        self.form.addRow("Ad", self.ad)
        self.form.addRow("Rol", self.rol)
        self.form.addRow("Sertifikalar", kutu)
        self.form.addRow("Bakiye", self.bakiye)
        self.form.addRow("Güvenilirlik", self.guven)
        self.form.addRow(ikincil("Bakiye varsayılan olarak rolün haftalık kotasıdır."))

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
        kutu, self.roller = self._onay_listesi(list(s.roller), list(s.roller))
        self.tur.currentTextChanged.connect(self._tur_degisti)
        self._tur_degisti(self.tur.currentText())
        self.form.addRow("Tür", self.tur)
        self.form.addRow("Kimlik", self.kimlik)
        self.form.addRow("Ad", self.ad)
        self.form.addRow("İzinli roller", kutu)

    def _tur_degisti(self, tur: str):
        # Aynı türdeki mevcut kimliklerin ön ekinden öneri üretir (ör. YAZ-2 -> YAZ-3).
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
