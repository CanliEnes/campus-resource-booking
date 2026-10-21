"""Renkler, stil sayfası ve metin biçimlendirme yardımcıları (yalnızca görünüm)."""
from datetime import datetime

from rezervasyon.mesajlar import aciklama

# Durum renkleri: (dolgu, kenar, yazı)
DURUM_RENK = {
    "ONAYLI":     ("#3b82f6", "#1d4ed8", "#ffffff"),
    "KULLANIMDA": ("#16a34a", "#15803d", "#ffffff"),
    "TAMAMLANDI": ("#cbd5e1", "#94a3b8", "#334155"),
    "IPTAL":      ("#fee2e2", "#f87171", "#991b1b"),
    "GELMEDI":    ("#fef3c7", "#f59e0b", "#92400e"),
}
DURUM_AD = {
    "ONAYLI": "Onaylı", "KULLANIMDA": "Kullanımda", "TAMAMLANDI": "Tamamlandı",
    "IPTAL": "İptal", "GELMEDI": "Gelmedi",
}
BAKIM_RENK = "#64748b"
HAZIRLIK_RENK = "#94a3b8"
SIMDI_RENK = "#ef4444"
ANA_RENK = "#2563eb"
BASARI_RENK = "#15803d"
HATA_RENK = "#b91c1c"

GUNLER = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
AYLAR = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]


def tarih_metni(an) -> str:
    return f"{GUNLER[an.weekday()]} {an.day} {AYLAR[an.month - 1]} {an.year}"


def saat_metni(an: datetime) -> str:
    return an.strftime("%H:%M")


def aralik_metni(b: datetime, e: datetime) -> str:
    return f"{b.day} {AYLAR[b.month - 1]} {saat_metni(b)}–{saat_metni(e)}"


def zaman_metinden(metin: str) -> str:
    """'2027-03-08T11:00' -> '8 Mar 11:00' (metin bozuksa olduğu gibi)."""
    try:
        an = datetime.strptime(metin, "%Y-%m-%dT%H:%M")
    except (TypeError, ValueError):
        return str(metin)
    return f"{an.day} {AYLAR[an.month - 1]} {saat_metni(an)}"


def hata_html(kod: str) -> str:
    return f"<b style='color:{HATA_RENK}'>✗ {kod}</b><br><span style='color:#475569'>{aciklama(kod)}</span>"


def olay_metni(olay: dict) -> str:
    z = zaman_metinden(olay.get("zaman"))
    tur = olay.get("tur")
    if tur == "GELMEDI":
        return f"{z} · {olay['rezervasyon']} GELMEDİ — {olay['kullanici']} güvenilirlik {olay['guvenilirlik']}"
    if tur == "TAMAMLANDI":
        return f"{z} · {olay['rezervasyon']} TAMAMLANDI — {olay['kullanici']} güvenilirlik {olay['guvenilirlik']}"
    if tur == "OTOMATIK_ATAMA":
        return (f"{z} · Bekleme {olay['bekleme']} → {olay['rezervasyon']} otomatik atandı — "
                f"{olay['kullanici']}, {olay['ucret']} KP, bakiye {olay['bakiye']}")
    if tur == "HAFTALIK_SIFIRLAMA":
        return f"{z} · Haftalık kota yenilendi"
    return f"{z} · {tur}"


def sonuc_ozeti(sonuc: dict) -> str:
    """Olay günlüğündeki tek satırlık özet."""
    if sonuc.get("durum") == "RED":
        return sonuc.get("kod", "")
    k = sonuc.get("komut")
    if k == "rezervasyon":
        return f"{sonuc['rezervasyon_id']} · {sonuc['ucret']} KP · bakiye {sonuc['bakiye']}"
    if k == "paket":
        return (f"{sonuc['paket_id']} [{', '.join(sonuc['rezervasyonlar'])}] · "
                f"{sonuc['toplam']} KP · bakiye {sonuc['bakiye']}")
    if k == "fiyat":
        return f"{sonuc['ucret']} KP"
    if k == "iptal":
        return f"iade {sonuc['iade']} · bakiye {sonuc['bakiye']} · güv {sonuc['guvenilirlik']}" + (
            f" · {len(sonuc['olaylar'])} olay" if sonuc["olaylar"] else "")
    if k == "giris":
        return sonuc["yeni_durum"]
    if k == "cikis":
        return f"{sonuc['yeni_durum']} · güv {sonuc['guvenilirlik']}" + (
            f" · {len(sonuc['olaylar'])} olay" if sonuc["olaylar"] else "")
    if k == "bekleme":
        return f"{sonuc['bekleme_id']} · sıra {sonuc['sira']}"
    if k == "saat":
        return f"{len(sonuc['olaylar'])} olay"
    if k == "sorgu":
        return "sorgu"
    return ""


