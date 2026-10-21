"""Ana pencere: üst bar (dosya + simüle saat), kullanıcı paneli, takvim, talep
formu ve olay günlüğü tek ekranda; işlem yapmak için pencere değiştirmek gerekmez."""
import os
from datetime import datetime, timedelta

from PySide6.QtCore import QDate, QDateTime, QEasingCurve, QPropertyAnimation, QRectF, Qt, QTime, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (QApplication, QDateTimeEdit, QFileDialog, QFrame, QHBoxLayout,
                               QLabel, QMainWindow, QMenu, QMessageBox, QPushButton, QScrollArea,
                               QSizePolicy, QSplitter, QToolButton, QVBoxLayout, QWidget)

from . import tema
from .oturum import Oturum
from .paneller import (GunKutusu, KullaniciPaneli, OlayGunlugu, SeciliKart, TalepFormu,
                       YeniKaynakPenceresi, YeniUyePenceresi, bolum_basligi, ikincil, ikonla,
                       ikonlari_yenile)
from .stil import DURUM_AD, olay_metni, saat_metni, tarih_metni
from .takvim import TakvimWidget


class Lejant(QWidget):
    """Takvim açıklaması; örnekler takvimdeki kutularla aynı biçimde çizilir."""

    OGELER = [("durum", d) for d in DURUM_AD] + [("bakim", "Bakım"), ("hazirlik", "Hazırlık"), ("pik", "Pik saat")]

    def __init__(self):
        super().__init__()
        self.setFixedHeight(20)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        tema.yonetici.degisti.connect(self.update)

    def paintEvent(self, _):
        t = tema.aktif()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        f = QFont(self.font()); f.setPointSizeF(self.font().pointSizeF() - 0.8)
        p.setFont(f)
        fm = QFontMetrics(f)
        x = 0.0
        for tur, deger in self.OGELER:
            r = QRectF(x, 4, 22, 12)
            if tur == "durum":
                dolgu, kenar, _ = t["durum"][deger]
                p.setPen(QPen(QColor(kenar), 1, Qt.DashLine if deger in ("IPTAL", "GELMEDI") else Qt.SolidLine))
                p.setBrush(QColor(dolgu))
                p.drawRoundedRect(r, 3, 3)
                ad = DURUM_AD[deger]
            elif tur == "bakim":
                renk = QColor(t["bakim"])
                p.setPen(QPen(renk, 1)); p.setBrush(QBrush(renk, Qt.BDiagPattern))
                p.drawRoundedRect(r, 3, 3)
                ad = deger
            elif tur == "hazirlik":
                p.setPen(Qt.NoPen); p.setBrush(QBrush(QColor(t["hazirlik"]), Qt.Dense6Pattern))
                p.drawRoundedRect(r, 3, 3)
                ad = deger
            else:
                p.fillRect(QRectF(x, 8.5, 22, 3), QColor(t["pik"]))
                ad = deger
            p.setPen(QColor(t["yazi2"]))
            p.drawText(QRectF(x + 27, 0, 120, 20), Qt.AlignLeft | Qt.AlignVCenter, ad)
            x += 27 + fm.horizontalAdvance(ad) + 16
            if x > self.width():
                break
        p.end()


