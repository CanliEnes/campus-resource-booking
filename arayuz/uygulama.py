"""Masaüstü uygulaması.

Arayüz iş kuralı içermez: her işlem rezervasyon modülündeki ilgili komut metodu
çağrılarak yapılır, sonuç olduğu gibi gösterilir. Geçersiz bir talep de modüle
gönderilir; reddi ve kodunu modül verir.
"""

import json
import sys
import tkinter as tk
from datetime import date, datetime, time, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from rezervasyon import RezervasyonSistemi, zaman_yaz

from .diyaloglar import KaynakEkle, KullaniciEkle
from .takvim import Takvim
from .tema import (BASARI, DURUM_ADI, DURUM_STILI, HATA, KENAR, METIN, MONO, PANEL, S, SOLUK,
                   UST_ZEMIN, UYARI, VURGU, YAZI, aciklama, gun_basligi, stilleri_kur)

KOK = Path(__file__).resolve().parent.parent
VARSAYILAN_DOSYA = KOK / "testler" / "01_ornek_senaryo" / "baslangic.json"
FORM_SAATLERI = [f"{s:02d}:{d:02d}" for s in range(8, 22) for d in (0, 15, 30, 45)] + ["22:00"]
TUM_SAATLER = [f"{s:02d}:{d:02d}" for s in range(24) for d in (0, 15, 30, 45)]
BEKLEMEYE_UYGUN_KODLAR = ("KESISME", "HAZIRLIK_IHLALI")


def jsonla(veri) -> str:
    return json.dumps(veri, ensure_ascii=False, separators=(",", ":"))


def olay_metni(o: dict) -> str:
    saat = o["zaman"][11:]
    if o["tur"] == "OTOMATIK_ATAMA":
        return (f"{saat}  {o['bekleme']} → {o['rezervasyon']} otomatik atandı "
                f"({o['kullanici']}, {o['ucret']} KP, bakiye {o['bakiye']})")
    if o["tur"] == "HAFTALIK_SIFIRLAMA":
        return f"{o['zaman'][:10]} {saat}  Haftalık kota sıfırlandı"
    if o["tur"] == "GELMEDI":
        return (f"{saat}  {o['rezervasyon']} GELMEDİ "
                f"({o['kullanici']}, güvenilirlik {o['guvenilirlik']})")
    if o["tur"] == "TAMAMLANDI":
        return (f"{saat}  {o['rezervasyon']} tamamlandı "
                f"({o['kullanici']}, güvenilirlik {o['guvenilirlik']})")
    return f"{saat}  {o['tur']}"


def gunluk_ozeti(komut: dict, s: dict) -> str:
    if s["durum"] == "RED":
        return f"{s['kod']} — {aciklama(s['kod'])}"
    ad = s["komut"]
    if ad == "rezervasyon":
        return f"{s['rezervasyon_id']} · {s['ucret']} KP · bakiye {s['bakiye']}"
    if ad == "paket":
        return f"{s['paket_id']}: {', '.join(s['rezervasyonlar'])} · toplam {s['toplam']} KP · bakiye {s['bakiye']}"
    if ad == "fiyat":
        return f"{komut.get('kaynak')} · {s['ucret']} KP"
    if ad == "iptal":
        return (f"{komut.get('rezervasyon')} · iade {s['iade']} · bakiye {s['bakiye']} · "
                f"güvenilirlik {s['guvenilirlik']} · {len(s['olaylar'])} atama")
    if ad in ("giris", "cikis"):
        return f"{komut.get('rezervasyon')} → {s['yeni_durum']}"
    if ad == "bekleme":
        return f"{s['bekleme_id']} · sıra {s['sira']}"
    if ad == "saat":
        return f"→ {komut.get('zaman')} · {len(s['olaylar'])} olay"
    if ad == "sorgu":
        if "doluluk" in s:
            return f"{komut.get('id')} {komut.get('gun')} · {len(s['doluluk'])} öğe"
        return f"{komut.get('id')} · bakiye {s['bakiye']} · {len(s['rezervasyonlar'])} rezervasyon"
    return str(komut.get("id", ""))


class SonucKutusu(tk.Frame):
    """İşlemin hemen yanında beliren renkli sonuç kutusu."""

    RENKLER = {"ok": ("#F0FDF4", "#16A34A", "#14532D"),
               "hata": ("#FEF2F2", "#DC2626", "#7F1D1D"),
               "bilgi": ("#EFF6FF", "#2563EB", "#1E3A8A")}

    def __init__(self, ana):
        super().__init__(ana, bg=PANEL)
        self.serit = tk.Frame(self, width=S(4), bg=PANEL)
        self.serit.pack(side="left", fill="y")
        self.ic = tk.Frame(self, bg=PANEL)
        self.ic.pack(side="left", fill="both", expand=True)
        self.etiket = tk.Label(self.ic, justify="left", anchor="w", bg=PANEL, font=(YAZI, 9))
        self.etiket.pack(fill="x", padx=S(8), pady=S(5))
        self.dugme = ttk.Button(self.ic, style="Kucuk.TButton")
        self._genislik = None
        self.bind("<Configure>", self._boyut_degisti)

    def _boyut_degisti(self, olay):
        # Yalnızca genişlik değişince sarma uzunluğu güncellenir; aksi halde yükseklik
        # değişimi yeni bir <Configure> doğurup döngüye girer.
        if olay.width != self._genislik:
            self._genislik = olay.width
            self.etiket.configure(wraplength=max(50, olay.width - S(24)))

    def goster(self, tur: str, metin: str, eylem=None):
        zemin, serit, yazi = self.RENKLER[tur]
        for w in (self, self.ic, self.etiket):
            w.configure(bg=zemin)
        self.serit.configure(bg=serit)
        self.etiket.configure(text=metin, fg=yazi)
        if eylem:
            self.dugme.configure(text=eylem[0], command=eylem[1])
            self.dugme.pack(anchor="w", padx=S(8), pady=(0, S(6)))
        else:
            self.dugme.pack_forget()

    def sonuc(self, sonuc: dict, basari_metni: str, eylem=None):
        if sonuc["durum"] == "TAMAM":
            self.goster("ok", basari_metni)
        else:
            self.goster("hata", f"✗ {sonuc['kod']}\n{aciklama(sonuc['kod'])}", eylem)

    def temizle(self):
        for w in (self, self.ic, self.etiket, self.serit):
            w.configure(bg=PANEL)
        self.etiket.configure(text="")
        self.dugme.pack_forget()


class Cubuk(tk.Canvas):
    """İnce ilerleme çubuğu (bakiye / güvenilirlik)."""

    def __init__(self, ana):
        super().__init__(ana, height=S(6), bg="#E2E8F0", highlightthickness=0)
        self._oran, self._renk = 0, VURGU
        self.bind("<Configure>", lambda e: self._ciz())

    def ayarla(self, oran: float, renk: str):
        self._oran, self._renk = max(0.0, min(1.0, oran)), renk
        self._ciz()

    def _ciz(self):
        self.delete("all")
        self.create_rectangle(0, 0, self.winfo_width() * self._oran, S(6), fill=self._renk,
                              outline="")


