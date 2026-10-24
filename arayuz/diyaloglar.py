"""Yeni üye ve yeni kaynak ekleme pencereleri."""

import re
import tkinter as tk
from tkinter import ttk

from .tema import HATA, PANEL, S, YAZI, aciklama


class EklemeDiyalogu(tk.Toplevel):
    baslik = ""

    def __init__(self, uygulama):
        super().__init__(uygulama)
        self.u = uygulama
        self.title(self.baslik)
        self.configure(bg=PANEL)
        self.resizable(False, False)
        self.transient(uygulama)
        govde = ttk.Frame(self, padding=S(16))
        govde.pack(fill="both", expand=True)
        ttk.Label(govde, text=self.baslik, style="Baslik.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, S(10)))
        self.govde = govde
        self.satir = 1
        self.alanlari_kur()
        self.hata = ttk.Label(govde, foreground=HATA, wraplength=S(320), justify="left")
        self.hata.grid(row=self.satir, column=0, columnspan=2, sticky="w", pady=(S(8), 0))
        dugmeler = ttk.Frame(govde)
        dugmeler.grid(row=self.satir + 1, column=0, columnspan=2, sticky="e", pady=(S(10), 0))
        ttk.Button(dugmeler, text="Vazgeç", command=self.destroy).pack(side="right")
        ttk.Button(dugmeler, text="Ekle", style="Vurgu.TButton", command=self.ekle).pack(
            side="right", padx=(0, S(6)))
        self.bind("<Return>", lambda e: self.ekle())
        self.bind("<Escape>", lambda e: self.destroy())
        self.update_idletasks()
        x = uygulama.winfo_rootx() + (uygulama.winfo_width() - self.winfo_width()) // 2
        y = uygulama.winfo_rooty() + S(90)
        self.geometry(f"+{x}+{y}")
        self.grab_set()
        self.focus_set()

    def alan(self, etiket: str, widget):
        ttk.Label(self.govde, text=etiket, style="Soluk.TLabel").grid(
            row=self.satir, column=0, sticky="nw", padx=(0, S(12)), pady=S(4))
        widget.grid(row=self.satir, column=1, sticky="ew", pady=S(4))
        self.satir += 1
        return widget

    def secim_kutulari(self, secenekler, secili):
        cerceve = ttk.Frame(self.govde)
        degiskenler = {}
        for i, ad in enumerate(secenekler):
            d = tk.BooleanVar(value=ad in secili)
            ttk.Checkbutton(cerceve, text=ad, variable=d).grid(row=i // 2, column=i % 2,
                                                               sticky="w", padx=(0, S(10)))
            degiskenler[ad] = d
        return cerceve, degiskenler

    def sonucu_isle(self, sonuc: dict, basarida):
        if sonuc["durum"] == "TAMAM":
            self.destroy()
            basarida()
        else:
            self.hata.configure(text=f"✗ {sonuc['kod']} — {aciklama(sonuc['kod'])}")


def _sonraki_id(mevcutlar, on_ek: str) -> str:
    numaralar = [int(m.group(1)) for k in mevcutlar
                 if (m := re.fullmatch(re.escape(on_ek) + r"(\d+)", k))]
    return f"{on_ek}{max(numaralar, default=0) + 1}"


class KullaniciEkle(EklemeDiyalogu):
    baslik = "Yeni üye ekle"

    def alanlari_kur(self):
        s = self.u.sistem
        self.v_id = tk.StringVar(value=_sonraki_id(s.kullanicilar, "u"))
        self.v_ad = tk.StringVar()
        roller = list(s.roller)
        self.v_rol = tk.StringVar(value=roller[0] if roller else "")
        self.v_bakiye = tk.StringVar()
        self.v_guven = tk.StringVar(value="100")
        self.alan("Kimlik", ttk.Entry(self.govde, textvariable=self.v_id, width=28))
        ad = self.alan("Ad soyad", ttk.Entry(self.govde, textvariable=self.v_ad, width=28))
        self.alan("Rol", ttk.Combobox(self.govde, textvariable=self.v_rol, values=roller,
                                      state="readonly"))
        cerceve, self.sertifikalar = self.secim_kutulari(s.tum_sertifikalar(), [])
        self.alan("Sertifikalar", cerceve)
        self.alan("Bakiye (KP)", ttk.Spinbox(self.govde, textvariable=self.v_bakiye, from_=0,
                                             to=100000, increment=10))
        self.alan("Güvenilirlik", ttk.Spinbox(self.govde, textvariable=self.v_guven, from_=0,
                                              to=100, increment=5))
        self.v_rol.trace_add("write", lambda *a: self._kota_varsayilani())
        self._kota_varsayilani()
        ad.focus_set()

    def _kota_varsayilani(self):
        rol = self.u.sistem.roller.get(self.v_rol.get())
        if rol:
            self.v_bakiye.set(str(rol.get("haftalik_kota", 0)))

    def ekle(self):
        alanlar = {
            "id": self.v_id.get().strip(),
            "ad": self.v_ad.get().strip(),
            "rol": self.v_rol.get(),
            "sertifikalar": [ad for ad, d in self.sertifikalar.items() if d.get()],
            "bakiye": _sayi(self.v_bakiye.get()),
            "guvenilirlik": _sayi(self.v_guven.get()),
        }
        sonuc = self.u.calistir("kullanici_ekle", **alanlar)
        self.sonucu_isle(sonuc, lambda: self.u.kullanici_sec(alanlar["id"]))


class KaynakEkle(EklemeDiyalogu):
    baslik = "Yeni kaynak ekle"

    def alanlari_kur(self):
        s = self.u.sistem
        turler = list(s.kaynak_turleri)
        self.v_tur = tk.StringVar(value=turler[0] if turler else "")
        self.v_id = tk.StringVar()
        self.v_ad = tk.StringVar()
        self.alan("Tür", ttk.Combobox(self.govde, textvariable=self.v_tur, values=turler,
                                      state="readonly"))
        self.alan("Kimlik", ttk.Entry(self.govde, textvariable=self.v_id, width=28))
        ad = self.alan("Ad", ttk.Entry(self.govde, textvariable=self.v_ad, width=28))
        cerceve, self.roller = self.secim_kutulari(list(s.roller), list(s.roller))
        self.alan("İzinli roller", cerceve)
        self.v_tur.trace_add("write", lambda *a: self._id_varsayilani())
        self._id_varsayilani()
        ad.focus_set()

    def _id_varsayilani(self):
        s, tur = self.u.sistem, self.v_tur.get()
        on_ekler = [k.id.rsplit("-", 1)[0] + "-" for k in s.kaynaklar.values()
                    if k.tur == tur and "-" in k.id]
        on_ek = on_ekler[0] if on_ekler else tur[:3] + "-"
        self.v_id.set(_sonraki_id(s.kaynaklar, on_ek))

    def ekle(self):
        alanlar = {
            "id": self.v_id.get().strip(),
            "ad": self.v_ad.get().strip(),
            "tur": self.v_tur.get(),
            "izinli_roller": [ad for ad, d in self.roller.items() if d.get()],
        }
        sonuc = self.u.calistir("kaynak_ekle", **alanlar)
        self.sonucu_isle(sonuc, lambda: self.u.yeni_kaynak_eklendi(alanlar["id"]))


def _sayi(metin: str):
    """Kutudaki metni sayıya çevirir; çevrilemiyorsa olduğu gibi modüle gönderilir."""
    metin = metin.strip().replace(",", ".")
    try:
        return int(metin)
    except ValueError:
        try:
            return float(metin)
        except ValueError:
            return metin
