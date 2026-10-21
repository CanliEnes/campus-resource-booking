"""Tema: açık/koyu renk takımları, stil sayfası ve çizilmiş (SVG) ikonlar.

Renkler tek yerde tanımlanır; arayüzün geri kalanı `aktif()` ile o anki
takımı okur. Tema değişince `yonetici.degisti` sinyali yayılır.
"""
import os
import tempfile

from PySide6.QtCore import QByteArray, QObject, QSettings, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

# ---------------------------------------------------------------------------
# Renk takımları
# ---------------------------------------------------------------------------
ACIK = {
    "ad": "acik",
    "zemin": "#f3f2f8", "yuzey": "#ffffff", "yuzey2": "#f8f7fc", "yuzey3": "#efedf7",
    "cizgi": "#e5e3ef", "cizgi_guclu": "#d2cfe2",
    "yazi": "#17152b", "yazi2": "#55526f", "yazi3": "#6f6b8a",
    "vurgu": "#5b4bdb", "vurgu_uzeri": "#4a3ac8", "vurgu_yumusak": "#ece9fd", "vurgu_yazi": "#3f2fb8",
    "ust": "#1c1940", "ust2": "#2a2658", "ust_cizgi": "#3a3570", "ust_yazi": "#eeecfb", "ust_yazi2": "#b4afdb",
    "basari": "#15803d", "basari_yumusak": "#e7f6ec", "basari_cizgi": "#a7e0bb",
    "hata": "#be123c", "hata_yumusak": "#fdecf0", "hata_cizgi": "#f6b4c3",
    "bilgi_yumusak": "#f1effd", "bilgi_cizgi": "#d6d0fa",
    "simdi": "#e11d48", "pik": "#f59e0b",
    "gecmis": (23, 21, 43, 14), "satir_alt": "#faf9fd",
    "izgara_saat": "#d9d6e6", "izgara_yarim": "#e9e7f1", "izgara_ceyrek": "#f2f1f7",
    "bakim": "#77738f", "hazirlik": "#a29ebb",
    "durum": {
        "ONAYLI":     ("#5b4bdb", "#4a3ac8", "#ffffff"),
        "KULLANIMDA": ("#087f58", "#06694a", "#ffffff"),
        "TAMAMLANDI": ("#e9e7f0", "#bdb9cf", "#454160"),
        "IPTAL":      ("#fdecf0", "#ec7d96", "#9f1239"),
        "GELMEDI":    ("#fff3dc", "#e5a13c", "#7c4306"),
    },
}

KOYU = {
    "ad": "koyu",
    "zemin": "#0e0d18", "yuzey": "#17152a", "yuzey2": "#1c1a32", "yuzey3": "#24213e",
    "cizgi": "#2a2744", "cizgi_guclu": "#3b3760",
    "yazi": "#eceaf8", "yazi2": "#b3b0cc", "yazi3": "#908cad",
    "vurgu": "#6d5ce8", "vurgu_uzeri": "#7e6ff0", "vurgu_yumusak": "#2b2654", "vurgu_yazi": "#c9c1ff",
    "ust": "#0a0914", "ust2": "#17152a", "ust_cizgi": "#2a2744", "ust_yazi": "#eceaf8", "ust_yazi2": "#9d99bd",
    "basari": "#4ade80", "basari_yumusak": "#132a1f", "basari_cizgi": "#24573b",
    "hata": "#fb7194", "hata_yumusak": "#2e1520", "hata_cizgi": "#6b2840",
    "bilgi_yumusak": "#1f1c3c", "bilgi_cizgi": "#3b3570",
    "simdi": "#fb7185", "pik": "#f5a524",
    "gecmis": (0, 0, 0, 60), "satir_alt": "#1a182e",
    "izgara_saat": "#35315a", "izgara_yarim": "#2a2746", "izgara_ceyrek": "#211e38",
    "bakim": "#8f8bb0", "hazirlik": "#6f6b93",
    "durum": {
        "ONAYLI":     ("#6d5ce8", "#8b7cf6", "#ffffff"),
        "KULLANIMDA": ("#0a7f58", "#2bb98a", "#ffffff"),
        "TAMAMLANDI": ("#26233f", "#47436a", "#c9c6de"),
        "IPTAL":      ("#34172a", "#e6688a", "#ffb3c6"),
        "GELMEDI":    ("#33270f", "#d99a37", "#ffd28a"),
    },
}