class Uygulama(tk.Tk):
    def __init__(self, dosya=None):
        super().__init__()
        self.title("Kampüs Kaynak Rezervasyon Sistemi")
        stilleri_kur(self)
        self.geometry(f"{S(1500)}x{S(920)}")
        self.minsize(S(1200), S(720))
        if sys.platform == "win32":
            self.state("zoomed")
        self.sistem: RezervasyonSistemi | None = None
        self.gun = date.today()
        self.secili_kullanici = None
        self.secili_rez = None
        self.secili_kaynak = None
        self.gunluk = []
        self.kalemler = []
        self.aktif_kalem = None
        self._agac_guncelleniyor = False
        self._onizleme_zamanlayici = None
        self._gonderilen = None  # başarıyla gönderilen formun imzası (önizlemeyi susturur)
        self._arayuzu_kur()
        self.after(80, lambda: self._ilk_yukleme(dosya))

    # =====================================================================
    # Kurulum
    # =====================================================================
    def _arayuzu_kur(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.ust = self._ust_cubuk()
        self.ust.grid(row=0, column=0, sticky="ew")
        dikey = ttk.PanedWindow(self, orient="vertical")
        dikey.grid(row=1, column=0, sticky="nsew", padx=S(10), pady=S(10))
        ana = ttk.Frame(dikey, style="Zemin.TFrame")
        ana.columnconfigure(1, weight=1)
        ana.rowconfigure(0, weight=1)
        self._kullanici_paneli(ana).grid(row=0, column=0, sticky="nsew", padx=(0, S(10)))
        self.takvim = Takvim(ana, self)
        self.takvim.grid(row=0, column=1, sticky="nsew")
        self._sag_panel(ana).grid(row=0, column=2, sticky="nsew", padx=(S(10), 0))
        dikey.add(ana, weight=5)
        dikey.add(self._gunluk_paneli(dikey), weight=1)
        self._olay_seridi_kur()
        self.after(200, lambda: dikey.sashpos(0, max(S(300), dikey.winfo_height() - S(165))))

    def _ust_cubuk(self):
        ust = tk.Frame(self, bg=UST_ZEMIN)
        sol = tk.Frame(ust, bg=UST_ZEMIN)
        sol.pack(side="left", padx=S(16), pady=S(8))
        tk.Label(sol, text="Kampüs Kaynak Rezervasyon", bg=UST_ZEMIN, fg="#FFFFFF",
                 font=(YAZI, 12, "bold")).pack(anchor="w")
        self.dosya_etiketi = tk.Label(sol, text="Başlangıç dosyası seçin…", bg=UST_ZEMIN,
                                      fg="#93C5FD", font=(YAZI, 8, "underline"), cursor="hand2")
        self.dosya_etiketi.pack(anchor="w")
        self.dosya_etiketi.bind("<Button-1>", lambda e: self.dosya_sec())

        sag = tk.Frame(ust, bg=UST_ZEMIN)
        sag.pack(side="right", padx=S(16))
        ttk.Button(sag, text="+ Yeni kaynak", style="Ust.TButton",
                   command=lambda: KaynakEkle(self)).pack(side="right")
        ttk.Button(sag, text="+ Yeni üye", style="Ust.TButton",
                   command=lambda: KullaniciEkle(self)).pack(side="right", padx=S(6))

        saat = tk.Frame(ust, bg=UST_ZEMIN)
        saat.pack(side="left", padx=(S(40), S(16)))
        tk.Label(saat, text="SİMÜLE SAAT", bg=UST_ZEMIN, fg="#94A3B8",
                 font=(YAZI, 7, "bold")).pack(anchor="w")
        satir = tk.Frame(saat, bg=UST_ZEMIN)
        satir.pack(anchor="w")
        self.saat_etiketi = tk.Label(satir, text="--:--", bg=UST_ZEMIN, fg="#FFFFFF",
                                     font=(YAZI, 20, "bold"))
        self.saat_etiketi.pack(side="left")
        self.tarih_etiketi = tk.Label(satir, text="", bg=UST_ZEMIN, fg="#CBD5E1",
                                      font=(YAZI, 10))
        self.tarih_etiketi.pack(side="left", padx=(S(8), 0), pady=(S(8), 0))

        kontrol = tk.Frame(ust, bg=UST_ZEMIN)
        kontrol.pack(side="left", pady=S(8))
        self.saat_kontrolu = kontrol
        tk.Label(kontrol, text="SAATİ İLERİ AL", bg=UST_ZEMIN, fg="#94A3B8",
                 font=(YAZI, 7, "bold")).grid(row=0, column=0, columnspan=8, sticky="w")
        for i, (metin, fark) in enumerate([("+15 dk", timedelta(minutes=15)),
                                           ("+1 saat", timedelta(hours=1)),
                                           ("+1 gün", timedelta(days=1))]):
            ttk.Button(kontrol, text=metin, style="Ust.TButton",
                       command=lambda f=fark: self.saati_ilerlet(f)).grid(
                row=1, column=i, padx=(0, S(4)))
        ttk.Separator(kontrol, orient="vertical").grid(row=1, column=3, sticky="ns", padx=S(8))
        self.v_hedef_tarih = tk.StringVar()
        self.v_hedef_saat = tk.StringVar()
        self.cb_hedef_tarih = ttk.Combobox(kontrol, textvariable=self.v_hedef_tarih, width=11,
                                           font=(YAZI, 9))
        self.cb_hedef_tarih.grid(row=1, column=4)
        ttk.Combobox(kontrol, textvariable=self.v_hedef_saat, width=6, values=TUM_SAATLER,
                     font=(YAZI, 9)).grid(row=1, column=5, padx=S(4))
        ttk.Button(kontrol, text="Saate git ▶", style="Vurgu.TButton",
                   command=self.saati_hedefe_al).grid(row=1, column=6)
        return ust

    def _olay_seridi_kur(self):
        self.olay_seridi = tk.Frame(self, bg="#FFFBEB", highlightbackground="#F59E0B",
                                    highlightthickness=1)
        self.olay_seridi.columnconfigure(0, weight=1)
        self.olay_basligi = tk.Label(self.olay_seridi, bg="#FFFBEB", fg="#92400E",
                                     font=(YAZI, 9, "bold"), anchor="w")
        self.olay_basligi.grid(row=0, column=0, sticky="w", padx=S(12), pady=(S(6), 0))
        self.olay_metni = tk.Label(self.olay_seridi, bg="#FFFBEB", fg="#78350F", font=(YAZI, 9),
                                   anchor="w", justify="left")
        self.olay_metni.grid(row=1, column=0, sticky="w", padx=S(12), pady=(0, S(6)))
        kapat = tk.Label(self.olay_seridi, text="✕", bg="#FFFBEB", fg="#92400E", cursor="hand2",
                         font=(YAZI, 10))
        kapat.grid(row=0, column=1, rowspan=2, sticky="ne", padx=S(10), pady=S(4))
        kapat.bind("<Button-1>", lambda e: self.olay_seridi.place_forget())

    def _olaylari_goster(self, baslik: str, metin: str, renk: str):
        """Saat ilerletme sonucunu saat denetiminin hemen altında gösterir."""
        self.olay_basligi.configure(text=baslik, fg=renk)
        self.olay_metni.configure(text=metin)
        self.update_idletasks()
        x = self.saat_kontrolu.winfo_rootx() - self.winfo_rootx()
        self.olay_seridi.place(x=x, y=self.ust.winfo_height() + S(4))
        self.olay_seridi.lift()

    def _kullanici_paneli(self, ana):
        p = ttk.Frame(ana, padding=S(14), width=S(330))
        p.pack_propagate(False)
        ttk.Label(p, text="KULLANICI", style="Bolum.TLabel").pack(anchor="w")
        self.v_kullanici = tk.StringVar()
        self.cb_kullanici = ttk.Combobox(p, textvariable=self.v_kullanici, state="readonly",
                                         font=(YAZI, 10))
        self.cb_kullanici.pack(fill="x", pady=(S(4), S(2)))
        self.cb_kullanici.bind("<<ComboboxSelected>>", lambda e: self._kullanici_secildi())
        self.rol_etiketi = ttk.Label(p, style="Soluk.TLabel")
        self.rol_etiketi.pack(anchor="w")

        istat = ttk.Frame(p)
        istat.pack(fill="x", pady=(S(10), S(4)))
        istat.columnconfigure((0, 1), weight=1, uniform="istat")
        self.istatistik = {}
        for i, (anahtar, baslik) in enumerate([("bakiye", "BAKİYE"), ("guven", "GÜVENİLİRLİK")]):
            kutu = ttk.Frame(istat)
            kutu.grid(row=0, column=i, sticky="ew", padx=(0, S(10)) if i == 0 else 0)
            ttk.Label(kutu, text=baslik, style="Bolum.TLabel").pack(anchor="w")
            satir = ttk.Frame(kutu)
            satir.pack(anchor="w")
            deger = ttk.Label(satir, style="Buyuk.TLabel")
            deger.pack(side="left")
            ust_sinir = ttk.Label(satir, style="Soluk.TLabel")
            ust_sinir.pack(side="left", padx=(S(4), 0), pady=(S(8), 0))
            cubuk = Cubuk(kutu)
            cubuk.pack(fill="x", pady=(S(2), 0))
            self.istatistik[anahtar] = (deger, ust_sinir, cubuk)
        self.sinir_etiketi = ttk.Label(p, style="Soluk.TLabel", wraplength=S(300), justify="left")
        self.sinir_etiketi.pack(anchor="w", pady=(S(6), 0))

        baslik = ttk.Frame(p)
        baslik.pack(fill="x", pady=(S(14), S(4)))
        ttk.Label(baslik, text="REZERVASYONLAR", style="Bolum.TLabel").pack(side="left")
        ttk.Button(baslik, text="Sorgula", style="Kucuk.TButton",
                   command=self.kullanici_sorgula).pack(side="right")
        alt = ttk.Frame(p)
        alt.pack(side="bottom", fill="x")
        agac_cerceve = ttk.Frame(p)
        agac_cerceve.pack(fill="both", expand=True)
        self.rez_agaci = ttk.Treeview(agac_cerceve, columns=("kaynak", "zaman", "durum", "ucret"),
                                      show="tree headings", selectmode="browse", height=4)
        self.rez_agaci.heading("#0", text="No")
        self.rez_agaci.column("#0", width=S(38), stretch=False)
        for kolon, baslik_metni, genislik in [("kaynak", "Kaynak", 52), ("zaman", "Zaman", 100),
                                              ("durum", "Durum", 70), ("ucret", "KP", 32)]:
            self.rez_agaci.heading(kolon, text=baslik_metni, anchor="w")
            self.rez_agaci.column(kolon, width=S(genislik), anchor="w",
                                  stretch=kolon == "zaman")
        for durum, (_, cerceve, _, _) in DURUM_STILI.items():
            self.rez_agaci.tag_configure(durum, foreground=cerceve)
        kaydirma = ttk.Scrollbar(agac_cerceve, orient="vertical", command=self.rez_agaci.yview)
        self.rez_agaci.configure(yscrollcommand=kaydirma.set)
        self.rez_agaci.pack(side="left", fill="both", expand=True)
        kaydirma.pack(side="right", fill="y")
        self.rez_agaci.bind("<<TreeviewSelect>>", lambda e: self._agactan_secildi())

        eylemler = ttk.Frame(alt)
        eylemler.pack(fill="x", pady=(S(6), S(4)))
        for i, (metin, ad) in enumerate([("Giriş", "giris"), ("Çıkış", "cikis"),
                                         ("İptal", "iptal")]):
            ttk.Button(eylemler, text=metin, command=lambda a=ad: self._agac_eylemi(a)).grid(
                row=0, column=i, sticky="ew", padx=(0, S(4)) if i < 2 else 0)
            eylemler.columnconfigure(i, weight=1)
        self.kullanici_sonucu = SonucKutusu(alt)
        self.kullanici_sonucu.pack(fill="x")

        ttk.Label(alt, text="BEKLEME KAYITLARI", style="Bolum.TLabel").pack(anchor="w",
                                                                           pady=(S(10), S(4)))
        self.bekleme_agaci = ttk.Treeview(alt, columns=("kaynak", "zaman", "sira"),
                                          show="tree headings", height=3, selectmode="none")
        self.bekleme_agaci.heading("#0", text="No")
        self.bekleme_agaci.column("#0", width=S(38), stretch=False)
        for kolon, baslik_metni, genislik in [("kaynak", "Kaynak", 60), ("zaman", "Zaman", 130),
                                              ("sira", "Sıra", 40)]:
            self.bekleme_agaci.heading(kolon, text=baslik_metni, anchor="w")
            self.bekleme_agaci.column(kolon, width=S(genislik), anchor="w",
                                      stretch=kolon == "zaman")
        self.bekleme_agaci.pack(fill="x")
        return p

    def _sag_panel(self, ana):
        p = ttk.Frame(ana, style="Zemin.TFrame", width=S(410))
        p.pack_propagate(False)
        talep = ttk.Frame(p, padding=S(14))
        talep.pack(fill="x")
        self._talep_formu(talep)
        kart = ttk.Frame(p, padding=S(14))
        kart.pack(fill="both", expand=True, pady=(S(10), 0))
        self._secim_karti(kart)
        return p

    def _talep_formu(self, p):
        ust = ttk.Frame(p)
        ust.pack(fill="x")
        ttk.Label(ust, text="TALEP", style="Bolum.TLabel").pack(side="left")
        self.v_mod = tk.StringVar(value="tek")
        for metin, deger in [("Paket", "paket"), ("Tek", "tek")]:
            ttk.Radiobutton(ust, text=metin, value=deger, variable=self.v_mod,
                            style="Segment.Toolbutton", command=self._mod_degisti).pack(side="right")
        self.talep_sahibi = ttk.Label(p, style="Soluk.TLabel")
        self.talep_sahibi.pack(anchor="w", pady=(S(4), S(8)))

        self.v_kaynak, self.v_tarih = tk.StringVar(), tk.StringVar()
        self.v_bas, self.v_bit = tk.StringVar(), tk.StringVar()
        self.tek_cerceve = ttk.Frame(p)
        tek = self.tek_cerceve
        tek.columnconfigure((0, 1, 2), weight=1, uniform="t")
        ttk.Label(tek, text="Kaynak", style="Soluk.TLabel").grid(row=0, column=0, sticky="w")
        self.cb_kaynak = ttk.Combobox(tek, textvariable=self.v_kaynak, font=(YAZI, 9))
        self.cb_kaynak.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, S(6)))
        for i, etiket in enumerate(["Tarih", "Başlangıç", "Bitiş"]):
            ttk.Label(tek, text=etiket, style="Soluk.TLabel").grid(row=2, column=i, sticky="w")
        self.cb_tarih = ttk.Combobox(tek, textvariable=self.v_tarih, font=(YAZI, 9), width=11)
        self.cb_tarih.grid(row=3, column=0, sticky="ew", padx=(0, S(4)))
        ttk.Combobox(tek, textvariable=self.v_bas, values=FORM_SAATLERI, font=(YAZI, 9),
                     width=6).grid(row=3, column=1, sticky="ew", padx=(0, S(4)))
        ttk.Combobox(tek, textvariable=self.v_bit, values=FORM_SAATLERI, font=(YAZI, 9),
                     width=6).grid(row=3, column=2, sticky="ew")
        for v in (self.v_kaynak, self.v_tarih, self.v_bas, self.v_bit):
            v.trace_add("write", lambda *a: self._onizleme_istegi())

        self.paket_cerceve = ttk.Frame(p)
        self.kalem_kutusu = ttk.Frame(self.paket_cerceve)
        self.kalem_kutusu.pack(fill="x")
        ttk.Button(self.paket_cerceve, text="+ Kalem ekle", style="Kucuk.TButton",
                   command=self._kalem_ekle).pack(anchor="w", pady=(S(4), 0))

        self.onizleme = ttk.Label(p, style="Kalin.TLabel", wraplength=S(370), justify="left")
        self.dugmeler = ttk.Frame(p)
        self.gonder_dugmesi = ttk.Button(self.dugmeler, text="Rezervasyon yap",
                                         style="Vurgu.TButton", command=self.talep_gonder)
        self.gonder_dugmesi.pack(side="left")
        self.fiyat_dugmesi = ttk.Button(self.dugmeler, text="Fiyat sor", command=self.fiyat_sor)
        self.fiyat_dugmesi.pack(side="left", padx=S(6))
        self.bekleme_dugmesi = ttk.Button(self.dugmeler, text="Beklemeye gir",
                                          command=lambda: self.bekleme_ac(self._tek_alanlar()))
        self.bekleme_dugmesi.pack(side="left")
        self.talep_sonucu = SonucKutusu(p)
        self._mod_degisti()

    def _secim_karti(self, p):
        self.kart_basligi = ttk.Label(p, text="SEÇİLİ REZERVASYON", style="Bolum.TLabel")
        self.kart_basligi.pack(anchor="w")
        self.kart_bos = ttk.Label(p, style="Soluk.TLabel", wraplength=S(360), justify="left",
                                  text="Takvimde ya da kullanıcı listesinde bir rezervasyona "
                                       "tıklayın; kaynağın doluluğunu görmek için takvimde "
                                       "kaynak adına tıklayın.")
        self.kart_rez = ttk.Frame(p)
        bilgi = ttk.Frame(self.kart_rez)
        bilgi.pack(fill="x", pady=(S(6), S(8)))
        bilgi.columnconfigure(1, weight=1)
        ust = ttk.Frame(bilgi)
        ust.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, S(6)))
        self.kart_no = ttk.Label(ust, style="Buyuk.TLabel")
        self.kart_no.pack(side="left")
        self.kart_rozet = tk.Label(ust, font=(YAZI, 8, "bold"), padx=S(8), pady=S(2))
        self.kart_rozet.pack(side="left", padx=S(10))
        self.kart_alanlari = {}
        for i, (anahtar, etiket) in enumerate([("kullanici", "Kullanıcı"), ("kaynak", "Kaynak"),
                                               ("aralik", "Aralık"), ("ucret", "Ücret"),
                                               ("paket", "Paket")]):
            ttk.Label(bilgi, text=etiket, style="Soluk.TLabel").grid(row=i + 1, column=0,
                                                                    sticky="w", pady=S(1))
            deger = ttk.Label(bilgi)
            deger.grid(row=i + 1, column=1, sticky="w", padx=(S(12), 0))
            self.kart_alanlari[anahtar] = deger
        eylemler = ttk.Frame(self.kart_rez)
        eylemler.pack(fill="x")
        for i, (metin, ad) in enumerate([("Giriş", "giris"), ("Çıkış", "cikis"),
                                         ("İptal", "iptal")]):
            ttk.Button(eylemler, text=metin,
                       command=lambda a=ad: self.eylem(a, self.secili_rez)).grid(
                row=0, column=i, sticky="ew", padx=(0, S(4)) if i < 2 else 0)
            eylemler.columnconfigure(i, weight=1)
        self.kart_sonucu = SonucKutusu(self.kart_rez)
        self.kart_sonucu.pack(fill="x", pady=(S(6), 0))

        self.kart_kaynak = ttk.Frame(p)
        self.kaynak_bilgisi = ttk.Label(self.kart_kaynak, wraplength=S(360), justify="left")
        self.kaynak_bilgisi.pack(anchor="w", pady=(S(6), S(6)))
        self.doluluk_agaci = ttk.Treeview(self.kart_kaynak, columns=("aralik", "tur", "rez"),
                                          show="headings", height=6, selectmode="browse")
        for kolon, baslik_metni, genislik in [("aralik", "Aralık", 120), ("tur", "Tür", 100),
                                              ("rez", "Rezervasyon", 90)]:
            self.doluluk_agaci.heading(kolon, text=baslik_metni, anchor="w")
            self.doluluk_agaci.column(kolon, width=S(genislik), anchor="w")
        self.doluluk_agaci.pack(fill="both", expand=True)
        self.doluluk_agaci.bind("<<TreeviewSelect>>", lambda e: self._doluluktan_secildi())
        self._karti_goster(None)

    def _gunluk_paneli(self, ana):
        p = ttk.Frame(ana, padding=S(10))
        p.columnconfigure(0, weight=3)
        p.columnconfigure(2, weight=2)
        p.rowconfigure(1, weight=1)
        ttk.Label(p, text="OLAY GÜNLÜĞÜ", style="Bolum.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(p, text="SEÇİLİ İŞLEMİN JSON KARŞILIĞI",
                  style="Bolum.TLabel").grid(row=0, column=2, sticky="w", padx=(S(10), 0))
        self.gunluk_agaci = ttk.Treeview(p, columns=("saat", "komut", "durum", "ozet"),
                                         show="tree headings", height=6, selectmode="browse")
        self.gunluk_agaci.heading("#0", text="No")
        self.gunluk_agaci.column("#0", width=S(44), stretch=False)
        for kolon, baslik_metni, genislik in [("saat", "Simüle saat", 110),
                                              ("komut", "Komut", 100), ("durum", "Durum", 60),
                                              ("ozet", "Sonuç", 380)]:
            self.gunluk_agaci.heading(kolon, text=baslik_metni, anchor="w")
            self.gunluk_agaci.column(kolon, width=S(genislik), anchor="w",
                                     stretch=kolon == "ozet")
        self.gunluk_agaci.tag_configure("RED", foreground=HATA)
        self.gunluk_agaci.tag_configure("TAMAM", foreground=METIN)
        kaydirma = ttk.Scrollbar(p, orient="vertical", command=self.gunluk_agaci.yview)
        self.gunluk_agaci.configure(yscrollcommand=kaydirma.set)
        self.gunluk_agaci.grid(row=1, column=0, sticky="nsew", pady=(S(4), 0))
        kaydirma.grid(row=1, column=1, sticky="ns", pady=(S(4), 0))
        self.gunluk_agaci.bind("<<TreeviewSelect>>", lambda e: self._gunluk_secildi())
        self.json_alani = tk.Text(p, font=(MONO, 9), wrap="char", height=6, bg="#F8FAFC",
                                  relief="flat", highlightthickness=1, highlightbackground=KENAR,
                                  padx=S(8), pady=S(6), state="disabled")
        self.json_alani.grid(row=1, column=2, sticky="nsew", padx=(S(10), 0), pady=(S(4), 0))
        self.json_alani.tag_configure("baslik", foreground=SOLUK, font=(YAZI, 8, "bold"))
        return p

    # =====================================================================
    # Dosya
    # =====================================================================
    def _ilk_yukleme(self, dosya):
        if dosya and self._dosya_yukle(dosya):
            return
        if not self.dosya_sec() and self.sistem is None:
            if VARSAYILAN_DOSYA.exists():
                self._dosya_yukle(str(VARSAYILAN_DOSYA))
            else:
                self.destroy()

    def dosya_sec(self) -> bool:
        yol = filedialog.askopenfilename(
            parent=self, title="Başlangıç dosyasını seçin",
            initialdir=str(VARSAYILAN_DOSYA.parent if VARSAYILAN_DOSYA.exists() else KOK),
            filetypes=[("JSON dosyası", "*.json"), ("Tüm dosyalar", "*.*")])
        return bool(yol) and self._dosya_yukle(yol)

    def _dosya_yukle(self, yol: str) -> bool:
        try:
            sistem = RezervasyonSistemi.dosyadan(yol)
        except (OSError, ValueError, KeyError, TypeError) as hata:
            messagebox.showerror("Dosya okunamadı", f"{yol}\n\n{hata}", parent=self)
            return False
        self.sistem = sistem
        self.dosya_etiketi.configure(text=f"📂 {Path(yol).name}  (değiştir)")
        self.gun = sistem.simdi.date()
        self.secili_rez = self.secili_kaynak = None
        self.gunluk.clear()
        self.gunluk_agaci.delete(*self.gunluk_agaci.get_children())
        self._json_goster("")
        self.olay_seridi.place_forget()
        for kutu in (self.talep_sonucu, self.kullanici_sonucu, self.kart_sonucu):
            kutu.temizle()
        self.secili_kullanici = next(iter(sistem.kullanicilar), None)
        self._form_varsayilanlari()
        self._hedef_saati_guncelle()
        self.yenile()
        return True

    def _form_varsayilanlari(self):
        s = self.sistem
        kaynak = next(iter(s.kaynaklar.values()), None)
        self.v_kaynak.set(self._kaynak_metni(kaynak.id) if kaynak else "")
        an = s.simdi + timedelta(minutes=(-s.simdi.minute) % 15)
        if an.hour < 8:
            an = datetime.combine(an.date(), time(9))
        elif an.hour >= 21:
            an = datetime.combine(an.date() + timedelta(days=1), time(9))
        self.v_tarih.set(an.date().isoformat())
        self.v_bas.set(an.strftime("%H:%M"))
        self.v_bit.set((an + timedelta(hours=1)).strftime("%H:%M"))
        for kalem in list(self.kalemler):
            kalem["cerceve"].destroy()
        self.kalemler.clear()
        self._kalem_ekle()
        self._kalem_ekle()

    # =====================================================================
    # Modül çağrısı ve yenileme
    # =====================================================================
    def calistir(self, komut_adi: str, **alanlar) -> dict:
        """Komutun karşılığı olan modül metodunu çağırır ve sonucu günlüğe yazar."""
        komut = {"komut": komut_adi, **{k: v for k, v in alanlar.items() if v is not None}}
        sonuc = getattr(self.sistem, komut_adi)(**alanlar)
        if komut_adi != "saat":
            self.olay_seridi.place_forget()
        satir = {"no": len(self.gunluk) + 1, "komut": komut_adi, **sonuc}
        self.gunluk.append((komut, satir))
        oge = self.gunluk_agaci.insert(
            "", "end", text=str(satir["no"]), tags=(satir["durum"],),
            values=(self.sistem.simdi.strftime("%d.%m %H:%M"), komut_adi, satir["durum"],
                    gunluk_ozeti(komut, satir)))
        self.gunluk_agaci.see(oge)
        self.gunluk_agaci.selection_set(oge)
        self._json_goster(komut, satir)
        self.yenile()
        return sonuc

    def yenile(self):
        if self.sistem is None:
            return
        s = self.sistem
        self.saat_etiketi.configure(text=s.simdi.strftime("%H:%M"))
        self.tarih_etiketi.configure(text=gun_basligi(s.simdi.date()))
        gunler = [(s.simdi.date() + timedelta(days=i)).isoformat() for i in range(0, 31)]
        self.cb_tarih.configure(values=gunler)
        self.cb_hedef_tarih.configure(values=gunler)
        kaynak_metinleri = [self._kaynak_metni(k) for k in s.kaynaklar]
        self.cb_kaynak.configure(values=kaynak_metinleri)
        for kalem in self.kalemler:
            kalem["cb_kaynak"].configure(values=list(s.kaynaklar))
            kalem["cb_tarih"].configure(values=gunler)
        self._kullanici_paneli_yenile()
        if self.secili_rez:
            self._karti_goster("rez")
        elif not self.secili_kaynak:
            self._karti_goster(None)
        self.takvim.ciz_istegi()
        self._onizleme_istegi()

    def _kaynak_metni(self, kaynak_id: str) -> str:
        k = self.sistem.kaynaklar.get(kaynak_id)
        return f"{kaynak_id}  —  {k.ad} ({k.tur})" if k else kaynak_id

    @staticmethod
    def _kaynak_id(metin: str) -> str:
        return metin.split()[0] if metin.strip() else ""

    # =====================================================================
    # Kullanıcı paneli
    # =====================================================================
    def _kullanici_paneli_yenile(self):
        s = self.sistem
        idler = list(s.kullanicilar)
        self.cb_kullanici.configure(values=[f"{u}  ·  {s.kullanicilar[u].ad}" for u in idler])
        kisi = s.kullanicilar.get(self.secili_kullanici)
        if kisi is None:
            self.v_kullanici.set("")
            self.talep_sahibi.configure(text="Talep sahibi: —")
            return
        self.v_kullanici.set(f"{kisi.id}  ·  {kisi.ad}")
        rol = s.roller.get(kisi.rol, {})
        self.rol_etiketi.configure(text=f"{kisi.rol}  ·  sertifikalar: "
                                        f"{', '.join(kisi.sertifikalar) or 'yok'}")
        self.talep_sahibi.configure(text=f"Talep sahibi: {kisi.id} · {kisi.ad} ({kisi.rol})")
        kota = rol.get("haftalik_kota", 0) or 1
        deger, ust, cubuk = self.istatistik["bakiye"]
        deger.configure(text=str(kisi.bakiye))
        ust.configure(text=f"/ {rol.get('haftalik_kota', '?')} KP")
        cubuk.ayarla(kisi.bakiye / kota, VURGU)
        deger, ust, cubuk = self.istatistik["guven"]
        deger.configure(text=str(kisi.guvenilirlik),
                        foreground=HATA if kisi.guvenilirlik < 50 else METIN)
        ust.configure(text="/ 100")
        cubuk.ayarla(kisi.guvenilirlik / 100,
                     "#DC2626" if kisi.guvenilirlik < 50 else
                     "#F59E0B" if kisi.guvenilirlik < 70 else "#16A34A")
        self.sinir_etiketi.configure(
            text=f"İleri tarih sınırı: {s.ileri_gun(kisi)} gün  ·  "
                 f"azami süre: {rol.get('azami_sure_dk', '?')} dk")

        self._agac_guncelleniyor = True
        self.rez_agaci.delete(*self.rez_agaci.get_children())
        rezler = sorted((r for r in s.rezervasyonlar.values() if r.kullanici == kisi.id),
                        key=lambda r: (r.baslangic, r.no))
        for r in rezler:
            self.rez_agaci.insert("", "end", iid=r.id, text=r.id, tags=(r.durum,), values=(
                r.kaynak, f"{r.baslangic:%d.%m %H:%M}–{r.bitis:%H:%M}", DURUM_ADI[r.durum],
                r.ucret))
        if self.secili_rez in self.rez_agaci.get_children():
            self.rez_agaci.selection_set(self.secili_rez)
            self.rez_agaci.see(self.secili_rez)
        self._agac_guncelleniyor = False

        self.bekleme_agaci.delete(*self.bekleme_agaci.get_children())
        for b in s.bekleme_kayitlari.values():
            if b.kullanici == kisi.id:
                sira = [x.id for x in s.bekleme_sirasi(b.kaynak)].index(b.id) + 1
                self.bekleme_agaci.insert("", "end", text=b.id, values=(
                    b.kaynak, f"{b.baslangic:%d.%m %H:%M}–{b.bitis:%H:%M}", sira))

    def _kullanici_secildi(self):
        idler = list(self.sistem.kullanicilar)
        i = self.cb_kullanici.current()
        if 0 <= i < len(idler):
            self.kullanici_sec(idler[i])

    def kullanici_sec(self, kullanici_id: str):
        self.secili_kullanici = kullanici_id
        self.kullanici_sonucu.temizle()
        self.talep_sonucu.temizle()
        self.yenile()

    def kullanici_sorgula(self):
        if not self.secili_kullanici:
            return
        sonuc = self.calistir("sorgu", tur="kullanici", id=self.secili_kullanici)
        self.kullanici_sonucu.sonuc(
            sonuc, f"✓ Sorgu: bakiye {sonuc.get('bakiye')} KP · güvenilirlik "
                   f"{sonuc.get('guvenilirlik')} · {len(sonuc.get('rezervasyonlar', []))} rezervasyon")

    def _agactan_secildi(self):
        if self._agac_guncelleniyor:
            return
        secim = self.rez_agaci.selection()
        if secim and secim[0] != self.secili_rez:
            self.rezervasyon_sec(secim[0])

    def _agac_eylemi(self, ad: str):
        secim = self.rez_agaci.selection()
        if not secim:
            self.kullanici_sonucu.goster("bilgi", "Önce listeden bir rezervasyon seçin.")
            return
        self.eylem(ad, secim[0], self.kullanici_sonucu)

    # =====================================================================
    # Seçim kartı ve eylemler
    # =====================================================================
    def rezervasyon_sec(self, rez_id: str):
        r = self.sistem.rezervasyonlar.get(rez_id)
        if r is None:
            return
        if self.secili_rez != rez_id:
            self.kart_sonucu.temizle()
        self.secili_rez = rez_id
        self.secili_kaynak = None
        self.gun = r.baslangic.date()
        self.yenile()

    def kaynak_sec(self, kaynak_id: str):
        self.secili_kaynak = kaynak_id
        self.secili_rez = None
        if self.v_mod.get() == "tek":
            self.v_kaynak.set(self._kaynak_metni(kaynak_id))
        sonuc = self.calistir("sorgu", tur="kaynak", id=kaynak_id, gun=self.gun.isoformat())
        self._karti_goster("kaynak", sonuc)

    def _karti_goster(self, tur, sonuc=None):
        if tur == "kaynak" and sonuc is None:
            return
        for cerceve in (self.kart_bos, self.kart_rez, self.kart_kaynak):
            cerceve.pack_forget()
        s = self.sistem
        if tur == "rez" and s and self.secili_rez in s.rezervasyonlar:
            r = s.rezervasyonlar[self.secili_rez]
            kisi = s.kullanicilar.get(r.kullanici)
            kaynak = s.kaynaklar.get(r.kaynak)
            dolgu, cerceve, yazi, _ = DURUM_STILI[r.durum]
            self.kart_basligi.configure(text="SEÇİLİ REZERVASYON")
            self.kart_no.configure(text=r.id)
            self.kart_rozet.configure(text=DURUM_ADI[r.durum].upper(), bg=dolgu, fg=yazi)
            alanlar = self.kart_alanlari
            alanlar["kullanici"].configure(text=f"{r.kullanici} · {kisi.ad if kisi else ''}")
            alanlar["kaynak"].configure(text=f"{r.kaynak} · {kaynak.ad if kaynak else ''}")
            alanlar["aralik"].configure(
                text=f"{gun_basligi(r.baslangic.date())}, {r.baslangic:%H:%M}–{r.bitis:%H:%M}")
            alanlar["ucret"].configure(text=f"{r.ucret} KP")
            alanlar["paket"].configure(text=r.paket or "—")
            self.kart_rez.pack(fill="both", expand=True)
        elif tur == "kaynak":
            kaynak = s.kaynaklar.get(self.secili_kaynak)
            self.kart_basligi.configure(text="KAYNAK DOLULUĞU (sorgu)")
            self.doluluk_agaci.delete(*self.doluluk_agaci.get_children())
            if sonuc["durum"] == "TAMAM":
                self.kaynak_bilgisi.configure(
                    text=f"{kaynak.id} · {kaynak.ad} ({kaynak.tur})\n"
                         f"İzinli roller: {', '.join(kaynak.izinli_roller)}\n"
                         f"{gun_basligi(self.gun)} — {len(sonuc['doluluk'])} dolu aralık",
                    foreground=METIN)
                for o in sonuc["doluluk"]:
                    self.doluluk_agaci.insert("", "end", iid=o.get("rezervasyon") or None, values=(
                        f"{o['baslangic'][11:]}–{o['bitis'][11:]}",
                        "Bakım" if o["tur"] == "BAKIM" else "Rezervasyon",
                        o.get("rezervasyon", "")))
            else:
                self.kaynak_bilgisi.configure(text=f"✗ {sonuc['kod']} — {aciklama(sonuc['kod'])}",
                                              foreground=HATA)
            self.kart_kaynak.pack(fill="both", expand=True)
        else:
            self.kart_basligi.configure(text="SEÇİM")
            self.kart_bos.pack(anchor="w", pady=(S(6), 0))

    def _doluluktan_secildi(self):
        secim = self.doluluk_agaci.selection()
        if secim and secim[0] in self.sistem.rezervasyonlar and secim[0] != self.secili_rez:
            self.rezervasyon_sec(secim[0])

    def eylem(self, ad: str, rez_id, kutu: SonucKutusu | None = None):
        """Giriş, çıkış veya iptal; sonuç işlemin yapıldığı yerde gösterilir."""
        if not rez_id:
            return
        if kutu is None:
            self.secili_rez = rez_id
            kutu = self.kart_sonucu
        sonuc = self.calistir(ad, rezervasyon=rez_id)
        if sonuc["durum"] == "TAMAM":
            if ad == "giris":
                metin = f"✓ {rez_id}: giriş yapıldı — durum Kullanımda"
            elif ad == "cikis":
                metin = (f"✓ {rez_id}: çıkış yapıldı — durum Tamamlandı · "
                         f"güvenilirlik {sonuc['guvenilirlik']}")
            else:
                metin = (f"✓ {rez_id} iptal edildi — iade {sonuc['iade']} KP · bakiye "
                         f"{sonuc['bakiye']} KP · güvenilirlik {sonuc['guvenilirlik']}")
            for o in sonuc.get("olaylar", []):
                metin += "\n↳ " + olay_metni(o)
            kutu.goster("ok", metin)
        else:
            kutu.sonuc(sonuc, "")

    # =====================================================================
    # Talep formu
    # =====================================================================
    def _mod_degisti(self):
        paket = self.v_mod.get() == "paket"
        for w in (self.tek_cerceve, self.paket_cerceve, self.onizleme, self.dugmeler,
                  self.talep_sonucu):
            w.pack_forget()
        (self.paket_cerceve if paket else self.tek_cerceve).pack(fill="x")
        self.onizleme.pack(anchor="w", pady=(S(10), S(6)))
        self.dugmeler.pack(fill="x")
        self.talep_sonucu.pack(fill="x", pady=(S(8), 0))
        self.gonder_dugmesi.configure(text="Paketi gönder" if paket else "Rezervasyon yap")
        for d in (self.fiyat_dugmesi, self.bekleme_dugmesi):
            if paket:
                d.pack_forget()
            else:
                d.pack(side="left", padx=(S(6), 0))
        self.talep_sonucu.temizle()
        self._onizleme_istegi()

    def _kalem_ekle(self, kaynak_id="", tarih=None, bas="", bit=""):
        satir = ttk.Frame(self.kalem_kutusu)
        satir.pack(fill="x", pady=(0, S(4)))
        kalem = {"cerceve": satir, "v_kaynak": tk.StringVar(value=kaynak_id),
                 "v_tarih": tk.StringVar(value=tarih or self.v_tarih.get()),
                 "v_bas": tk.StringVar(value=bas), "v_bit": tk.StringVar(value=bit),
                 "gonderildi": False}
        kalem["no"] = ttk.Label(satir, style="Soluk.TLabel", width=2)
        kalem["no"].grid(row=0, column=0)
        kalem["cb_kaynak"] = ttk.Combobox(satir, textvariable=kalem["v_kaynak"], width=7,
                                          values=list(self.sistem.kaynaklar) if self.sistem else [])
        kalem["cb_kaynak"].grid(row=0, column=1, padx=(0, S(3)))
        kalem["cb_tarih"] = ttk.Combobox(satir, textvariable=kalem["v_tarih"], width=10)
        kalem["cb_tarih"].grid(row=0, column=2, padx=(0, S(3)))
        bas_cb = ttk.Combobox(satir, textvariable=kalem["v_bas"], values=FORM_SAATLERI, width=5)
        bas_cb.grid(row=0, column=3)
        ttk.Label(satir, text="–").grid(row=0, column=4)
        bit_cb = ttk.Combobox(satir, textvariable=kalem["v_bit"], values=FORM_SAATLERI, width=5)
        bit_cb.grid(row=0, column=5)
        kalem["fiyat"] = ttk.Label(satir, style="Soluk.TLabel", width=7, anchor="e")
        kalem["fiyat"].grid(row=0, column=6, padx=(S(3), 0))
        sil = tk.Label(satir, text="✕", fg=SOLUK, bg=PANEL, cursor="hand2")
        sil.grid(row=0, column=7, padx=(S(4), 0))
        sil.bind("<Button-1>", lambda e: self._kalem_sil(kalem))
        kalem["sonuc"] = tk.Label(satir, bg=PANEL, font=(YAZI, 8), anchor="w", justify="left",
                                  wraplength=S(340))
        kalem["sonuc"].grid(row=1, column=1, columnspan=7, sticky="w")
        for w in (kalem["cb_kaynak"], kalem["cb_tarih"], bas_cb, bit_cb):
            w.bind("<FocusIn>", lambda e, k=kalem: setattr(self, "aktif_kalem", k))
        for anahtar in ("v_kaynak", "v_tarih", "v_bas", "v_bit"):
            kalem[anahtar].trace_add("write", lambda *a, k=kalem: self._kalem_degisti(k))
        self.kalemler.append(kalem)
        self._kalemleri_numarala()
        self._onizleme_istegi()
        return kalem

    def _kalem_sil(self, kalem):
        kalem["cerceve"].destroy()
        self.kalemler.remove(kalem)
        if self.aktif_kalem is kalem:
            self.aktif_kalem = None
        self._kalemleri_numarala()
        self._onizleme_istegi()

    def _kalemleri_numarala(self):
        for i, kalem in enumerate(self.kalemler):
            kalem["no"].configure(text=f"{i + 1}.")

    def _kalem_degisti(self, kalem):
        kalem["gonderildi"] = False
        kalem["sonuc"].configure(text="")
        self._onizleme_istegi()

    def _kalem_alanlari(self, kalem) -> dict:
        tarih = kalem["v_tarih"].get().strip()
        return {"kaynak": kalem["v_kaynak"].get().strip(),
                "baslangic": f"{tarih}T{kalem['v_bas'].get().strip()}",
                "bitis": f"{tarih}T{kalem['v_bit'].get().strip()}"}

    def _tek_alanlar(self) -> dict:
        tarih = self.v_tarih.get().strip()
        return {"kullanici": self.secili_kullanici,
                "kaynak": self._kaynak_id(self.v_kaynak.get()),
                "baslangic": f"{tarih}T{self.v_bas.get().strip()}",
                "bitis": f"{tarih}T{self.v_bit.get().strip()}"}

    def formu_doldur(self, kaynak_id: str, bas: datetime, bit: datetime):
        """Takvimde tıklanan / sürüklenen aralığı talep formuna yazar."""
        if self.v_mod.get() == "tek":
            self.v_kaynak.set(self._kaynak_metni(kaynak_id))
            self.v_tarih.set(bas.date().isoformat())
            self.v_bas.set(bas.strftime("%H:%M"))
            self.v_bit.set(bit.strftime("%H:%M"))
            self.talep_sonucu.temizle()
            self.gonder_dugmesi.focus_set()
            return
        kalem = self.aktif_kalem if self.aktif_kalem in self.kalemler else None
        if kalem is None:
            bos = [k for k in self.kalemler if not k["v_kaynak"].get().strip()]
            kalem = bos[0] if bos else self._kalem_ekle()
        kalem["v_kaynak"].set(kaynak_id)
        kalem["v_tarih"].set(bas.date().isoformat())
        kalem["v_bas"].set(bas.strftime("%H:%M"))
        kalem["v_bit"].set(bit.strftime("%H:%M"))
        sonraki = self.kalemler.index(kalem) + 1
        self.aktif_kalem = self.kalemler[sonraki] if sonraki < len(self.kalemler) else None

    def _form_imzasi(self):
        if self.v_mod.get() == "tek":
            return ("tek", *self._tek_alanlar().values())
        return ("paket", self.secili_kullanici,
                *(tuple(self._kalem_alanlari(k).values()) for k in self.kalemler))

    def _onizleme_istegi(self):
        if self._onizleme_zamanlayici:
            self.after_cancel(self._onizleme_zamanlayici)
        self._onizleme_zamanlayici = self.after(120, self._onizle)

    def _onizle(self):
        """Gönderimden önce fiyat komutunun karşılığıyla ücreti gösterir (durum değişmez)."""
        self._onizleme_zamanlayici = None
        s = self.sistem
        if s is None:
            return
        if self._gonderilen == self._form_imzasi():
            # Talep az önce kabul edildi; aynı aralığı yeniden sorgulamak kendi
            # rezervasyonuyla kesişme uyarısı gösterirdi. Form değişince önizleme döner.
            self.onizleme.configure(text="")
            return
        kisi = s.kullanicilar.get(self.secili_kullanici)
        bakiye = f"   (bakiye {kisi.bakiye} KP)" if kisi else ""
        if self.v_mod.get() == "tek":
            sonuc = s.fiyat(**self._tek_alanlar())
            if sonuc["durum"] == "TAMAM":
                self.onizleme.configure(text=f"Ücret: {sonuc['ucret']} KP{bakiye}",
                                        foreground=BASARI)
            else:
                self.onizleme.configure(text=f"⚠ {sonuc['kod']} — {aciklama(sonuc['kod'])}",
                                        foreground=HATA)
            return
        toplam, hatali = 0, 0
        for kalem in self.kalemler:
            sonuc = s.fiyat(kullanici=self.secili_kullanici, **self._kalem_alanlari(kalem))
            if sonuc["durum"] == "TAMAM":
                toplam += sonuc["ucret"]
                kalem["fiyat"].configure(text=f"{sonuc['ucret']} KP", foreground=BASARI)
            else:
                hatali += 1
                kalem["fiyat"].configure(text="⚠", foreground=HATA)
            if not kalem["gonderildi"]:
                kalem["sonuc"].configure(
                    fg=UYARI, text="" if sonuc["durum"] == "TAMAM"
                    else f"⚠ {sonuc['kod']} — {aciklama(sonuc['kod'])}")
        ek = f" · {hatali} kalem geçersiz görünüyor" if hatali else ""
        self.onizleme.configure(text=f"Paket ücreti: {toplam} KP{bakiye}{ek}",
                                foreground=HATA if hatali else BASARI)

    def talep_gonder(self):
        if self.sistem is None:
            return
        if self.v_mod.get() == "paket":
            self._paket_gonder()
            return
        alanlar = self._tek_alanlar()
        sonuc = self.calistir("rezervasyon", **alanlar)
        if sonuc["durum"] == "TAMAM":
            self._gonderilen = self._form_imzasi()
            self.talep_sonucu.goster(
                "ok", f"✓ {sonuc['rezervasyon_id']} oluşturuldu — ücret {sonuc['ucret']} KP · "
                      f"yeni bakiye {sonuc['bakiye']} KP")
            self.rezervasyon_sec(sonuc["rezervasyon_id"])
            return
        eylem = None
        if sonuc["kod"] in BEKLEMEYE_UYGUN_KODLAR:
            eylem = ("Bu talep için bekleme kaydı aç", lambda: self.bekleme_ac(alanlar))
        self.talep_sonucu.sonuc(sonuc, "", eylem)

    def fiyat_sor(self):
        sonuc = self.calistir("fiyat", **self._tek_alanlar())
        if sonuc["durum"] == "TAMAM":
            self.talep_sonucu.goster("bilgi", f"Fiyat: {sonuc['ucret']} KP — rezervasyon yapılmadı, "
                                              f"durum değişmedi.")
        else:
            self.talep_sonucu.sonuc(sonuc, "")

    def bekleme_ac(self, alanlar: dict):
        sonuc = self.calistir("bekleme", **alanlar)
        self.talep_sonucu.sonuc(sonuc, f"✓ Bekleme kaydı {sonuc.get('bekleme_id')} açıldı — "
                                       f"{alanlar['kaynak']} listesinde sıra {sonuc.get('sira')}. "
                                       f"Yer boşalınca otomatik atanır.")

    def _paket_gonder(self):
        kalemler = [self._kalem_alanlari(k) for k in self.kalemler]
        sonuc = self.calistir("paket", kullanici=self.secili_kullanici, kalemler=kalemler)
        for kalem in self.kalemler:
            kalem["gonderildi"] = True
            kalem["sonuc"].configure(text="")
        if sonuc["durum"] == "TAMAM":
            self._gonderilen = self._form_imzasi()
            for kalem, rez_id, ucret in zip(self.kalemler, sonuc["rezervasyonlar"],
                                            sonuc["ucretler"]):
                kalem["sonuc"].configure(text=f"✓ {rez_id} · {ucret} KP", fg=BASARI)
            self.talep_sonucu.goster(
                "ok", f"✓ Paket {sonuc['paket_id']} oluşturuldu — "
                      f"{', '.join(sonuc['rezervasyonlar'])} · toplam {sonuc['toplam']} KP · "
                      f"yeni bakiye {sonuc['bakiye']} KP")
            return
        for k in sonuc.get("kalemler", []):
            if k["sira"] < len(self.kalemler):
                etiket = self.kalemler[k["sira"]]["sonuc"]
                if k["durum"] == "TAMAM":
                    etiket.configure(text="✓ geçti", fg=BASARI)
                else:
                    etiket.configure(text=f"✗ {k['kod']} — {aciklama(k['kod'])}", fg=HATA)
        self.talep_sonucu.sonuc(sonuc, "")

    # =====================================================================
    # Simüle saat ve takvim günü
    # =====================================================================
    def _hedef_saati_guncelle(self):
        self.v_hedef_tarih.set(self.sistem.simdi.date().isoformat())
        self.v_hedef_saat.set(self.sistem.simdi.strftime("%H:%M"))

    def saati_ilerlet(self, fark: timedelta):
        if self.sistem:
            self._saat_komutu(zaman_yaz(self.sistem.simdi + fark))

    def saati_hedefe_al(self):
        if self.sistem:
            self._saat_komutu(f"{self.v_hedef_tarih.get().strip()}T{self.v_hedef_saat.get().strip()}")

    def _saat_komutu(self, zaman: str):
        eski_gun = self.sistem.simdi.date()
        takip = self.gun == eski_gun
        sonuc = self.calistir("saat", zaman=zaman)
        if sonuc["durum"] == "TAMAM":
            if takip:
                self.gun = self.sistem.simdi.date()
                self.takvim.ciz_istegi()
            olaylar = sonuc["olaylar"]
            self._olaylari_goster(
                f"Saat {zaman.replace('T', ' ')} olarak ayarlandı — "
                f"{len(olaylar) if olaylar else 'hiç'} olay",
                "\n".join(olay_metni(o) for o in olaylar) or "Bu aralıkta olay gerçekleşmedi.",
                "#92400E")
            self._hedef_saati_guncelle()
        else:
            self._olaylari_goster(f"✗ {sonuc['kod']}", aciklama(sonuc["kod"]), HATA)

    def gun_kaydir(self, gun_sayisi: int):
        if self.sistem:
            self.gun += timedelta(days=gun_sayisi)
            self.takvim.ciz_istegi()

    def simule_gune_don(self):
        if self.sistem:
            self.gun = self.sistem.simdi.date()
            self.takvim.ciz_istegi()

    def yeni_kaynak_eklendi(self, kaynak_id: str):
        self.secili_kaynak = kaynak_id
        self.secili_rez = None
        self._karti_goster(None)
        self.yenile()

    # =====================================================================
    # Olay günlüğü
    # =====================================================================
    def _gunluk_secildi(self):
        secim = self.gunluk_agaci.selection()
        if not secim:
            return
        komut, satir = self.gunluk[int(self.gunluk_agaci.item(secim[0], "text")) - 1]
        self._json_goster(komut, satir)

    def _json_goster(self, komut, satir=None):
        alan = self.json_alani
        alan.configure(state="normal")
        alan.delete("1.0", "end")
        if satir is not None:
            alan.insert("end", "KOMUT  (komutlar.jsonl satırı)\n", "baslik")
            alan.insert("end", jsonla(komut) + "\n\n")
            alan.insert("end", "SONUÇ  (sonuclar.jsonl satırı)\n", "baslik")
            alan.insert("end", jsonla(satir))
        alan.configure(state="disabled")



def main(argv=None):
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    argv = sys.argv[1:] if argv is None else argv
    Uygulama(argv[0] if argv else None).mainloop()
