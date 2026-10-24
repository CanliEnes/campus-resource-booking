"""Arayüzün renk, yazı tipi ve metin sabitleri. İş kuralı içermez."""

import sys
import tkinter as tk
from tkinter import ttk

ZEMIN = "#EEF2F6"
PANEL = "#FFFFFF"
KENAR = "#E2E8F0"
KENAR_KOYU = "#CBD5E1"
METIN = "#0F172A"
SOLUK = "#64748B"
VURGU = "#2563EB"
VURGU_KOYU = "#1D4ED8"
UST_ZEMIN = "#0F172A"
UST_METIN = "#E2E8F0"
SAAT_RENGI = "#E11D48"
BASARI = "#15803D"
HATA = "#B91C1C"
UYARI = "#B45309"

# Durum -> (dolgu, çerçeve, yazı, kesikli mi)
DURUM_STILI = {
    "ONAYLI": ("#3B82F6", "#1D4ED8", "#FFFFFF", False),
    "KULLANIMDA": ("#16A34A", "#166534", "#FFFFFF", False),
    "TAMAMLANDI": ("#CBD5E1", "#94A3B8", "#1E293B", False),
    "IPTAL": ("#FEE2E2", "#EF4444", "#991B1B", True),
    "GELMEDI": ("#FFEDD5", "#F97316", "#9A3412", True),
}
DURUM_ADI = {
    "ONAYLI": "Onaylı",
    "KULLANIMDA": "Kullanımda",
    "TAMAMLANDI": "Tamamlandı",
    "IPTAL": "İptal",
    "GELMEDI": "Gelmedi",
}
BAKIM_STILI = ("#E2E8F0", "#64748B")
HAZIRLIK_STILI = ("#FEF3C7", "#F59E0B")

GUN_ADLARI = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
AY_ADLARI = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos",
             "Eylül", "Ekim", "Kasım", "Aralık"]

# Modülün döndürdüğü hata kodlarının Türkçe açıklamaları
KOD_ACIKLAMASI = {
    "BULUNAMADI": "Kullanıcı, kaynak veya kayıt bulunamadı.",
    "ZAMAN_ADIMI_HATASI": "Saatler 15 dakikalık adımlara (:00, :15, :30, :45) oturmalı ve bitiş başlangıçtan sonra olmalı.",
    "GECMIS_ZAMAN": "Başlangıç simüle saatten önce olamaz.",
    "CALISMA_SAATI_DISI": "Rezervasyon aynı gün içinde 08:00–22:00 arasında kalmalı.",
    "SURE_SINIRI": "Süre en az 30 dakika, en fazla rolün azami süresi kadar olabilir.",
    "ILERI_TARIH_SINIRI": "Başlangıç, rolün ileri tarih sınırını aşıyor (güvenilirlik 50'nin altındaysa sınır 1 gün).",
    "ROL_IZNI_YOK": "Kullanıcının rolü bu kaynağı rezerve edemez.",
    "SERTIFIKA_YOK": "Bu kaynak türü için gereken sertifika kullanıcıda yok.",
    "BAKIM": "İstenen aralık bir bakım penceresiyle çakışıyor.",
    "KESISME": "İstenen aralık başka bir rezervasyonla kesişiyor.",
    "HAZIRLIK_IHLALI": "Kaynağın hazırlık süresi (soğuma / havalandırma) ihlal ediliyor.",
    "ARDISIK_KULLANIM": "Aynı kaynaktaki iki rezervasyonunuz arasında en az 60 dakika olmalı.",
    "BAKIYE_YETERSIZ": "Bakiye ücreti karşılamıyor.",
    "PAKET_BOYUTU": "Paket 2 ile 4 arasında kalem içermeli.",
    "GUVENILIRLIK_DUSUK": "Güvenilirlik 50'nin altında; paket rezervasyon yapılamaz.",
    "PAKET_RED": "Paketteki en az bir kalem doğrulamadan geçemedi.",
    "PAKET_ICI_KESISME": "Paketteki aynı kaynağa ait kalemler kesişiyor ya da hazırlık / ardışık kullanım kuralını ihlal ediyor.",
    "DURUM_HATASI": "Rezervasyon bu işlem için uygun durumda değil.",
    "GIRIS_PENCERESI_DISI": "Giriş yalnızca başlangıçtan 10 dk önce ile 15 dk sonra arasında yapılabilir.",
    "BEKLEME_GEREKSIZ": "Talep zaten geçerli; bekleme kaydına gerek yok, doğrudan rezervasyon yapabilirsiniz.",
    "SAAT_GERI": "Simüle saat geri alınamaz.",
    "ID_MEVCUT": "Bu kimlikle bir kayıt zaten var.",
    "TANIMSIZ_DEGER": "Rol, tür veya izinli rollerden biri başlangıç dosyasında tanımlı değil.",
    "GECERSIZ_DEGER": "Değer geçersiz (bakiye 0 ile rol kotası arasında, güvenilirlik 0–100 arasında tam sayı olmalı).",
    "BILINMEYEN_KOMUT": "Komut tanınmadı.",
}

