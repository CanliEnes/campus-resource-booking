"""Kaynak takvimi: seçilen gün için her kaynak bir satır, yatay eksen 08:00-22:00.

Yalnızca çizim yapar. Hangi rezervasyonun geçerli olduğuna karar vermez;
veriyi modülden okur. Boş alana sürükleyerek aralık seçmek talep formunu
doldurur, bir kutuya tıklamak rezervasyonu seçer, sağ tık eylem menüsü açar.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QMenu, QToolTip, QWidget

from rezervasyon.motor import CALISMA_BASLANGIC_SAAT, CALISMA_BITIS_SAAT, DILIM_DK, PIK_BASLANGIC_SAAT, PIK_BITIS_SAAT
from .stil import (BAKIM_RENK, DURUM_AD, DURUM_RENK, HAZIRLIK_RENK, SIMDI_RENK, ANA_RENK,
                   aralik_metni, saat_metni)

ETIKET_GEN = 150     # sol kaynak adı sütunu
UST = 30             # saat başlıkları
SERIT = 30           # bir alt satırın yüksekliği
SATIR_IC = 5         # satır iç boşluğu
SAG = 26

PASIF = ("IPTAL", "GELMEDI")


@dataclass
class Satir:
    kaynak: dict
    y: float
    h: float
    seritler: list = field(default_factory=list)   # her biri rezervasyon listesi


class TakvimWidget(QWidget):
    rezervasyon_secildi = Signal(str)
    aralik_secildi = Signal(str, object, object)    # kaynak_id, baslangic, bitis
    eylem_istendi = Signal(str, str)                # "giris"/"cikis"/"iptal", rezervasyon_id

    def __init__(self, oturum, parent=None):
        super().__init__(parent)
        self.oturum = oturum
        self.gun: date = date.today()
        self.secili: str | None = None
        self._satirlar: list[Satir] = []
        self._kutular: list[tuple[QRectF, str]] = []
        self._surukle = None          # (satir_indeksi, ilk_dilim, son_dilim)
        self._uzerinde = None         # (satir_indeksi, dilim)
        self.setMouseTracking(True)
        self.setMinimumWidth(640)

    # ------------------------------------------------------------------
    def gun_ayarla(self, gun: date) -> None:
        self.gun = gun
        self.yenile()

    def sec(self, rid: str | None) -> None:
        self.secili = rid
        self.update()

    def yenile(self) -> None:
        self._duzen_hesapla()
        self.update()

    # ------------------------------------------------------------------
    # Yerleşim
    # ------------------------------------------------------------------
    @property
    def _dk_basi(self) -> float:
        toplam_dk = (CALISMA_BITIS_SAAT - CALISMA_BASLANGIC_SAAT) * 60
        return max(0.3, (self.width() - ETIKET_GEN - SAG) / toplam_dk)

    def _x(self, an: datetime) -> float:
        bas = datetime(self.gun.year, self.gun.month, self.gun.day, CALISMA_BASLANGIC_SAAT)
        dakika = (an - bas) / timedelta(minutes=1)
        dakika = max(0, min((CALISMA_BITIS_SAAT - CALISMA_BASLANGIC_SAAT) * 60, dakika))
        return ETIKET_GEN + dakika * self._dk_basi

    def _dilim_zamani(self, dilim: int) -> datetime:
        return (datetime(self.gun.year, self.gun.month, self.gun.day, CALISMA_BASLANGIC_SAAT)
                + timedelta(minutes=dilim * DILIM_DK))

    def _dilim(self, x: float) -> int:
        en_cok = (CALISMA_BITIS_SAAT - CALISMA_BASLANGIC_SAAT) * 60 // DILIM_DK - 1
        return int(max(0, min(en_cok, (x - ETIKET_GEN) / self._dk_basi // DILIM_DK)))

    def _duzen_hesapla(self) -> None:
        self._satirlar = []
        s = self.oturum.sistem
        if s is None:
            return
        y = UST
        for kaynak in s.kaynaklar.values():
            h_dk = timedelta(minutes=s.turler[kaynak["tur"]].get("hazirlik_dk", 0))
            gunun = [r for r in s.rezervasyonlar.values()
                     if r.kaynak == kaynak["id"] and r.baslangic.date() == self.gun]
            # Aktifler önce ilk alt satıra; İPTAL/GELMEDİ çakışırsa yeni alt satıra iner.
            gunun.sort(key=lambda r: (r.durum in PASIF, r.baslangic, r.no))
            seritler: list[list] = []
            for r in gunun:
                for serit in seritler:
                    if all(not self._carpisir(r, o, h_dk) for o in serit):
                        serit.append(r)
                        break
                else:
                    seritler.append([r])
            adet = max(1, len(seritler))
            yuk = adet * SERIT + 2 * SATIR_IC
            self._satirlar.append(Satir(kaynak, y, yuk, seritler))
            y += yuk
        self.setMinimumHeight(int(y + 6))

    @staticmethod
    def _carpisir(a, b, h) -> bool:
        a_son = a.bitis + (h if a.durum not in PASIF else timedelta(0))
        b_son = b.bitis + (h if b.durum not in PASIF else timedelta(0))
        return a.baslangic < b_son and a_son > b.baslangic

    # ------------------------------------------------------------------
    # Çizim
    # ------------------------------------------------------------------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#ffffff"))
        s = self.oturum.sistem
        if s is None:
            return
        if not self._satirlar and s.kaynaklar:
            self._duzen_hesapla()
        sol, sag = ETIKET_GEN, self.width() - SAG
        alt = self._satirlar[-1].y + self._satirlar[-1].h if self._satirlar else UST + 40
        gun_basi = datetime(self.gun.year, self.gun.month, self.gun.day)

        # Pik saat şeridi (başlıkta ince turuncu çizgi)
        p.fillRect(QRectF(self._x(gun_basi + timedelta(hours=PIK_BASLANGIC_SAAT)), UST - 4,
                          self._x(gun_basi + timedelta(hours=PIK_BITIS_SAAT))
                          - self._x(gun_basi + timedelta(hours=PIK_BASLANGIC_SAAT)), 3),
                   QColor("#fdba74"))

        # Satır zeminleri ve etiketler
        kalin = QFont(self.font()); kalin.setBold(True)
        kucuk = QFont(self.font()); kucuk.setPointSizeF(self.font().pointSizeF() - 1)
        for i, satir in enumerate(self._satirlar):
            if i % 2:
                p.fillRect(QRectF(0, satir.y, self.width(), satir.h), QColor("#f8fafc"))
            p.setPen(QColor("#0f172a")); p.setFont(kalin)
            p.drawText(QRectF(10, satir.y + 3, sol - 14, 18), Qt.AlignLeft | Qt.AlignVCenter,
                       satir.kaynak["id"])
            p.setPen(QColor("#64748b")); p.setFont(kucuk)
            ad = QFontMetrics(kucuk).elidedText(f"{satir.kaynak['ad']} · {satir.kaynak['tur']}",
                                                Qt.ElideRight, sol - 14)
            p.drawText(QRectF(10, satir.y + 19, sol - 14, 16), Qt.AlignLeft | Qt.AlignVCenter, ad)
        p.setFont(self.font())

        # Izgara: her 15 dk ince, her saat belirgin
        for dilim in range((CALISMA_BITIS_SAAT - CALISMA_BASLANGIC_SAAT) * 60 // DILIM_DK + 1):
            an = self._dilim_zamani(dilim)
            x = self._x(an)
            if an.minute == 0:
                p.setPen(QPen(QColor("#cbd5e1"), 1))
                p.drawLine(QPointF(x, UST - 6), QPointF(x, alt))
                p.setPen(QColor("#475569"))
                p.drawText(QRectF(x - 20, 4, 40, 18), Qt.AlignCenter, saat_metni(an))
            else:
                renk = "#e2e8f0" if an.minute == 30 else "#f1f5f9"
                p.setPen(QPen(QColor(renk), 1))
                p.drawLine(QPointF(x, UST), QPointF(x, alt))
        p.setPen(QPen(QColor("#e2e8f0"), 1))
        for satir in self._satirlar:
            p.drawLine(QPointF(0, satir.y + satir.h), QPointF(self.width(), satir.y + satir.h))
        p.drawLine(QPointF(sol, UST), QPointF(sol, alt))

        # Geçmiş zaman gölgesi
        if self.gun < s.saat.date():
            p.fillRect(QRectF(sol, UST, sag - sol, alt - UST), QColor(15, 23, 42, 12))
        elif self.gun == s.saat.date():
            p.fillRect(QRectF(sol, UST, self._x(s.saat) - sol, alt - UST), QColor(15, 23, 42, 12))

        self._kutular = []
        for i, satir in enumerate(self._satirlar):
            kid = satir.kaynak["id"]
            ic_ust = satir.y + SATIR_IC
            tum_yuk = satir.h - 2 * SATIR_IC
            # Bakım pencereleri: satırın tamamını kaplar
            for b in s.bakimlar:
                if b["kaynak"] == kid and b["baslangic"] < gun_basi + timedelta(days=1) and b["bitis"] > gun_basi:
                    r = QRectF(self._x(b["baslangic"]), ic_ust, self._x(b["bitis"]) - self._x(b["baslangic"]), tum_yuk)
                    p.setPen(QPen(QColor(BAKIM_RENK), 1))
                    p.setBrush(QBrush(QColor(BAKIM_RENK), Qt.BDiagPattern))
                    p.drawRoundedRect(r, 4, 4)
                    p.setPen(QColor("#334155"))
                    p.drawText(r, Qt.AlignCenter, "Bakım")
            # Hazırlık süreleri: ilgili rezervasyonun ardından, ilk alt satırda
            for bas, bit in s.hazirlik_araliklari(kid, self.gun):
                r = QRectF(self._x(bas), ic_ust + 3, self._x(bit) - self._x(bas), SERIT - 6)
                p.setPen(QPen(QColor(HAZIRLIK_RENK), 1, Qt.DotLine))
                p.setBrush(QBrush(QColor(HAZIRLIK_RENK), Qt.Dense6Pattern))
                p.drawRect(r)
            # Rezervasyon kutuları
            for sira, serit in enumerate(satir.seritler):
                for rez in serit:
                    self._kutu_ciz(p, rez, QRectF(self._x(rez.baslangic) + 1, ic_ust + sira * SERIT + 1,
                                                  self._x(rez.bitis) - self._x(rez.baslangic) - 2, SERIT - 2))

        # Fare altındaki 15 dakikalık hücre ve sürükleme seçimi
        if self._surukle:
            i, d1, d2 = self._surukle
            satir = self._satirlar[i]
            a, b = min(d1, d2), max(d1, d2) + 1
            r = QRectF(self._x(self._dilim_zamani(a)), satir.y + 2,
                       self._x(self._dilim_zamani(b)) - self._x(self._dilim_zamani(a)), satir.h - 4)
            renk = QColor(ANA_RENK); renk.setAlpha(45)
            p.setPen(QPen(QColor(ANA_RENK), 1.5, Qt.DashLine)); p.setBrush(renk)
            p.drawRoundedRect(r, 4, 4)
            p.setPen(QColor("#1e3a8a"))
            p.drawText(r, Qt.AlignCenter, f"{saat_metni(self._dilim_zamani(a))}–{saat_metni(self._dilim_zamani(b))}")
        elif self._uzerinde:
            i, d = self._uzerinde
            satir = self._satirlar[i]
            r = QRectF(self._x(self._dilim_zamani(d)), satir.y + 1, DILIM_DK * self._dk_basi, satir.h - 2)
            renk = QColor(ANA_RENK); renk.setAlpha(25)
            p.fillRect(r, renk)

        # Simüle saat çizgisi
        if self.gun == s.saat.date():
            x = self._x(s.saat)
            p.setPen(QPen(QColor(SIMDI_RENK), 2))
            p.drawLine(QPointF(x, UST - 6), QPointF(x, alt))
            etiket = QRectF(x - 22, UST - 17, 44, 15)
            p.setPen(Qt.NoPen); p.setBrush(QColor(SIMDI_RENK))
            p.drawRoundedRect(etiket, 3, 3)
            p.setPen(QColor("white")); p.setFont(kucuk)
            p.drawText(etiket, Qt.AlignCenter, saat_metni(s.saat))
        p.end()

    def _kutu_ciz(self, p: QPainter, rez, r: QRectF) -> None:
        dolgu, kenar, yazi = DURUM_RENK.get(rez.durum, ("#e2e8f0", "#94a3b8", "#0f172a"))
        secili = rez.id == self.secili
        p.setPen(QPen(QColor("#0f172a") if secili else QColor(kenar), 2.2 if secili else 1,
                      Qt.DashLine if rez.durum in PASIF else Qt.SolidLine))
        p.setBrush(QColor(dolgu))
        p.drawRoundedRect(r, 4, 4)
        self._kutular.append((r, rez.id))
        p.setPen(QColor(yazi))
        metin = f"{rez.id} · {rez.kullanici}"
        if rez.paket:
            metin += f" · {rez.paket}"
        if r.width() > QFontMetrics(self.font()).horizontalAdvance(metin + " 00:00–00:00 ") + 10:
            metin += f"  {saat_metni(rez.baslangic)}–{saat_metni(rez.bitis)}"
        metin = QFontMetrics(self.font()).elidedText(metin, Qt.ElideRight, int(r.width() - 8))
        f = QFont(self.font()); f.setStrikeOut(rez.durum == "IPTAL")
        p.setFont(f)
        p.drawText(r.adjusted(5, 0, -3, 0), Qt.AlignLeft | Qt.AlignVCenter, metin)
        p.setFont(self.font())

    # ------------------------------------------------------------------
    # Fare
    # ------------------------------------------------------------------
    def _kutu_bul(self, pos) -> str | None:
        for r, rid in reversed(self._kutular):
            if r.contains(pos):
                return rid
        return None

    def _satir_bul(self, y: float) -> int | None:
        for i, satir in enumerate(self._satirlar):
            if satir.y <= y < satir.y + satir.h:
                return i
        return None

    def mousePressEvent(self, e):
        pos = e.position()
        rid = self._kutu_bul(pos)
        if rid:
            self.secili = rid
            self.update()
            self.rezervasyon_secildi.emit(rid)
            if e.button() == Qt.RightButton:
                self._eylem_menusu(rid, e.globalPosition().toPoint())
            return
        i = self._satir_bul(pos.y())
        if i is not None and pos.x() >= ETIKET_GEN and e.button() == Qt.LeftButton:
            d = self._dilim(pos.x())
            self._surukle = (i, d, d)
            self.update()

    def mouseMoveEvent(self, e):
        pos = e.position()
        if self._surukle:
            i, d1, _ = self._surukle
            self._surukle = (i, d1, self._dilim(pos.x()))
            self.update()
            return
        i = self._satir_bul(pos.y())
        yeni = (i, self._dilim(pos.x())) if i is not None and pos.x() >= ETIKET_GEN else None
        if yeni != self._uzerinde:
            self._uzerinde = yeni
            self.update()
        self.setCursor(Qt.PointingHandCursor if self._kutu_bul(pos) else Qt.ArrowCursor)

    def mouseReleaseEvent(self, e):
        if not self._surukle:
            return
        i, d1, d2 = self._surukle
        self._surukle = None
        self.update()
        a, b = min(d1, d2), max(d1, d2) + 1
        if a == b - 1:  # tek tıklama: varsayılan 1 saat
            b = a + 60 // DILIM_DK
        bas = self._dilim_zamani(a)
        bit = min(self._dilim_zamani(b),
                  datetime(self.gun.year, self.gun.month, self.gun.day, CALISMA_BITIS_SAAT))
        self.aralik_secildi.emit(self._satirlar[i].kaynak["id"], bas, bit)

    def leaveEvent(self, _):
        self._uzerinde = None
        self.update()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.update()

    def event(self, e):
        if e.type() == QEvent.Type.ToolTip:
            rid = self._kutu_bul(QPointF(e.pos()))
            if rid:
                r = self.oturum.sistem.rezervasyonlar[rid]
                kul = self.oturum.sistem.kullanicilar.get(r.kullanici, {})
                metin = (f"<b>{r.id}</b> · {DURUM_AD.get(r.durum, r.durum)}<br>"
                         f"{r.kullanici} {kul.get('ad', '')}<br>{r.kaynak} · {aralik_metni(r.baslangic, r.bitis)}"
                         f"<br>Ücret: {r.ucret} KP" + (f"<br>Paket: {r.paket}" if r.paket else ""))
                QToolTip.showText(e.globalPos(), metin, self)
            else:
                i = self._satir_bul(e.pos().y())
                if i is not None and e.pos().x() >= ETIKET_GEN:
                    an = self._dilim_zamani(self._dilim(e.pos().x()))
                    QToolTip.showText(e.globalPos(), f"{self._satirlar[i].kaynak['id']} · {saat_metni(an)}"
                                      " — sürükleyerek aralık seçin", self)
                else:
                    QToolTip.hideText()
            return True
        return super().event(e)

    def _eylem_menusu(self, rid: str, konum) -> None:
        menu = QMenu(self)
        for eylem, ad in (("giris", "Giriş yap"), ("cikis", "Çıkış yap"), ("iptal", "İptal et")):
            menu.addAction(ad, lambda e=eylem: self.eylem_istendi.emit(e, rid))
        menu.exec(konum)
