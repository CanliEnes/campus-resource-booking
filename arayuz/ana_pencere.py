"""Ana pencere: üst bar (dosya + simüle saat), kullanıcı paneli, takvim, talep
formu ve olay günlüğü tek ekranda; işlem yapmak için pencere değiştirmek gerekmez."""
import os
from datetime import datetime, timedelta

from PySide6.QtCore import QDate, QDateTime, Qt, QTime
from PySide6.QtWidgets import (QDateTimeEdit, QFileDialog, QFrame, QHBoxLayout, QLabel,
                               QMainWindow, QMessageBox, QPushButton, QScrollArea, QSplitter,
                               QVBoxLayout, QWidget)

from .oturum import Oturum
from .paneller import (GunKutusu, KullaniciPaneli, OlayGunlugu, SeciliKart, TalepFormu,
                       YeniKaynakPenceresi, YeniUyePenceresi, bolum_basligi, hata_html, ikincil)
from .stil import (BAKIM_RENK, DURUM_AD, DURUM_RENK, HAZIRLIK_RENK, olay_metni, saat_metni,
                   tarih_metni)
from .takvim import TakvimWidget


class AnaPencere(QMainWindow):
    def __init__(self, oturum: Oturum):
        super().__init__()
        self.oturum = oturum
        self.setWindowTitle("Kampüs Kaynak Rezervasyon Sistemi")
        self.resize(1500, 900)

        kok = QWidget()
        kok.setObjectName("kok")
        self.setCentralWidget(kok)
        dikey = QVBoxLayout(kok)
        dikey.setContentsMargins(0, 0, 0, 0)
        dikey.setSpacing(0)
        dikey.addWidget(self._ust_bar())

        icerik = QWidget()
        ic = QVBoxLayout(icerik)
        ic.setContentsMargins(10, 8, 10, 10)
        ic.setSpacing(8)
        dikey.addWidget(icerik, 1)

        # Saat ilerletilince oluşan olaylar, saatin hemen altında gösterilir.
        self.olay_bandi = QFrame()
        self.olay_bandi.setObjectName("olayBandi")
        bant = QHBoxLayout(self.olay_bandi)
        bant.setContentsMargins(10, 6, 6, 6)
        self.olay_metni = QLabel()
        self.olay_metni.setTextFormat(Qt.RichText)
        self.olay_metni.setWordWrap(True)
        bant.addWidget(self.olay_metni, 1)
        kapat = QPushButton("✕")
        kapat.setObjectName("kucuk")
        kapat.setFixedWidth(28)
        kapat.clicked.connect(self.olay_bandi.hide)
        bant.addWidget(kapat, 0, Qt.AlignTop)
        self.olay_bandi.hide()
        ic.addWidget(self.olay_bandi)

        self.kullanici = KullaniciPaneli(oturum)
        self.takvim = TakvimWidget(oturum)
        self.kart = SeciliKart(oturum)
        self.form = TalepFormu(oturum)
        self.gunluk = OlayGunlugu(oturum)

        yatay = QSplitter(Qt.Horizontal)
        yatay.addWidget(self.kullanici)
        yatay.addWidget(self._takvim_paneli())
        yatay.addWidget(self.form)
        yatay.setStretchFactor(1, 1)
        yatay.setSizes([350, 820, 360])
        yatay.setChildrenCollapsible(False)
        self.kullanici.setMinimumWidth(330)
        self.form.setMinimumWidth(330)

        dikey_bolme = QSplitter(Qt.Vertical)
        dikey_bolme.addWidget(yatay)
        dikey_bolme.addWidget(self.gunluk)
        dikey_bolme.setStretchFactor(0, 1)
        dikey_bolme.setSizes([640, 190])
        ic.addWidget(dikey_bolme, 1)

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
        self._gosterilen_simule_gun = None

    # ------------------------------------------------------------------
    def _ust_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("ustBar")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(14, 8, 14, 8)
        baslik = QLabel("Kampüs Kaynak Rezervasyon")
        baslik.setObjectName("baslik")
        lay.addWidget(baslik)
        lay.addSpacing(14)
        self.dosya_dugme = QPushButton("📂 Başlangıç dosyası")
        self.dosya_dugme.setToolTip("Başka bir başlangıç dosyası seç (tüm durum yeniden kurulur)")
        self.dosya_dugme.clicked.connect(lambda: self.dosya_sec())
        lay.addWidget(self.dosya_dugme)
        yeniden = QPushButton("⟳ Yeniden yükle")
        yeniden.setToolTip("Aynı dosyayı baştan yükle (dosyada değiştirdiğiniz parametreler uygulanır)")
        yeniden.clicked.connect(lambda: self.oturum.dosya and self.yukle(self.oturum.dosya))
        lay.addWidget(yeniden)
        lay.addStretch()

        saat_kutu = QVBoxLayout()
        saat_kutu.setSpacing(0)
        alt = QLabel("SİMÜLE SAAT")
        alt.setObjectName("saatAlt")
        self.saat_etiket = QLabel("—")
        self.saat_etiket.setObjectName("saatEtiket")
        saat_kutu.addWidget(alt, 0, Qt.AlignRight)
        saat_kutu.addWidget(self.saat_etiket)
        lay.addLayout(saat_kutu)
        lay.addSpacing(8)
        for metin, fark in (("+15 dk", timedelta(minutes=15)), ("+1 saat", timedelta(hours=1))):
            d = QPushButton(metin)
            d.clicked.connect(lambda _=False, f=fark: self._saat_ilerlet(self.oturum.sistem.saat + f))
            lay.addWidget(d)
        ertesi = QPushButton("Ertesi gün 08:00")
        ertesi.clicked.connect(lambda: self._saat_ilerlet(
            datetime.combine(self.oturum.sistem.saat.date() + timedelta(days=1), datetime.min.time())
            + timedelta(hours=8)))
        lay.addWidget(ertesi)
        self.saat_secici = QDateTimeEdit()
        self.saat_secici.setDisplayFormat("dd.MM.yyyy HH:mm")
        self.saat_secici.setCalendarPopup(True)
        lay.addWidget(self.saat_secici)
        git = QPushButton("İlerlet")
        git.setObjectName("ilerletDugme")
        git.clicked.connect(lambda: self._saat_ilerlet(self.saat_secici.dateTime().toPython()))
        lay.addWidget(git)
        return bar

    def _takvim_paneli(self) -> QWidget:
        kutu = QWidget()
        lay = QVBoxLayout(kutu)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        panel = QFrame()
        panel.setObjectName("panel")
        p = QVBoxLayout(panel)
        p.setContentsMargins(12, 10, 12, 6)
        ust = QHBoxLayout()
        ust.addWidget(bolum_basligi("Kaynak takvimi"))
        ust.addSpacing(10)
        onceki = QPushButton("◀")
        onceki.setObjectName("kucuk")
        sonraki = QPushButton("▶")
        sonraki.setObjectName("kucuk")
        self.gun_secici = GunKutusu()
        bugun = QPushButton("Simüle gün")
        bugun.setObjectName("kucuk")
        onceki.clicked.connect(lambda: self.gun_secici.setDate(self.gun_secici.date().addDays(-1)))
        sonraki.clicked.connect(lambda: self.gun_secici.setDate(self.gun_secici.date().addDays(1)))
        bugun.clicked.connect(self._simule_gune_git)
        self.gun_secici.dateChanged.connect(lambda d: self.takvim.gun_ayarla(d.toPython()))
        for w in (onceki, self.gun_secici, sonraki, bugun):
            ust.addWidget(w)
        ust.addStretch()
        yeni_kaynak = QPushButton("+ Yeni kaynak")
        yeni_kaynak.setObjectName("kucuk")
        yeni_kaynak.clicked.connect(self._yeni_kaynak)
        ust.addWidget(yeni_kaynak)
        p.addLayout(ust)
        p.addWidget(self._lejant())
        kaydirma = QScrollArea()
        kaydirma.setWidgetResizable(True)
        kaydirma.setWidget(self.takvim)
        p.addWidget(kaydirma, 1)
        lay.addWidget(panel, 1)
        lay.addWidget(self.kart)
        return kutu

    @staticmethod
    def _lejant() -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        for durum, (dolgu, kenar, _) in DURUM_RENK.items():
            cizgi = "dashed" if durum in ("IPTAL", "GELMEDI") else "solid"
            lay.addWidget(QLabel(f"<span style='background:{dolgu};border:1px {cizgi} {kenar};'>&nbsp;&nbsp;&nbsp;&nbsp;</span>"
                                 f" <span style='color:#475569'>{DURUM_AD[durum]}</span>"))
        lay.addWidget(QLabel(f"<span style='background:{BAKIM_RENK};'>&nbsp;&nbsp;&nbsp;&nbsp;</span>"
                             " <span style='color:#475569'>Bakım</span>"))
        lay.addWidget(QLabel(f"<span style='background:#e2e8f0;border:1px dotted {HAZIRLIK_RENK};'>&nbsp;&nbsp;&nbsp;&nbsp;</span>"
                             " <span style='color:#475569'>Hazırlık</span>"))
        lay.addWidget(QLabel("<span style='background:#fdba74;'>&nbsp;&nbsp;&nbsp;&nbsp;</span>"
                             " <span style='color:#475569'>Pik saat</span>"))
        lay.addStretch()
        for etiket in w.findChildren(QLabel):
            etiket.setTextFormat(Qt.RichText)
        return w

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
            QMessageBox.critical(self, "Dosya okunamadı", f"{yol}\n\n{hata}")
            return False
        return True

    def _yuklendi(self):
        s = self.oturum.sistem
        self.dosya_dugme.setText(f"📂 {os.path.basename(self.oturum.dosya)}")
        self.olay_bandi.hide()
        self.form.sifirla()
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
        self.gun_secici.setDate(QDate(g.year, g.month, g.day))
        self.takvim.gun_ayarla(g)

    # ------------------------------------------------------------------
    def _saat_ilerlet(self, yeni: datetime):
        sonuc = self.oturum.saat(yeni.strftime("%Y-%m-%dT%H:%M"))
        if sonuc["durum"] == "RED":
            self.olay_metni.setText(hata_html(sonuc["kod"]))
        else:
            olaylar = sonuc["olaylar"]
            baslik = f"<b>Saat {saat_metni(yeni)}'e ilerletildi</b> — "
            if olaylar:
                self.olay_metni.setText(baslik + f"{len(olaylar)} olay:<br>"
                                        + "<br>".join(f"• {olay_metni(o)}" for o in olaylar))
            else:
                self.olay_metni.setText(baslik + "bu aralıkta olay yok.")
        self.olay_bandi.show()

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
        if pencere.exec():
            self.form.kaynaklari_yenile()
            self.takvim.yenile()