_TEMALAR = {"acik": ACIK, "koyu": KOYU}


class _Yonetici(QObject):
    degisti = Signal()

    def __init__(self):
        super().__init__()
        self._ayar = QSettings("KampusRezervasyon", "Arayuz")
        self.renk = _TEMALAR.get(self._ayar.value("tema", "acik"), ACIK)
        self.animasyon = self._ayar.value("animasyon", True, type=bool)

    def ayarla(self, ad: str):
        self.renk = _TEMALAR[ad]
        self._ayar.setValue("tema", ad)
        self.degisti.emit()

    def degistir(self):
        self.ayarla("koyu" if self.renk["ad"] == "acik" else "acik")

    def animasyon_ayarla(self, acik: bool):
        self.animasyon = acik
        self._ayar.setValue("animasyon", acik)


yonetici = _Yonetici()


def aktif() -> dict:
    return yonetici.renk


def renk(anahtar: str) -> QColor:
    return QColor(yonetici.renk[anahtar])


# ---------------------------------------------------------------------------
# İkonlar (Lucide çizgi ikonları; 24x24, 2px çizgi)
# ---------------------------------------------------------------------------
_YOLLAR = {
    "klasor": '<path d="m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2"/>',
    "yenile": '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
    "sol": '<path d="m15 18-6-6 6-6"/>',
    "sag": '<path d="m9 18 6-6-6-6"/>',
    "asagi": '<path d="m6 9 6 6 6-6"/>',
    "yukari": '<path d="m18 15-6-6-6 6"/>',
    "kapat": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "arti": '<path d="M5 12h14"/><path d="M12 5v14"/>',
    "tamam": '<path d="M20 6 9 17l-5-5"/>',
    "hata": '<circle cx="12" cy="12" r="10"/><path d="M12 8v4"/><path d="M12 16h.01"/>',
    "gunes": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>',
    "ay": '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
    "saat": '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    "ileri": '<path d="m13 19 9-7-9-7z"/><path d="m2 19 9-7-9-7z"/>',
    "giris": '<path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><path d="m10 17 5-5-5-5"/><path d="M15 12H3"/>',
    "cikis": '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/>',
    "iptal": '<circle cx="12" cy="12" r="10"/><path d="m4.9 4.9 14.2 14.2"/>',
    "uye": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M19 8v6"/><path d="M22 11h-6"/>',
    "katman": '<path d="M12 3 2 8l10 5 10-5-10-5Z"/><path d="m2 16 10 5 10-5"/><path d="m2 12 10 5 10-5"/>',
    "kum": '<path d="M5 22h14"/><path d="M5 2h14"/><path d="M17 22v-4.172a2 2 0 0 0-.586-1.414L12 12l-4.414 4.414A2 2 0 0 0 7 17.828V22"/><path d="M7 2v4.172a2 2 0 0 0 .586 1.414L12 12l4.414-4.414A2 2 0 0 0 17 6.172V2"/>',
    "takvim": '<rect width="18" height="18" x="3" y="4" rx="2"/><path d="M16 2v4"/><path d="M8 2v4"/><path d="M3 10h18"/>',
    "bilgi": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
}


def _svg(ad: str, renk_kodu: str, kalinlik: float = 2) -> bytes:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
            f'fill="none" stroke="{renk_kodu}" stroke-width="{kalinlik}" stroke-linecap="round" '
            f'stroke-linejoin="round">{_YOLLAR[ad]}</svg>').encode()


def ikon_pixmap(ad: str, renk_kodu: str, boyut: int = 16) -> QPixmap:
    oran = 2  # yüksek DPI ekranlarda keskin görünsün
    pm = QPixmap(boyut * oran, boyut * oran)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    QSvgRenderer(QByteArray(_svg(ad, renk_kodu))).render(p)
    p.end()
    pm.setDevicePixelRatio(oran)
    return pm


def ikon(ad: str, renk_anahtari: str = "yazi2", boyut: int = 16) -> QIcon:
    return QIcon(ikon_pixmap(ad, yonetici.renk[renk_anahtari], boyut))