YAZI = "Segoe UI" if sys.platform == "win32" else "Helvetica"
MONO = "Consolas" if sys.platform == "win32" else "Courier"


def aciklama(kod: str) -> str:
    return KOD_ACIKLAMASI.get(kod, kod)


def gun_basligi(gun) -> str:
    return f"{gun.day} {AY_ADLARI[gun.month - 1]} {gun.year}, {GUN_ADLARI[gun.weekday()]}"


class Olcek:
    """Yüksek DPI ekranlarda piksel ölçülerini büyütür."""

    oran = 1.0

    @classmethod
    def ayarla(cls, kok: tk.Tk):
        cls.oran = max(1.0, kok.winfo_fpixels("1i") / 96.0)


def S(deger: float) -> int:
    return int(round(deger * Olcek.oran))


def stilleri_kur(kok: tk.Tk):
    Olcek.ayarla(kok)
    kok.configure(bg=ZEMIN)
    st = ttk.Style(kok)
    st.theme_use("clam")
    st.configure(".", font=(YAZI, 9), background=PANEL, foreground=METIN,
                 bordercolor=KENAR, lightcolor=PANEL, darkcolor=PANEL, focuscolor=VURGU)
    st.configure("TFrame", background=PANEL)
    st.configure("Zemin.TFrame", background=ZEMIN)
    st.configure("TLabel", background=PANEL, foreground=METIN)
    st.configure("Soluk.TLabel", foreground=SOLUK, font=(YAZI, 8))
    st.configure("Bolum.TLabel", foreground=SOLUK, font=(YAZI, 8, "bold"))
    st.configure("Baslik.TLabel", font=(YAZI, 12, "bold"))
    st.configure("Buyuk.TLabel", font=(YAZI, 18, "bold"))
    st.configure("Kalin.TLabel", font=(YAZI, 9, "bold"))
    st.configure("TButton", padding=(S(10), S(4)), background="#F1F5F9", bordercolor=KENAR_KOYU,
                 relief="flat", font=(YAZI, 9))
    st.map("TButton", background=[("pressed", "#CBD5E1"), ("active", "#E2E8F0")])
    st.configure("Vurgu.TButton", background=VURGU, foreground="#FFFFFF", bordercolor=VURGU,
                 font=(YAZI, 9, "bold"))
    st.map("Vurgu.TButton", background=[("pressed", "#1E40AF"), ("active", VURGU_KOYU)])
    st.configure("Kucuk.TButton", padding=(S(6), S(2)), font=(YAZI, 8))
    st.configure("Ust.TButton", background="#1E293B", foreground=UST_METIN, bordercolor="#334155",
                 padding=(S(8), S(3)))
    st.map("Ust.TButton", background=[("pressed", "#475569"), ("active", "#334155")])
    st.configure("Ust.TCombobox", fieldbackground="#1E293B", foreground="#FFFFFF",
                 background="#334155", arrowcolor=UST_METIN, bordercolor="#334155")
    st.map("Ust.TCombobox", fieldbackground=[("readonly", "#1E293B")],
           foreground=[("readonly", "#FFFFFF")])
    st.configure("TCombobox", padding=S(3), arrowsize=S(12))
    st.configure("TEntry", padding=S(3))
    st.configure("Treeview", rowheight=S(22), background=PANEL, fieldbackground=PANEL,
                 bordercolor=KENAR, font=(YAZI, 9))
    st.map("Treeview", background=[("selected", "#DBEAFE")], foreground=[("selected", METIN)])
    st.configure("Treeview.Heading", background="#F8FAFC", foreground=SOLUK,
                 font=(YAZI, 8, "bold"), relief="flat", bordercolor=KENAR)
    st.configure("Segment.Toolbutton", padding=(S(14), S(4)), background="#F1F5F9",
                 font=(YAZI, 9))
    st.map("Segment.Toolbutton", background=[("selected", VURGU), ("active", "#E2E8F0")],
           foreground=[("selected", "#FFFFFF")])
    st.configure("TCheckbutton", background=PANEL)
    st.configure("TRadiobutton", background=PANEL)
    st.configure("TPanedwindow", background=ZEMIN)
    st.configure("Vertical.TScrollbar", arrowsize=S(12))
    kok.option_add("*TCombobox*Listbox.font", (YAZI, 9))
