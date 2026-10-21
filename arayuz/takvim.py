"""Kaynak takvimi: seçilen gün için her kaynak bir satır, yatay eksen 08:00-22:00.

Yalnızca çizim yapar; hangi rezervasyonun geçerli olduğuna karar vermez, veriyi
modülden okur. Boş alana sürüklemek talep formunu doldurur, kutuya tıklamak
rezervasyonu seçer, sağ tık eylem menüsünü açar.

Hareket: saat ilerletildiğinde simüle saat çizgisi yeni konumuna kayar ve
geçmiş gölgesi onunla ilerler; ardından durumu değişen ya da yeni oluşan
rezervasyonlar kısa bir halkayla belirtilir.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from PySide6.QtCore import QEasingCurve, QEvent, QPointF, QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QMenu, QToolTip, QWidget

from rezervasyon.motor import (CALISMA_BASLANGIC_SAAT, CALISMA_BITIS_SAAT, DILIM_DK,
                               PIK_BASLANGIC_SAAT, PIK_BITIS_SAAT)
from . import tema
from .stil import DURUM_AD, aralik_metni, saat_metni

ETIKET_GEN = 156     # sol kaynak adı sütunu
UST = 46             # saat başlıkları + simüle saat şeridi
SERIT = 30           # bir alt satırın yüksekliği
SATIR_IC = 6         # satır iç boşluğu
SAG = 18
PASIF = ("IPTAL", "GELMEDI")


@dataclass
class Satir:
    kaynak: dict
    y: float
    h: float
    seritler: list = field(default_factory=list)   # her biri rezervasyon listesi


def _sayisal(an: datetime) -> float:
    return an.timestamp()


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
        self._uzerindeki_kutu = None
        self._onceki: dict[str, tuple] = {}
        self._vurgu: set[str] = set()
        self._bekleyen_vurgu: set[str] = set()
        self._vurgu_ilerleme = 1.0
        self._cizgi: datetime | None = None   # ekranda gösterilen simüle saat

        self._kayma = QVariantAnimation(self)
        self._kayma.setDuration(650)
        self._kayma.setEasingCurve(QEasingCurve.OutExpo)
        self._kayma.valueChanged.connect(self._kayma_adim)
        self._kayma.finished.connect(self._vurguyu_baslat)

        self._halka = QVariantAnimation(self)
        self._halka.setDuration(1100)
        self._halka.setStartValue(0.0)
        self._halka.setEndValue(1.0)
        self._halka.setEasingCurve(QEasingCurve.OutCubic)
        self._halka.valueChanged.connect(self._halka_adim)

        self.setMouseTracking(True)
        self.setMinimumWidth(600)
        f = QFont(self.font())
        try:
            f.setFeature(QFont.Tag("tnum"), 1)   # saatler hizalı dursun
        except Exception:
            pass
        self.setFont(f)

    # ------------------------------------------------------------------
    def sifirla(self) -> None:
        """Yeni dosya yüklenince: animasyon ve vurgu yok, durum anlık alınır."""
        self._kayma.stop()
        self._halka.stop()
        self._vurgu = set()
        self._bekleyen_vurgu = set()
        self._cizgi = self.oturum.sistem.saat
        self._onceki = self._durum_resmi()
        self.secili = None
        self._duzen_hesapla()
        self.update()

    def gun_ayarla(self, gun: date) -> None:
        self.gun = gun
        self._duzen_hesapla()
        self.update()

    def sec(self, rid: str | None) -> None:
        self.secili = rid
        self.update()

    def yenile(self) -> None:
        """Modülün durumu değişince çağrılır: farkları bulur, animasyonları başlatır."""
        s = self.oturum.sistem
        if s is None:
            return
        simdiki = self._durum_resmi()
        degisen = {rid for rid, deger in simdiki.items() if self._onceki.get(rid) != deger}
        self._onceki = simdiki
        self._duzen_hesapla()
        self._bekleyen_vurgu |= degisen

        if self._cizgi is None:
            self._cizgi = s.saat
        if s.saat != self._cizgi:
            ayni_gun = self._cizgi.date() == s.saat.date() == self.gun
            if tema.yonetici.animasyon and ayni_gun:
                self._kayma.stop()
                self._kayma.setStartValue(_sayisal(self._cizgi))
                self._kayma.setEndValue(_sayisal(s.saat))
                self._kayma.start()
                self.update()
                return
            self._cizgi = s.saat
        if self._kayma.state() != QVariantAnimation.Running:
            self._vurguyu_baslat()
        self.update()

    def _durum_resmi(self) -> dict[str, tuple]:
        s = self.oturum.sistem
        return {r.id: (r.durum, r.bitis) for r in s.rezervasyonlar.values()} if s else {}

    def _kayma_adim(self, deger):
        self._cizgi = datetime.fromtimestamp(deger)
        self.update()

    def _vurguyu_baslat(self):
        self._cizgi = self.oturum.sistem.saat
        if self._bekleyen_vurgu:
            self._vurgu = self._bekleyen_vurgu
            self._bekleyen_vurgu = set()
            self._halka.stop()
            self._halka.start()
        self.update()

    def _halka_adim(self, deger):
        self._vurgu_ilerleme = deger
        if deger >= 1.0:
            self._vurgu = set()
        self.update()

    # ------------------------------------------------------------------
    # Yerleşim
    # ------------------------------------------------------------------
    @property
    def _dk_basi(self) -> float:
        toplam_dk = (CALISMA_BITIS_SAAT - CALISMA_BASLANGIC_SAAT) * 60
        return max(0.3, (self.width() - ETIKET_GEN - SAG) / toplam_dk)

    def _gun_basi(self) -> datetime:
        return datetime(self.gun.year, self.gun.month, self.gun.day)

    def _x(self, an: datetime) -> float:
        bas = self._gun_basi() + timedelta(hours=CALISMA_BASLANGIC_SAAT)
        dakika = (an - bas) / timedelta(minutes=1)
        dakika = max(0, min((CALISMA_BITIS_SAAT - CALISMA_BASLANGIC_SAAT) * 60, dakika))
        return ETIKET_GEN + dakika * self._dk_basi

    def _dilim_zamani(self, dilim: int) -> datetime:
        return self._gun_basi() + timedelta(hours=CALISMA_BASLANGIC_SAAT, minutes=dilim * DILIM_DK)

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
        self.setMinimumHeight(int(y + 8))

    @staticmethod
    def _carpisir(a, b, h) -> bool:
        a_son = a.bitis + (h if a.durum not in PASIF else timedelta(0))
        b_son = b.bitis + (h if b.durum not in PASIF else timedelta(0))
        return a.baslangic < b_son and a_son > b.baslangic

    # ------------------------------------------------------------------
    # Çizim
    # ------------------------------------------------------------------
    def paintEvent(self, _):
        t = tema.aktif()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(t["yuzey"]))
        s = self.oturum.sistem
        if s is None:
            return
        if not self._satirlar and s.kaynaklar:
            self._duzen_hesapla()
        sol, sag = ETIKET_GEN, self.width() - SAG
        alt = self._satirlar[-1].y + self._satirlar[-1].h if self._satirlar else UST + 40
        gun_basi = self._gun_basi()
        cizgi = self._cizgi or s.saat

        kalin = QFont(self.font()); kalin.setWeight(QFont.DemiBold)
        kucuk = QFont(self.font()); kucuk.setPointSizeF(self.font().pointSizeF() - 1.2)

        # Satır zeminleri ve kaynak adları
        for i, satir in enumerate(self._satirlar):
            if i % 2:
                p.fillRect(QRectF(0, satir.y, self.width(), satir.h), QColor(t["satir_alt"]))
            p.setPen(QColor(t["yazi"])); p.setFont(kalin)
            p.drawText(QRectF(12, satir.y + 5, sol - 16, 18), Qt.AlignLeft | Qt.AlignVCenter, satir.kaynak["id"])
            p.setPen(QColor(t["yazi3"])); p.setFont(kucuk)
            ad = QFontMetrics(kucuk).elidedText(f"{satir.kaynak['ad']} · {satir.kaynak['tur']}",
                                                Qt.ElideRight, sol - 18)
            p.drawText(QRectF(12, satir.y + 22, sol - 16, 15), Qt.AlignLeft | Qt.AlignVCenter, ad)

        # Saat başlıkları: genişliğe göre "08:00", "08" ya da iki saatte bir
        saat_px = 60 * self._dk_basi
        p.setFont(kucuk)
        fm = QFontMetrics(kucuk)
        uzun = saat_px >= fm.horizontalAdvance("00:00") + 12
        adim = 1 if saat_px >= fm.horizontalAdvance("00") + 10 else 2
        for saat in range(CALISMA_BASLANGIC_SAAT, CALISMA_BITIS_SAAT + 1, adim):
            x = self._x(gun_basi + timedelta(hours=saat))
            p.setPen(QColor(t["yazi3"]))
            metin = f"{saat:02d}:00" if uzun else f"{saat:02d}"
            p.drawText(QRectF(x - 24, 6, 48, 16), Qt.AlignCenter, metin)

        # Pik saat şeridi
        pik_b = self._x(gun_basi + timedelta(hours=PIK_BASLANGIC_SAAT))
        pik_e = self._x(gun_basi + timedelta(hours=PIK_BITIS_SAAT))
        pik = QColor(t["pik"]); pik.setAlpha(160)
        p.fillRect(QRectF(pik_b, UST - 4, pik_e - pik_b, 3), pik)

        # Izgara: her 15 dk ince, her saat belirgin
        for dilim in range((CALISMA_BITIS_SAAT - CALISMA_BASLANGIC_SAAT) * 60 // DILIM_DK + 1):
            an = self._dilim_zamani(dilim)
            x = round(self._x(an)) + 0.5
            anahtar = "izgara_saat" if an.minute == 0 else ("izgara_yarim" if an.minute == 30 else "izgara_ceyrek")
            p.setPen(QPen(QColor(t[anahtar]), 1))
            p.drawLine(QPointF(x, UST - (6 if an.minute == 0 else 0)), QPointF(x, alt))
        p.setPen(QPen(QColor(t["cizgi"]), 1))
        for satir in self._satirlar:
            p.drawLine(QPointF(0, satir.y + satir.h - 0.5), QPointF(self.width(), satir.y + satir.h - 0.5))
        p.drawLine(QPointF(sol - 0.5, UST), QPointF(sol - 0.5, alt))

        # Geçmiş zaman gölgesi (simüle saat çizgisiyle birlikte ilerler)
        gecmis = QColor(*t["gecmis"])
        if self.gun < cizgi.date():
            p.fillRect(QRectF(sol, UST, sag - sol, alt - UST), gecmis)
        elif self.gun == cizgi.date():
            p.fillRect(QRectF(sol, UST, self._x(cizgi) - sol, alt - UST), gecmis)

        self._kutular = []
        p.setFont(self.font())
        for satir in self._satirlar:
            kid = satir.kaynak["id"]
            ic_ust = satir.y + SATIR_IC
            tum_yuk = satir.h - 2 * SATIR_IC
            # Bakım pencereleri: satırın tamamını kaplar
            for b in s.bakimlar:
                if b["kaynak"] == kid and b["baslangic"] < gun_basi + timedelta(days=1) and b["bitis"] > gun_basi:
                    r = QRectF(self._x(b["baslangic"]) + 1, ic_ust,
                               self._x(b["bitis"]) - self._x(b["baslangic"]) - 2, tum_yuk)
                    renk = QColor(t["bakim"])
                    zemin = QColor(renk); zemin.setAlpha(28)
                    p.setPen(Qt.NoPen); p.setBrush(zemin); p.drawRoundedRect(r, 5, 5)
                    p.setPen(QPen(renk, 1)); p.setBrush(QBrush(renk, Qt.BDiagPattern))
                    p.drawRoundedRect(r, 5, 5)
                    p.setPen(QColor(t["yazi2"])); p.setFont(kalin)
                    if r.width() > 46:
                        p.drawText(r, Qt.AlignCenter, "Bakım")
                    p.setFont(self.font())
            # Hazırlık süreleri: ilgili rezervasyonun ardından, ilk alt satırda
            for bas, bit in s.hazirlik_araliklari(kid, self.gun):
                r = QRectF(self._x(bas), ic_ust + 4, self._x(bit) - self._x(bas), SERIT - 8)
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(QColor(t["hazirlik"]), Qt.Dense6Pattern))
                p.drawRoundedRect(r.adjusted(1, 0, 0, 0), 3, 3)
            # Rezervasyon kutuları
            for sira, serit in enumerate(satir.seritler):
                for rez in serit:
                    self._kutu_ciz(p, rez, QRectF(self._x(rez.baslangic) + 1.5, ic_ust + sira * SERIT + 1.5,
                                                  self._x(rez.bitis) - self._x(rez.baslangic) - 3, SERIT - 3))

        # Sürükleme seçimi ya da fare altındaki 15 dakikalık hücre
        vurgu = QColor(t["vurgu"])
        if self._surukle:
            i, d1, d2 = self._surukle
            satir = self._satirlar[i]
            a, b = min(d1, d2), max(d1, d2) + 1
            r = QRectF(self._x(self._dilim_zamani(a)), satir.y + 3,
                       self._x(self._dilim_zamani(b)) - self._x(self._dilim_zamani(a)), satir.h - 6)
            dolgu = QColor(vurgu); dolgu.setAlpha(40)
            p.setPen(QPen(vurgu, 1.5, Qt.DashLine)); p.setBrush(dolgu)
            p.drawRoundedRect(r, 5, 5)
            p.setPen(QColor(t["vurgu_yazi"])); p.setFont(kalin)
            p.drawText(r, Qt.AlignCenter, f"{saat_metni(self._dilim_zamani(a))}–{saat_metni(self._dilim_zamani(b))}")
            p.setFont(self.font())
        elif self._uzerinde and not self._uzerindeki_kutu:
            i, d = self._uzerinde
            satir = self._satirlar[i]
            r = QRectF(self._x(self._dilim_zamani(d)), satir.y + 1, DILIM_DK * self._dk_basi, satir.h - 2)
            dolgu = QColor(vurgu); dolgu.setAlpha(28)
            p.fillRect(r, dolgu)

        # Simüle saat çizgisi ve etiketi (başlıkla çakışmasın diye ayrı şeritte)
        if self.gun == cizgi.date():
            x = self._x(cizgi)
            simdi = QColor(t["simdi"])
            p.setPen(QPen(simdi, 2))
            p.drawLine(QPointF(x, UST - 4), QPointF(x, alt))
            p.setFont(kucuk)
            metin = saat_metni(cizgi)
            gen = QFontMetrics(kucuk).horizontalAdvance(metin) + 14
            etiket = QRectF(min(max(x - gen / 2, sol), sag - gen), 24, gen, 17)
            p.setPen(Qt.NoPen); p.setBrush(simdi)
            p.drawRoundedRect(etiket, 8.5, 8.5)
            p.setPen(QColor("#ffffff"))
            p.drawText(etiket, Qt.AlignCenter, metin)
        p.end()

    def _kutu_ciz(self, p: QPainter, rez, r: QRectF) -> None:
        t = tema.aktif()
        dolgu, kenar, yazi = t["durum"].get(rez.durum, (t["yuzey3"], t["cizgi_guclu"], t["yazi"]))
        dolgu, kenar = QColor(dolgu), QColor(kenar)
        secili = rez.id == self.secili
        if rez.id == self._uzerindeki_kutu:
            dolgu = dolgu.lighter(110) if t["ad"] == "acik" else dolgu.lighter(125)

        # Seçili kutuya yumuşak gölge: aşağı kaymış, kenarı dağılan katmanlar
        if secili:
            for kat, alfa in ((4, 16), (3, 22), (2, 30)):
                p.setPen(Qt.NoPen); p.setBrush(QColor(0, 0, 0, alfa))
                p.drawRoundedRect(r.adjusted(-kat + 2, kat, kat - 2, kat + 1), 6, 6)

        p.setPen(QPen(kenar, 1, Qt.DashLine if rez.durum in PASIF else Qt.SolidLine))
        p.setBrush(dolgu)
        p.drawRoundedRect(r, 5, 5)
        if secili:
            p.setPen(QPen(QColor(t["yazi"]), 2))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(r.adjusted(-1.5, -1.5, 1.5, 1.5), 6, 6)

        # Değişiklik halkası: büyüyerek söner (animasyon kapalıysa yalnızca söner)
        if rez.id in self._vurgu:
            ilerleme = self._vurgu_ilerleme
            buyume = 1 + (7 * ilerleme if tema.yonetici.animasyon else 2)
            halka = QColor(t["vurgu"] if rez.durum not in PASIF else kenar)
            halka.setAlphaF(max(0.0, 0.85 * (1 - ilerleme)))
            p.setPen(QPen(halka, 2)); p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(r.adjusted(-buyume, -buyume, buyume, buyume), 5 + buyume, 5 + buyume)

        self._kutular.append((r, rez.id))
        fm = QFontMetrics(self.font())
        metin = f"{rez.id} · {rez.kullanici}"
        if rez.paket:
            metin += f" · {rez.paket}"
        if r.width() > fm.horizontalAdvance(metin + "  00:00–00:00") + 14:
            metin += f"  {saat_metni(rez.baslangic)}–{saat_metni(rez.bitis)}"
        elif r.width() < fm.horizontalAdvance(metin) + 12:
            metin = rez.id
        metin = fm.elidedText(metin, Qt.ElideRight, int(r.width() - 10))
        f = QFont(self.font())
        f.setStrikeOut(rez.durum == "IPTAL")
        f.setWeight(QFont.DemiBold if rez.durum in ("ONAYLI", "KULLANIMDA") else QFont.Normal)
        p.setFont(f)
        p.setPen(QColor(yazi))
        p.drawText(r.adjusted(6, 0, -4, 0), Qt.AlignLeft | Qt.AlignVCenter, metin)
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
        kutu = self._kutu_bul(pos)
        if yeni != self._uzerinde or kutu != self._uzerindeki_kutu:
            self._uzerinde, self._uzerindeki_kutu = yeni, kutu
            self.update()
        self.setCursor(Qt.PointingHandCursor if kutu else (Qt.CrossCursor if yeni else Qt.ArrowCursor))

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
        bit = min(self._dilim_zamani(b), self._gun_basi() + timedelta(hours=CALISMA_BITIS_SAAT))
        self.aralik_secildi.emit(self._satirlar[i].kaynak["id"], bas, bit)

    def leaveEvent(self, _):
        self._uzerinde = None
        self._uzerindeki_kutu = None
        self.update()

    def event(self, e):
        if e.type() == QEvent.Type.ToolTip:
            rid = self._kutu_bul(QPointF(e.pos()))
            if rid:
                r = self.oturum.sistem.rezervasyonlar[rid]
                kul = self.oturum.sistem.kullanicilar.get(r.kullanici, {})
                metin = (f"<b>{r.id}</b> · {DURUM_AD.get(r.durum, r.durum)}<br>"
                         f"{r.kullanici} {kul.get('ad', '')}<br>{r.kaynak} · {aralik_metni(r.baslangic, r.bitis)}"
                         f"<br>Ücret: {r.ucret} KP" + (f"<br>Paket: {r.paket}" if r.paket else "")
                         + "<br><i>Sağ tık: giriş, çıkış, iptal</i>")
                QToolTip.showText(e.globalPos(), metin, self)
            else:
                QToolTip.hideText()
            return True
        return super().event(e)

    def _eylem_menusu(self, rid: str, konum) -> None:
        menu = QMenu(self)
        for eylem, ad in (("giris", "Giriş yap"), ("cikis", "Çıkış yap"), ("iptal", "İptal et")):
            menu.addAction(tema.ikon(eylem), ad, lambda e=eylem: self.eylem_istendi.emit(e, rid))
        menu.exec(konum)