STIL = f"""
QWidget {{ font-family: 'Segoe UI'; font-size: 9.5pt; color: #0f172a; }}
QMainWindow, #kok {{ background: #f1f5f9; }}
#panel {{ background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; }}
#ustBar {{ background: #0f172a; }}
#ustBar QLabel {{ color: #e2e8f0; }}
#baslik {{ font-size: 12pt; font-weight: 600; color: #ffffff; }}
#saatEtiket {{ font-size: 13pt; font-weight: 600; color: #ffffff; padding: 0 6px; }}
#saatAlt {{ color: #94a3b8; font-size: 8.5pt; }}
#ustBar QPushButton {{ background: #1e293b; color: #e2e8f0; border: 1px solid #334155;
    border-radius: 5px; padding: 4px 10px; }}
#ustBar QPushButton:hover {{ background: #334155; }}
#ustBar QPushButton#ilerletDugme {{ background: {ANA_RENK}; border-color: {ANA_RENK}; color: white; font-weight: 600; }}
#ustBar QDateTimeEdit {{ background: #1e293b; color: #f8fafc; border: 1px solid #334155;
    border-radius: 5px; padding: 3px 6px; }}
#olayBandi {{ background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 6px; }}
#olayBandi QLabel {{ color: #1e3a8a; }}
#bolumBaslik {{ font-weight: 600; font-size: 10pt; color: #0f172a; }}
#ikincil {{ color: #64748b; font-size: 8.5pt; }}
#buyukDeger {{ font-size: 15pt; font-weight: 600; }}
QPushButton {{ background: #ffffff; border: 1px solid #cbd5e1; border-radius: 5px; padding: 5px 10px; }}
QPushButton:hover {{ background: #f8fafc; border-color: #94a3b8; }}
QPushButton:pressed {{ background: #e2e8f0; }}
QPushButton#birincil {{ background: {ANA_RENK}; color: white; border-color: {ANA_RENK}; font-weight: 600; }}
QPushButton#birincil:hover {{ background: #1d4ed8; }}
QPushButton#tehlike {{ color: {HATA_RENK}; }}
QPushButton#kucuk {{ padding: 2px 8px; }}
QComboBox, QDateEdit, QSpinBox, QLineEdit {{ background: #ffffff; border: 1px solid #cbd5e1;
    border-radius: 5px; padding: 3px 6px; min-height: 20px; }}
QComboBox:focus, QDateEdit:focus, QSpinBox:focus, QLineEdit:focus {{ border-color: {ANA_RENK}; }}
QTableWidget {{ background: #ffffff; border: none; gridline-color: #f1f5f9;
    selection-background-color: #dbeafe; selection-color: #0f172a; }}
QHeaderView::section {{ background: #f8fafc; border: none; border-bottom: 1px solid #e2e8f0;
    padding: 4px 6px; color: #475569; font-weight: 600; font-size: 8.5pt; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ padding: 6px 14px; border: none; color: #64748b; }}
QTabBar::tab:selected {{ color: {ANA_RENK}; border-bottom: 2px solid {ANA_RENK}; font-weight: 600; }}
QPlainTextEdit {{ font-family: Consolas, monospace; font-size: 9pt; background: #f8fafc;
    border: 1px solid #e2e8f0; border-radius: 5px; }}
QProgressBar {{ border: none; background: #e2e8f0; border-radius: 3px; max-height: 6px; }}
QProgressBar::chunk {{ border-radius: 3px; background: {ANA_RENK}; }}
QSplitter::handle {{ background: transparent; }}
QScrollArea {{ border: none; background: transparent; }}
#sonucKutusu {{ border-radius: 6px; padding: 2px; }}
"""