class AnaPencere(QMainWindow):
    def __init__(self, oturum: Oturum):
        super().__init__()
        self.oturum = oturum
        self.setWindowTitle("Kampüs Kaynak Rezervasyon Sistemi")
        self.resize(1500, 900)
        self.setMinimumSize(1240, 700)

        kok = QWidget()
        kok.setObjectName("kok")
        self.setCentralWidget(kok)
        dikey = QVBoxLayout(kok)
        dikey.setContentsMargins(0, 0, 0, 0)
        dikey.setSpacing(0)
        dikey.addWidget(self._ust_bar())

        icerik = QWidget()
        ic = QVBoxLayout(icerik)
        ic.setContentsMargins(12, 10, 12, 12)
        ic.setSpacing(10)
        dikey.addWidget(icerik, 1)

        ic.addWidget(self._olay_bandi())

        self.kullanici = KullaniciPaneli(oturum)
        self.takvim = TakvimWidget(oturum)
        self.kart = SeciliKart(oturum)
        self.form = TalepFormu(oturum)
        self.gunluk = OlayGunlugu(oturum)

        yatay = QSplitter(Qt.Horizontal)
        yatay.setHandleWidth(10)
        yatay.addWidget(self.kullanici)
        yatay.addWidget(self._takvim_paneli())
        yatay.addWidget(self.form)
        yatay.setStretchFactor(1, 1)
        yatay.setSizes([340, 840, 360])
        yatay.setChildrenCollapsible(False)
        self.kullanici.setMinimumWidth(300)
        self.form.setMinimumWidth(320)

        self.dikey_bolme = QSplitter(Qt.Vertical)
        self.dikey_bolme.setHandleWidth(10)
        self.dikey_bolme.addWidget(yatay)
        self.dikey_bolme.addWidget(self.gunluk)
        self.dikey_bolme.setStretchFactor(0, 1)
        self.dikey_bolme.setChildrenCollapsible(False)
        self.dikey_bolme.setSizes([660, 170])
        ic.addWidget(self.dikey_bolme, 1)

        # Bağlantılar
        oturum.yuklendi.connect(self._yuklendi)
        oturum.degisti.connect(self._yenile)
        oturum.gunluk_eklendi.connect(self.gunluk.yenile)
        self.kullanici.kullanici_degisti.connect(self.form.kullanici_ayarla)
        self.kullanici.rezervasyon_secildi.connect(self._rezervasyon_sec)
        self.kullanici.eylem_istendi.connect(self._eylem)
        self.kullanici.yeni_uye_istendi.connect(self._yeni_uye)
        self.takvim.rezervasyon_secildi.connect(self._takvimden_secildi)
        self.takvim.aralik_secildi.connect(self.form.aralik_doldur)
        self.takvim.eylem_istendi.connect(self._eylem)
        self.gunluk.daraltildi.connect(self._gunluk_daraltildi)
        tema.yonetici.degisti.connect(self._tema_uygula)
        self._gosterilen_simule_gun = None
        self._tema_dugmesi_yaz()

    # ------------------------------------------------------------------
    def _ust_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("ustBar")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 9, 16, 9)
        lay.setSpacing(8)
        self.baslik = QLabel("Kampüs Kaynak Rezervasyon")
        self.baslik.setObjectName("baslik")
        lay.addWidget(self.baslik)
        lay.addSpacing(10)
        self.dosya_dugme = ikonla(QPushButton("Başlangıç dosyası"), "klasor", "ust_yazi2")
        self.dosya_dugme.setToolTip("Başka bir başlangıç dosyası seç; bütün durum o dosyaya göre yeniden kurulur")
        self.dosya_dugme.clicked.connect(lambda: self.dosya_sec())
        lay.addWidget(self.dosya_dugme)
        yeniden = ikonla(QPushButton("Yeniden yükle"), "yenile", "ust_yazi2")
        yeniden.setToolTip("Aynı dosyayı baştan yükle; dosyada değiştirdiğiniz parametreler hemen uygulanır")
        yeniden.clicked.connect(lambda: self.oturum.dosya and self.yukle(self.oturum.dosya))
        lay.addWidget(yeniden)
        lay.addStretch()

        self.saat_ikon = QLabel()
        lay.addWidget(self.saat_ikon)
        saat_kutu = QVBoxLayout()
        saat_kutu.setSpacing(0)
        alt = QLabel("SİMÜLE SAAT")
        alt.setObjectName("saatAlt")
        self.saat_etiket = QLabel("—")
        self.saat_etiket.setObjectName("saatEtiket")
        f = self.saat_etiket.font()
        try:
            f.setFeature(QFont.Tag("tnum"), 1)
        except Exception:
            pass
        self.saat_etiket.setFont(f)
        self.saat_etiket.setMinimumWidth(self.saat_etiket.fontMetrics().horizontalAdvance("Paz 28 Ağu 2027 · 00:00") + 8)
        saat_kutu.addWidget(alt)
        saat_kutu.addWidget(self.saat_etiket)
        lay.addLayout(saat_kutu)
        lay.addSpacing(10)
        for metin, fark in (("+15 dk", timedelta(minutes=15)), ("+1 saat", timedelta(hours=1))):
            d = QPushButton(metin)
            d.clicked.connect(lambda _=False, fk=fark: self._saat_ilerlet(self.oturum.sistem.saat + fk))
            lay.addWidget(d)
        ertesi = QPushButton("Ertesi gün 08:00")
        self.ertesi = ertesi
        ertesi.clicked.connect(lambda: self._saat_ilerlet(
            datetime.combine(self.oturum.sistem.saat.date() + timedelta(days=1), datetime.min.time())
            + timedelta(hours=8)))
        lay.addWidget(ertesi)
        self.saat_secici = QDateTimeEdit()
        self.saat_secici.setDisplayFormat("dd.MM.yyyy HH:mm")
        self.saat_secici.setCalendarPopup(True)
        lay.addWidget(self.saat_secici)
        git = ikonla(QPushButton("İlerlet"), "ileri", "ust_yazi")
        git.setObjectName("ilerletDugme")
        git.clicked.connect(lambda: self._saat_ilerlet(self.saat_secici.dateTime().toPython()))
        lay.addWidget(git)
        lay.addSpacing(6)

        self.tema_dugme = QToolButton()
        self.tema_dugme.setToolTip("Açık / koyu tema")
        self.tema_dugme.setPopupMode(QToolButton.MenuButtonPopup)
        self.tema_dugme.clicked.connect(tema.yonetici.degistir)
        menu = QMenu(self.tema_dugme)
        menu.addAction("Açık tema", lambda: tema.yonetici.ayarla("acik"))
        menu.addAction("Koyu tema", lambda: tema.yonetici.ayarla("koyu"))
        menu.addSeparator()
        self.animasyon_eylem = menu.addAction("Animasyonlar")
        self.animasyon_eylem.setCheckable(True)
        self.animasyon_eylem.setChecked(tema.yonetici.animasyon)
        self.animasyon_eylem.toggled.connect(tema.yonetici.animasyon_ayarla)
        self.tema_dugme.setMenu(menu)
        lay.addWidget(self.tema_dugme)
        return bar

    def _olay_bandi(self) -> QWidget:
        self.olay_bandi = QFrame()
        self.olay_bandi.setObjectName("olayBandi")
        bant = QHBoxLayout(self.olay_bandi)
        bant.setContentsMargins(12, 8, 8, 8)
        bant.setSpacing(10)
        self.olay_ikon = QLabel()
        self.olay_ikon.setFixedSize(18, 18)
        bant.addWidget(self.olay_ikon, 0, Qt.AlignTop)
        metinler = QVBoxLayout()
        metinler.setSpacing(2)
        self.olay_baslik = QLabel()
        self.olay_baslik.setObjectName("sonucBaslik")
        self.olay_metni = QLabel()
        self.olay_metni.setObjectName("sonucMetin")
        self.olay_metni.setTextFormat(Qt.RichText)
        self.olay_metni.setWordWrap(True)
        metinler.addWidget(self.olay_baslik)
        metinler.addWidget(self.olay_metni)
        bant.addLayout(metinler, 1)
        kapat = ikonla(QPushButton(), "kapat", "yazi3")
        kapat.setObjectName("hayalet")
        kapat.setFixedWidth(30)
        kapat.setToolTip("Kapat")
        kapat.clicked.connect(self._bandi_kapat)
        bant.addWidget(kapat, 0, Qt.AlignTop)
        self.olay_bandi.hide()
        self._bant_anim = QPropertyAnimation(self.olay_bandi, b"maximumHeight", self)
        self._bant_anim.setDuration(240)
        self._bant_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._bant_zamanlayici = QTimer(self)
        self._bant_zamanlayici.setSingleShot(True)
        self._bant_zamanlayici.timeout.connect(self._bandi_kapat)
        return self.olay_bandi

    def _takvim_paneli(self) -> QWidget:
        kutu = QWidget()
        lay = QVBoxLayout(kutu)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        panel = QFrame()
        panel.setObjectName("panel")
        p = QVBoxLayout(panel)
        p.setContentsMargins(14, 12, 14, 8)
        p.setSpacing(8)
        ust = QHBoxLayout()
        ust.setSpacing(6)
        ust.addWidget(bolum_basligi("Kaynak takvimi"))
        ust.addSpacing(10)
        onceki = ikonla(QPushButton(), "sol")
        onceki.setObjectName("ikonDugme")
        onceki.setToolTip("Önceki gün")
        sonraki = ikonla(QPushButton(), "sag")
        sonraki.setObjectName("ikonDugme")
        sonraki.setToolTip("Sonraki gün")
        self.gun_secici = GunKutusu()
        bugun = ikonla(QPushButton("Simüle güne dön"), "takvim")
        bugun.setObjectName("hayalet")
        onceki.clicked.connect(lambda: self.gun_secici.setDate(self.gun_secici.date().addDays(-1)))
        sonraki.clicked.connect(lambda: self.gun_secici.setDate(self.gun_secici.date().addDays(1)))
        bugun.clicked.connect(self._simule_gune_git)
        self.gun_secici.dateChanged.connect(lambda d: self.takvim.gun_ayarla(d.toPython()))
        for w in (onceki, self.gun_secici, sonraki, bugun):
            ust.addWidget(w)
        ust.addStretch()
        yeni_kaynak = ikonla(QPushButton("Yeni kaynak"), "katman")
        yeni_kaynak.setObjectName("hayalet")
        yeni_kaynak.clicked.connect(self._yeni_kaynak)
        ust.addWidget(yeni_kaynak)
        p.addLayout(ust)
        p.addWidget(Lejant())
        kaydirma = QScrollArea()
        kaydirma.setWidgetResizable(True)
        kaydirma.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        kaydirma.setWidget(self.takvim)
        p.addWidget(kaydirma, 1)
        lay.addWidget(panel, 1)
        lay.addWidget(self.kart)
        return kutu

    # ------------------------------------------------------------------
    # Tema
    # ------------------------------------------------------------------
    def resizeEvent(self, e):
        super().resizeEvent(e)
        genis = self.width() >= 1440
        self.baslik.setVisible(genis)
        self.ertesi.setText("Ertesi gün 08:00" if genis else "Ertesi gün")

    def showEvent(self, e):
        super().showEvent(e)
        # Kısa ekranlarda günlük daha az yer kaplasın, takvim büyüsün.
        toplam = sum(self.dikey_bolme.sizes())
        alt = 140 if self.height() < 820 else 180
        self.dikey_bolme.setSizes([toplam - alt, alt])

    def _tema_dugmesi_yaz(self):
        koyu = tema.aktif()["ad"] == "koyu"
        self.tema_dugme.setIcon(tema.ikon("gunes" if koyu else "ay", "ust_yazi"))
        self.tema_dugme.setToolTip("Açık temaya geç" if koyu else "Koyu temaya geç")
        self.saat_ikon.setPixmap(tema.ikon_pixmap("saat", tema.aktif()["ust_yazi2"], 20))

    def _tema_uygula(self):
        QApplication.instance().setStyleSheet(tema.stil_sayfasi())
        ikonlari_yenile()
        self._tema_dugmesi_yaz()
        self._olay_ikonu_ciz()
        if self.oturum.sistem:
            self.kullanici.yenile()
            self.takvim.update()

    # ------------------------------------------------------------------
    def dosya_sec(self, ilk: bool = False) -> str | None:
        baslangic_dizin = os.path.dirname(self.oturum.dosya) if self.oturum.dosya else os.getcwd()
        yol, _ = QFileDialog.getOpenFileName(self, "Başlangıç dosyası seç", baslangic_dizin,
                                             "JSON dosyaları (*.json);;Tüm dosyalar (*)")
        if yol and not ilk:
            self.yukle(yol)
        return yol or None

    def yukle(self, yol: str) -> bool:
        try:
            self.oturum.yukle(yol)
        except Exception as hata:  # bozuk dosya uygulamayı kapatmasın
            QMessageBox.critical(self, "Dosya okunamadı",
                                 f"{yol}\n\nDosya başlangıç dosyası biçiminde değil:\n{hata}")
            return False
        return True

    def _yuklendi(self):
        self.dosya_dugme.setText(os.path.basename(self.oturum.dosya))
        self.olay_bandi.hide()
        self.form.sifirla()
        self.takvim.sifirla()
        self.kullanici.kullanicilari_yenile()
        self.kart.goster(None)
        self._gosterilen_simule_gun = None
        self._simule_gune_git()

    def _yenile(self):
        s = self.oturum.sistem
        self.saat_etiket.setText(f"{tarih_metni(s.saat)} · {saat_metni(s.saat)}")
        self.saat_secici.setDateTime(QDateTime(QDate(s.saat.year, s.saat.month, s.saat.day),
                                               QTime(s.saat.hour, s.saat.minute)))
        # Takvim simüle günü gösteriyorsa saatle birlikte ilerler.
        if self._gosterilen_simule_gun is not None and self.takvim.gun == self._gosterilen_simule_gun:
            if s.saat.date() != self.takvim.gun:
                self._simule_gune_git()
        self._gosterilen_simule_gun = s.saat.date()
        self.form.kaynaklari_yenile()
        self.form.durum_degisti()
        self.takvim.yenile()
        self.kullanici.yenile()
        self.kullanici.rezervasyonu_sec(self.kart.rid)
        self.kart.goster(self.kart.rid, sonucu_koru=True)

    def _simule_gune_git(self):
        g = self.oturum.sistem.saat.date()
        self.gun_secici.blockSignals(True)
        self.gun_secici.setDate(QDate(g.year, g.month, g.day))
        self.gun_secici.blockSignals(False)
        self.takvim.gun_ayarla(g)

    # ------------------------------------------------------------------
    # Saat ve olay bandı
    # ------------------------------------------------------------------
    def _saat_ilerlet(self, yeni: datetime):
        sonuc = self.oturum.saat(yeni.strftime("%Y-%m-%dT%H:%M"))
        if sonuc["durum"] == "RED":
            self._bandi_goster("hata", sonuc["kod"], "Simüle saat geri alınamaz; ileri bir zaman seçin.", 6000)
            return
        olaylar = sonuc["olaylar"]
        baslik = f"Saat {tarih_metni(yeni)} {saat_metni(yeni)} oldu"
        if olaylar:
            self._bandi_goster("bilgi", f"{baslik} · {len(olaylar)} olay",
                               "&nbsp;&nbsp;<span style='opacity:.5'>|</span>&nbsp;&nbsp;".join(
                                   olay_metni(o) for o in olaylar))
        else:
            self._bandi_goster("bilgi", baslik, "Bu aralıkta olay olmadı.", 3500)

    def _olay_ikonu_ciz(self):
        t = tema.aktif()
        tur = getattr(self, "_bant_tur", "bilgi")
        ad, renk = ("hata", t["hata"]) if tur == "hata" else ("saat", t["vurgu"])
        self.olay_ikon.setPixmap(tema.ikon_pixmap(ad, renk, 18))

    def _bandi_goster(self, tur: str, baslik: str, metin: str, kendiliginden_kapan: int = 0):
        self._bant_tur = tur
        self._olay_ikonu_ciz()
        self.olay_baslik.setText(baslik)
        self.olay_metni.setText(metin)
        self._bant_zamanlayici.stop()
        if kendiliginden_kapan:
            self._bant_zamanlayici.start(kendiliginden_kapan)
        hedef = self.olay_bandi.sizeHint().height() + self.olay_metni.heightForWidth(self.width() - 120) \
            - self.olay_metni.sizeHint().height()
        hedef = max(hedef, self.olay_bandi.sizeHint().height())
        gorunur = self.olay_bandi.isVisible()
        self.olay_bandi.show()
        if tema.yonetici.animasyon and not gorunur:
            self._bant_anim.stop()
            self._bant_anim.setStartValue(0)
            self._bant_anim.setEndValue(hedef)
            self._bant_anim.finished.connect(self._bant_serbest)
            self._bant_anim.start()
        else:
            self.olay_bandi.setMaximumHeight(16777215)

    def _bant_serbest(self):
        self.olay_bandi.setMaximumHeight(16777215)
        try:
            self._bant_anim.finished.disconnect(self._bant_serbest)
        except RuntimeError:
            pass

    def _bandi_kapat(self):
        self._bant_zamanlayici.stop()
        self.olay_bandi.hide()

    # ------------------------------------------------------------------
    def _gunluk_daraltildi(self, daralti: bool):
        toplam = sum(self.dikey_bolme.sizes())
        alt = self.gunluk.sizeHint().height() if daralti else 190
        if daralti:
            self.gunluk.setMaximumHeight(alt)
        else:
            self.gunluk.setMaximumHeight(16777215)
        self.dikey_bolme.setSizes([toplam - alt, alt])

    def _rezervasyon_sec(self, rid: str):
        r = self.oturum.sistem.rezervasyonlar.get(rid)
        if not r:
            return
        g = r.baslangic.date()
        if self.takvim.gun != g:
            self.gun_secici.setDate(QDate(g.year, g.month, g.day))
        self.takvim.sec(rid)
        self.kart.goster(rid)

    def _takvimden_secildi(self, rid: str):
        self.kart.goster(rid)
        self.kullanici.rezervasyonu_sec(rid)

    def _eylem(self, eylem: str, rid: str):
        self._rezervasyon_sec(rid)
        self.kart.eylem(eylem, rid)

    def _yeni_uye(self):
        pencere = YeniUyePenceresi(self.oturum, self)
        if pencere.exec() and pencere.eklenen_id:
            self.kullanici.kullanicilari_yenile(secilecek=pencere.eklenen_id)

    def _yeni_kaynak(self):
        pencere = YeniKaynakPenceresi(self.oturum, self)
        pencere.exec()