def _ikon_dosyasi(ad: str, renk_kodu: str) -> str:
    """Stil sayfası url() ile dosya ister; ikonlar geçici klasöre yazılır."""
    klasor = os.path.join(tempfile.gettempdir(), "kampus_rezervasyon_ikon")
    os.makedirs(klasor, exist_ok=True)
    yol = os.path.join(klasor, f"{ad}_{renk_kodu.lstrip('#')}.svg")
    if not os.path.exists(yol):
        with open(yol, "wb") as f:
            f.write(_svg(ad, renk_kodu, 2.4))
    return yol.replace("\\", "/")


# ---------------------------------------------------------------------------
# Stil sayfası
# ---------------------------------------------------------------------------
def stil_sayfasi() -> str:
    t = yonetici.renk
    asagi = _ikon_dosyasi("asagi", t["yazi2"])
    yukari = _ikon_dosyasi("yukari", t["yazi2"])
    tik = _ikon_dosyasi("tamam", "#ffffff")
    sol = _ikon_dosyasi("sol", t["yazi"])
    sag = _ikon_dosyasi("sag", t["yazi"])
    return f"""
* {{ outline: none; }}
QWidget {{ font-family: 'Segoe UI'; font-size: 9.5pt; color: {t['yazi']}; }}
QMainWindow, #kok, QDialog {{ background: {t['zemin']}; }}
#panel {{ background: {t['yuzey']}; border: 1px solid {t['cizgi']}; border-radius: 10px; }}
QLabel {{ background: transparent; }}

/* Üst bar */
#ustBar {{ background: {t['ust']}; border-bottom: 1px solid {t['ust_cizgi']}; }}
#ustBar QLabel {{ color: {t['ust_yazi']}; }}
#baslik {{ font-size: 11.5pt; font-weight: 600; }}
#saatEtiket {{ font-size: 14pt; font-weight: 600; }}
#saatAlt {{ color: {t['ust_yazi2']}; font-size: 8pt; letter-spacing: 0.5px; }}
#ustBar QPushButton, #ustBar QToolButton {{ background: {t['ust2']}; color: {t['ust_yazi']};
    border: 1px solid {t['ust_cizgi']}; border-radius: 6px; padding: 5px 11px; }}
#ustBar QPushButton:hover, #ustBar QToolButton:hover {{ background: {t['ust_cizgi']}; }}
#ustBar QPushButton:pressed {{ background: {t['ust']}; }}
#ustBar QPushButton#ilerletDugme {{ background: {t['vurgu']}; border-color: {t['vurgu']}; color: #ffffff; font-weight: 600; }}
#ustBar QPushButton#ilerletDugme:hover {{ background: {t['vurgu_uzeri']}; }}
#ustBar QDateTimeEdit {{ background: {t['ust2']}; color: {t['ust_yazi']}; border: 1px solid {t['ust_cizgi']};
    border-radius: 6px; padding: 4px 8px; }}
#ustBar QDateTimeEdit::drop-down {{ border: none; width: 20px; }}
#ustBar QDateTimeEdit::down-arrow {{ image: url({_ikon_dosyasi("asagi", t["ust_yazi2"])}); width: 11px; height: 11px; }}
QToolButton::menu-button {{ border: none; width: 16px; }}
QToolButton::menu-arrow {{ image: url({_ikon_dosyasi("asagi", t["ust_yazi2"])}); width: 10px; height: 10px; }}

/* Bilgi bandı ve sonuç kutuları */
#olayBandi {{ background: {t['bilgi_yumusak']}; border: 1px solid {t['bilgi_cizgi']}; border-radius: 8px; }}
#sonucKutusu {{ border-radius: 8px; border: 1px solid {t['cizgi']}; background: {t['yuzey2']}; }}
#sonucKutusu[tur="tamam"] {{ background: {t['basari_yumusak']}; border-color: {t['basari_cizgi']}; }}
#sonucKutusu[tur="hata"] {{ background: {t['hata_yumusak']}; border-color: {t['hata_cizgi']}; }}
#sonucBaslik {{ font-weight: 600; }}
#sonucKutusu[tur="tamam"] #sonucBaslik {{ color: {t['basari']}; }}
#sonucKutusu[tur="hata"] #sonucBaslik {{ color: {t['hata']}; }}
#sonucMetin {{ color: {t['yazi2']}; }}

#bolumBaslik {{ font-weight: 600; font-size: 10.5pt; }}
#ikincil {{ color: {t['yazi3']}; font-size: 8.5pt; }}
#etiket {{ color: {t['yazi2']}; }}
#buyukDeger {{ font-size: 15pt; font-weight: 600; }}
#birim {{ color: {t['yazi3']}; font-size: 9pt; }}
#fiyat {{ font-size: 13pt; font-weight: 600; color: {t['vurgu_yazi']}; }}
#fiyat[tur="hata"] {{ font-size: 9.5pt; font-weight: 600; color: {t['hata']}; }}
#fiyat[tur="bos"] {{ font-size: 9pt; font-weight: 400; color: {t['yazi3']}; }}
#kalemDurum[tur="tamam"] {{ color: {t['basari']}; font-weight: 600; }}
#kalemDurum[tur="hata"] {{ color: {t['hata']}; font-weight: 600; }}
#kalemDurum[tur="fiyat"] {{ color: {t['yazi2']}; }}
#durumHap {{ border-radius: 9px; padding: 1px 9px; font-size: 8.5pt; font-weight: 600; }}
#kalem {{ border: 1px solid transparent; border-radius: 8px; }}
#kalem[aktif="true"] {{ background: {t['vurgu_yumusak']}; border-color: {t['bilgi_cizgi']}; }}

/* Düğmeler */
QPushButton {{ background: {t['yuzey']}; border: 1px solid {t['cizgi_guclu']}; border-radius: 6px;
    padding: 6px 12px; color: {t['yazi']}; }}
QPushButton:hover {{ background: {t['yuzey3']}; }}
QPushButton:pressed {{ background: {t['cizgi']}; }}
QPushButton:focus {{ border-color: {t['vurgu']}; }}
QPushButton:disabled {{ color: {t['yazi3']}; background: {t['yuzey2']}; border-color: {t['cizgi']}; }}
QPushButton#birincil {{ background: {t['vurgu']}; color: #ffffff; border-color: {t['vurgu']}; font-weight: 600; }}
QPushButton#birincil:hover {{ background: {t['vurgu_uzeri']}; border-color: {t['vurgu_uzeri']}; }}
QPushButton#hayalet {{ background: transparent; border-color: transparent; color: {t['yazi2']}; }}
QPushButton#hayalet:hover {{ background: {t['yuzey3']}; color: {t['yazi']}; }}
QPushButton#tehlike {{ color: {t['hata']}; }}
QPushButton#kucuk {{ padding: 3px 9px; }}
QPushButton#ikonDugme {{ padding: 4px; min-width: 22px; }}

/* Girdi alanları */
QComboBox, QDateEdit, QSpinBox, QLineEdit {{ background: {t['yuzey']}; border: 1px solid {t['cizgi_guclu']};
    border-radius: 6px; padding: 4px 8px; min-height: 20px; color: {t['yazi']};
    selection-background-color: {t['vurgu']}; selection-color: #ffffff; }}
QComboBox:hover, QDateEdit:hover, QSpinBox:hover, QLineEdit:hover {{ border-color: {t['yazi3']}; }}
QComboBox:focus, QDateEdit:focus, QSpinBox:focus, QLineEdit:focus {{ border-color: {t['vurgu']}; }}
QComboBox::drop-down, QDateEdit::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow, QDateEdit::down-arrow {{ image: url({asagi}); width: 11px; height: 11px; }}
QComboBox QAbstractItemView {{ background: {t['yuzey']}; border: 1px solid {t['cizgi_guclu']};
    selection-background-color: {t['vurgu_yumusak']}; selection-color: {t['yazi']}; outline: none; padding: 4px; }}
QSpinBox::up-button, QSpinBox::down-button {{ border: none; width: 18px; }}
QSpinBox::up-arrow {{ image: url({yukari}); width: 10px; height: 10px; }}
QSpinBox::down-arrow {{ image: url({asagi}); width: 10px; height: 10px; }}
QCheckBox {{ spacing: 6px; }}
QCheckBox::indicator {{ width: 15px; height: 15px; border-radius: 4px; border: 1px solid {t['cizgi_guclu']}; background: {t['yuzey']}; }}
QCheckBox::indicator:hover {{ border-color: {t['vurgu']}; }}
QCheckBox::indicator:checked {{ background: {t['vurgu']}; border-color: {t['vurgu']}; image: url({tik}); }}

/* Açılır takvim */
QCalendarWidget QWidget {{ alternate-background-color: {t['yuzey2']}; }}
QCalendarWidget QWidget#qt_calendar_navigationbar {{ background: {t['yuzey2']}; border-bottom: 1px solid {t['cizgi']}; }}
QCalendarWidget QToolButton {{ color: {t['yazi']}; background: transparent; border: none; padding: 4px 8px; font-weight: 600; }}
QCalendarWidget QToolButton:hover {{ background: {t['yuzey3']}; border-radius: 5px; }}
QCalendarWidget QToolButton#qt_calendar_prevmonth {{ qproperty-icon: url({sol}); }}
QCalendarWidget QToolButton#qt_calendar_nextmonth {{ qproperty-icon: url({sag}); }}
QCalendarWidget QAbstractItemView {{ background: {t['yuzey']}; color: {t['yazi']};
    selection-background-color: {t['vurgu']}; selection-color: #ffffff; outline: none; }}
QCalendarWidget QAbstractItemView:disabled {{ color: {t['yazi3']}; }}
QCalendarWidget QSpinBox {{ min-height: 18px; }}
QCalendarWidget QMenu {{ background: {t['yuzey']}; }}

/* Tablolar */
QTableWidget {{ background: {t['yuzey']}; border: none; gridline-color: transparent;
    selection-background-color: {t['vurgu_yumusak']}; selection-color: {t['yazi']}; outline: none; }}
QTableWidget::item {{ padding: 0 4px; border-bottom: 1px solid {t['izgara_ceyrek']}; }}
QHeaderView {{ background: {t['yuzey']}; }}
QHeaderView::section {{ background: {t['yuzey']}; border: none; border-bottom: 1px solid {t['cizgi']};
    padding: 5px 6px; color: {t['yazi3']}; font-weight: 600; font-size: 8.5pt; }}
QTableCornerButton::section {{ background: {t['yuzey']}; border: none; }}

/* Sekmeler */
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ padding: 7px 14px; border: none; color: {t['yazi3']}; background: transparent;
    border-bottom: 2px solid transparent; }}
QTabBar::tab:hover {{ color: {t['yazi']}; }}
QTabBar::tab:selected {{ color: {t['vurgu_yazi']}; border-bottom: 2px solid {t['vurgu']}; font-weight: 600; }}

QPlainTextEdit {{ font-family: Consolas, 'Cascadia Mono', monospace; font-size: 9pt; background: {t['yuzey2']};
    border: 1px solid {t['cizgi']}; border-radius: 8px; padding: 4px; color: {t['yazi']};
    selection-background-color: {t['vurgu']}; selection-color: #ffffff; }}
QProgressBar {{ border: none; background: {t['yuzey3']}; border-radius: 3px; max-height: 6px; min-height: 6px; }}
QProgressBar::chunk {{ border-radius: 3px; background: {t['vurgu']}; }}
QProgressBar[tur="iyi"]::chunk {{ background: {t['basari']}; }}
QProgressBar[tur="dusuk"]::chunk {{ background: {t['hata']}; }}
QSplitter::handle {{ background: transparent; }}
QSplitter::handle:hover {{ background: {t['cizgi']}; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}

/* Kaydırma çubukları */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle {{ background: {t['cizgi_guclu']}; border-radius: 3px; min-height: 24px; min-width: 24px; }}
QScrollBar::handle:hover {{ background: {t['yazi3']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* Menü ve ipucu */
QMenu {{ background: {t['yuzey']}; border: 1px solid {t['cizgi_guclu']}; border-radius: 8px; padding: 4px; }}
QMenu::item {{ padding: 6px 14px 6px 10px; border-radius: 5px; color: {t['yazi']}; }}
QMenu::item:selected {{ background: {t['vurgu_yumusak']}; color: {t['yazi']}; }}
QMenu::separator {{ height: 1px; background: {t['cizgi']}; margin: 4px 6px; }}
QMenu::indicator {{ width: 14px; height: 14px; }}
QToolTip {{ background: {t['yuzey']}; color: {t['yazi']}; border: 1px solid {t['cizgi_guclu']};
    border-radius: 6px; padding: 6px 8px; }}
"""


def yeniden_cilala(w) -> None:
    """Dinamik özellik (ör. tur="hata") değişince stilin yeniden uygulanması için."""
    w.style().unpolish(w)
    w.style().polish(w)
