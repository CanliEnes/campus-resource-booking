"""Kaynak takvimi: seçilen gün için her kaynak ayrı satırda, 08:00-22:00 ekseninde."""

import tkinter as tk
from datetime import datetime, time, timedelta
from tkinter import ttk

from rezervasyon.cekirdek import PIK_BASI, PIK_SONU, kesisir

from .tema import (BAKIM_STILI, DURUM_ADI, DURUM_STILI, HAZIRLIK_STILI, KENAR, KENAR_KOYU,
                   METIN, PANEL, S, SAAT_RENGI, SOLUK, VURGU, YAZI, gun_basligi)

GOSTERIM_BASI = 8   # takvim ekseni 08:00
GOSTERIM_DK = 14 * 60
ETIKET_GENISLIGI = 150
SERIT_YUKSEKLIGI = 27
SATIR_BOSLUGU = 4
GRUP_YUKSEKLIGI = 22
PASIF_DURUMLAR = ("IPTAL", "GELMEDI")


def tarali_dikdortgen(c: tk.Canvas, x0, y0, x1, y1, zemin, cizgi, etiketler, aralik=7):
    c.create_rectangle(x0, y0, x1, y1, fill=zemin, outline="", tags=etiketler)
    yukseklik = y1 - y0
    k = -yukseklik
    while k < x1 - x0:
        ax, ay, bx, by = x0 + k, y1, x0 + k + yukseklik, y0
        if ax < x0:
            ay, ax = y1 - (x0 - ax), x0
        if bx > x1:
            by, bx = y0 + (bx - x1), x1
        if ax < bx:
            c.create_line(ax, ay, bx, by, fill=cizgi, tags=etiketler)
        k += S(aralik)


class Ipucu:
    def __init__(self, ana):
        self.pencere = tk.Toplevel(ana)
        self.pencere.withdraw()
        self.pencere.overrideredirect(True)
        self.etiket = tk.Label(self.pencere, justify="left", bg="#0F172A", fg="#F8FAFC",
                               font=(YAZI, 9), padx=S(8), pady=S(6))
        self.etiket.pack()
        self._metin = None

    def goster(self, metin, x, y):
        if metin != self._metin:
            self.etiket.configure(text=metin)
            self._metin = metin
        self.pencere.geometry(f"+{x + S(14)}+{y + S(12)}")
        self.pencere.deiconify()
        self.pencere.lift()

    def gizle(self):
        self._metin = None
        self.pencere.withdraw()


class Takvim(ttk.Frame):
    def __init__(self, ana, uygulama):
        super().__init__(ana)
        self.u = uygulama
        self.satirlar = []          # (y0, y1, kaynak_id)
        self._surukleme = None      # (kaynak_id, başlangıç dk, y0, y1)
        self._hayalet = None
        self._ciz_bekliyor = False

        ust = ttk.Frame(self)
        ust.grid(row=0, column=0, columnspan=2, sticky="ew", padx=S(12), pady=(S(10), S(6)))
        ttk.Button(ust, text="◀", width=3, command=lambda: self.u.gun_kaydir(-1)).pack(side="left")
        self.gun_etiketi = ttk.Label(ust, style="Baslik.TLabel", width=26, anchor="center")
        self.gun_etiketi.pack(side="left", padx=S(6))
        ttk.Button(ust, text="▶", width=3, command=lambda: self.u.gun_kaydir(1)).pack(side="left")
        ttk.Button(ust, text="Simüle güne dön", command=self.u.simule_gune_don).pack(
            side="left", padx=(S(10), 0))
        lejant = ttk.Frame(self)
        lejant.grid(row=3, column=0, columnspan=2, sticky="w", padx=S(8), pady=S(5))
        ogeler = [(DURUM_ADI[d], DURUM_STILI[d][0], DURUM_STILI[d][1]) for d in DURUM_STILI]
        ogeler += [("Hazırlık", HAZIRLIK_STILI[0], HAZIRLIK_STILI[1]),
                   ("Bakım", BAKIM_STILI[0], BAKIM_STILI[1])]
        for ad, dolgu, cerceve in ogeler:
            kutu = tk.Canvas(lejant, width=S(12), height=S(12), bg=PANEL, highlightthickness=0)
            kutu.create_rectangle(1, 1, S(11), S(11), fill=dolgu, outline=cerceve)
            kutu.pack(side="left", padx=(S(8), S(3)))
            ttk.Label(lejant, text=ad, style="Soluk.TLabel").pack(side="left")

        self.baslik = tk.Canvas(self, height=S(34), bg=PANEL, highlightthickness=0)
        self.baslik.grid(row=1, column=0, sticky="ew")
        self.govde = tk.Canvas(self, bg=PANEL, highlightthickness=0)
        self.govde.grid(row=2, column=0, sticky="nsew")
        kaydirma = ttk.Scrollbar(self, orient="vertical", command=self.govde.yview)
        kaydirma.grid(row=2, column=1, sticky="ns")
        self.govde.configure(yscrollcommand=kaydirma.set)
        ttk.Label(ust, style="Soluk.TLabel", justify="right",
                  text="Boş alanı sürükle → talep formu · kutu → ayrıntı\n"
                       "sağ tık → giriş/çıkış/iptal · kaynak adı → doluluk").pack(side="right")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        self.ipucu = Ipucu(self)
        self.govde.bind("<Configure>", lambda e: self.ciz_istegi())
        self.govde.bind("<ButtonPress-1>", self._bas)
        self.govde.bind("<B1-Motion>", self._surukle)
        self.govde.bind("<ButtonRelease-1>", self._birak)
        self.govde.bind("<Button-3>", self._sag_tik)
        self.govde.bind("<Motion>", self._hareket)
        self.govde.bind("<Leave>", lambda e: self.ipucu.gizle())
        self.govde.bind("<MouseWheel>",
                        lambda e: self.govde.yview_scroll(int(-e.delta / 120), "units"))

    # --- Koordinatlar ---------------------------------------------------------
    def _x(self, dakika: float) -> float:
        return self.x0 + max(0, min(GOSTERIM_DK, dakika)) * self.px

    def _x_an(self, an: datetime) -> float:
        return self._x((an - self.gun_basi).total_seconds() / 60)

    def _dakika(self, x: float) -> int:
        dk = int((x - self.x0) / self.px // 15 * 15)
        return max(0, min(GOSTERIM_DK - 15, dk))

    def _satir(self, y: float):
        for y0, y1, kaynak_id in self.satirlar:
            if y0 <= y < y1:
                return y0, y1, kaynak_id
        return None

    # --- Çizim ----------------------------------------------------------------
    def ciz_istegi(self):
        if not self._ciz_bekliyor:
            self._ciz_bekliyor = True
            self.after_idle(self.ciz)

    def ciz(self):
        self._ciz_bekliyor = False
        s, gun = self.u.sistem, self.u.gun
        if s is None:
            return
        c, b = self.govde, self.baslik
        c.delete("all")
        b.delete("all")
        self.gun_etiketi.configure(text=gun_basligi(gun))
        genislik = max(c.winfo_width(), S(500))
        self.x0, self.x1 = S(ETIKET_GENISLIGI), genislik - S(14)
        self.px = (self.x1 - self.x0) / GOSTERIM_DK
        self.gun_basi = datetime.combine(gun, time(GOSTERIM_BASI))
        self._baslik_ciz(b)

        y = 0
        self.satirlar = []
        tur_sirasi = list(s.kaynak_turleri)
        kaynaklar = sorted(s.kaynaklar.values(), key=lambda k: (
            tur_sirasi.index(k.tur) if k.tur in tur_sirasi else len(tur_sirasi), k.eklenme))
        onceki_tur = None
        for kaynak in kaynaklar:
            if kaynak.tur != onceki_tur:
                y = self._grup_ciz(c, kaynak.tur, y, genislik)
                onceki_tur = kaynak.tur
            y = self._satir_ciz(c, kaynak, y, genislik)

        simdi = s.simdi
        dakika = (simdi - self.gun_basi).total_seconds() / 60
        if simdi.date() == gun and 0 <= dakika <= GOSTERIM_DK:
            x = self._x(dakika)
            c.create_line(x, 0, x, max(y, c.winfo_height()), fill=SAAT_RENGI, width=2)
            b.create_rectangle(x - S(22), S(1), x + S(22), S(15), fill=SAAT_RENGI,
                               outline=SAAT_RENGI)
            b.create_text(x, S(8), text=simdi.strftime("%H:%M"), fill="#FFFFFF",
                          font=(YAZI, 8, "bold"))
            b.create_line(x, S(15), x, S(34), fill=SAAT_RENGI, width=2)
        c.configure(scrollregion=(0, 0, genislik, max(y, 1)))

    def _baslik_ciz(self, b: tk.Canvas):
        yuk = S(34)
        pik0, pik1 = self._x((PIK_BASI - GOSTERIM_BASI) * 60), self._x((PIK_SONU - GOSTERIM_BASI) * 60)
        b.create_rectangle(pik0, S(17), pik1, yuk, fill="#FFF7ED", outline="")
        b.create_text(pik1 - S(4), S(9), text="pik saatler", anchor="e", fill="#C2410C",
                      font=(YAZI, 7))
        for ceyrek in range(0, GOSTERIM_DK // 15 + 1):
            x = self._x(ceyrek * 15)
            if ceyrek % 4 == 0:
                saat = GOSTERIM_BASI + ceyrek // 4
                cift = saat % 2 == 0
                b.create_line(x, yuk - S(8), x, yuk, fill=KENAR_KOYU)
                hiza = "w" if ceyrek == 0 else ("e" if ceyrek == GOSTERIM_DK // 15 else "center")
                b.create_text(x, S(25), text=f"{saat:02d}:00" if cift else f"{saat:02d}",
                              anchor=hiza,
                              font=(YAZI, 8, "bold" if cift else "normal"),
                              fill=METIN if cift else SOLUK)
            else:
                b.create_line(x, yuk - S(4), x, yuk, fill=KENAR)
        b.create_line(0, yuk - 1, self.x1 + S(20), yuk - 1, fill=KENAR_KOYU)

    def _grup_ciz(self, c: tk.Canvas, tur_adi: str, y: int, genislik: int) -> int:
        tur = self.u.sistem.kaynak_turleri.get(tur_adi, {})
        ozellik = [f"hazırlık {tur.get('hazirlik_dk', 0)} dk",
                   f"{tur.get('temel_ucret', '?')} KP/saat"]
        if tur.get("enerji_yogun"):
            ozellik.append("enerji yoğun (pikte ×1,5)")
        if tur.get("sertifika"):
            ozellik.append(f"sertifika: {tur['sertifika']}")
        yuk = S(GRUP_YUKSEKLIGI)
        c.create_rectangle(0, y, genislik, y + yuk, fill="#F8FAFC", outline="")
        c.create_text(S(12), y + yuk / 2, anchor="w", text=tur_adi, fill=SOLUK,
                      font=(YAZI, 8, "bold"))
        c.create_text(self.x0, y + yuk / 2, anchor="w", text="  ·  ".join(ozellik), fill=SOLUK,
                      font=(YAZI, 8))
        c.create_line(0, y + yuk, genislik, y + yuk, fill=KENAR)
        return y + yuk

    def _seritler(self, kaynak_id: str):
        """Aktif rezervasyonlar ilk şeritte; çakışan IPTAL/GELMEDI kutular alt şeritlere iner."""
        gunun = [r for r in self.u.sistem.rezervasyonlar.values()
                 if r.kaynak == kaynak_id and r.baslangic.date() == self.u.gun]
        seritler = [[r for r in gunun if r.durum not in PASIF_DURUMLAR]]
        for r in sorted((r for r in gunun if r.durum in PASIF_DURUMLAR), key=lambda r: r.no):
            for serit in seritler:
                if not any(kesisir(r.baslangic, r.bitis, o.baslangic, o.bitis) for o in serit):
                    serit.append(r)
                    break
            else:
                seritler.append([r])
        return seritler

    def _satir_ciz(self, c: tk.Canvas, kaynak, y: int, genislik: int) -> int:
        s = self.u.sistem
        seritler = self._seritler(kaynak.id)
        serit_yuk, bosluk = S(SERIT_YUKSEKLIGI), S(SATIR_BOSLUGU)
        yuk = len(seritler) * serit_yuk + 2 * bosluk
        secili = kaynak.id == self.u.secili_kaynak
        c.create_rectangle(0, y, genislik, y + yuk, fill="#EFF6FF" if secili else PANEL,
                           outline="")
        etiket = ("etiket", f"kaynak:{kaynak.id}")
        c.create_text(S(12), y + yuk / 2 - S(7), anchor="w", text=kaynak.id,
                      font=(YAZI, 9, "bold"), fill=VURGU if secili else METIN, tags=etiket)
        ad = kaynak.ad if len(kaynak.ad) <= 20 else kaynak.ad[:19] + "…"
        c.create_text(S(12), y + yuk / 2 + S(8), anchor="w", text=ad, font=(YAZI, 8),
                      fill=SOLUK, tags=etiket)

        for ceyrek in range(0, GOSTERIM_DK // 15 + 1):
            renk = KENAR_KOYU if ceyrek % 8 == 0 else (KENAR if ceyrek % 4 == 0 else "#F5F7FA")
            x = self._x(ceyrek * 15)
            c.create_line(x, y, x, y + yuk, fill=renk)
        c.create_line(0, y + yuk, genislik, y + yuk, fill=KENAR)

        gun_basi, gun_sonu = self.gun_basi, self.gun_basi + timedelta(minutes=GOSTERIM_DK)
        for i, bakim in enumerate(s.bakim_pencereleri):
            if bakim.kaynak == kaynak.id and kesisir(bakim.baslangic, bakim.bitis, gun_basi,
                                                     gun_sonu):
                x0, x1 = self._x_an(bakim.baslangic), self._x_an(bakim.bitis)
                tarali_dikdortgen(c, x0, y + S(2), x1, y + yuk - S(2), *BAKIM_STILI,
                                  ("bakim", f"bakim:{i}"))
                if x1 - x0 > S(40):
                    c.create_text((x0 + x1) / 2, y + yuk / 2, text="BAKIM", fill="#334155",
                                  font=(YAZI, 8, "bold"), tags=("bakim", f"bakim:{i}"))

        hazirlik = s.hazirlik_suresi(kaynak.id)
        for i, serit in enumerate(seritler):
            y0 = y + bosluk + i * serit_yuk + S(2)
            y1 = y0 + serit_yuk - S(4)
            for r in serit:
                if hazirlik and r.durum not in PASIF_DURUMLAR:
                    hx0, hx1 = self._x_an(r.bitis), self._x_an(r.bitis + hazirlik)
                    if hx1 > hx0:
                        tarali_dikdortgen(c, hx0, y0 + S(3), hx1, y1 - S(3), *HAZIRLIK_STILI,
                                          ("hazirlik", f"hazirlik:{r.id}"), aralik=5)
                self._kutu_ciz(c, r, y0, y1)
        self.satirlar.append((y, y + yuk, kaynak.id))
        return y + yuk

    def _kutu_ciz(self, c: tk.Canvas, r, y0, y1):
        dolgu, cerceve, yazi, kesikli = DURUM_STILI[r.durum]
        x0, x1 = self._x_an(r.baslangic) + 1, self._x_an(r.bitis) - 1
        if x1 - x0 < 2:
            x1 = x0 + 2
        secili = r.id == self.u.secili_rez
        etiket = ("rez", f"rez:{r.id}")
        c.create_rectangle(x0, y0, x1, y1, fill=dolgu, outline="#0F172A" if secili else cerceve,
                           width=2 if secili else 1, dash=(4, 2) if kesikli else None,
                           tags=etiket)
        if r.paket:
            c.create_rectangle(x0, y0, x0 + S(4), y1, fill=cerceve, outline="", tags=etiket)
        kisi = self.u.sistem.kullanicilar.get(r.kullanici)
        genislik = x1 - x0
        if genislik > S(110) and kisi:
            metin = f"{r.id} · {kisi.ad}"
        elif genislik > S(60):
            metin = f"{r.id} · {r.kullanici}"
        elif genislik > S(24):
            metin = r.id
        else:
            return
        sigan = max(1, int((genislik - S(10)) / S(6.5)))
        if len(metin) > sigan:
            metin = metin[:max(1, sigan - 1)] + "…"
        c.create_text(x0 + S(7), (y0 + y1) / 2, anchor="w", text=metin, fill=yazi,
                      font=(YAZI, 8, "bold"), tags=etiket)

    # --- Etkileşim -------------------------------------------------------------
    def _etiketli_oge(self, on_ek: str):
        oge = self.govde.find_withtag("current")
        if not oge:
            return None
        for etiket in self.govde.gettags(oge[0]):
            if etiket.startswith(on_ek):
                return etiket[len(on_ek):]
        return None

    def _bas(self, olay):
        self.ipucu.gizle()
        x, y = self.govde.canvasx(olay.x), self.govde.canvasy(olay.y)
        rez_id = self._etiketli_oge("rez:")
        if rez_id:
            self.u.rezervasyon_sec(rez_id)
            return
        satir = self._satir(y)
        if satir is None:
            return
        y0, y1, kaynak_id = satir
        if x < self.x0:
            self.u.kaynak_sec(kaynak_id)
            return
        self._surukleme = (kaynak_id, self._dakika(x), y0, y1)
        self._hayalet_ciz(self._surukleme[1], self._surukleme[1] + 15)

    def _surukle(self, olay):
        if not self._surukleme:
            return
        _, bas, _, _ = self._surukleme
        dk = self._dakika(self.govde.canvasx(olay.x))
        self._hayalet_ciz(min(bas, dk), max(bas, dk) + 15)

    def _birak(self, olay):
        if not self._surukleme:
            return
        kaynak_id, bas, _, _ = self._surukleme
        self._surukleme = None
        dk = self._dakika(self.govde.canvasx(olay.x))
        if dk == bas:  # tek tıklama: varsayılan bir saatlik talep
            bas_dk, bit_dk = bas, min(bas + 60, GOSTERIM_DK)
        else:
            bas_dk, bit_dk = min(bas, dk), max(bas, dk) + 15
        self.u.formu_doldur(kaynak_id, self.gun_basi + timedelta(minutes=bas_dk),
                            self.gun_basi + timedelta(minutes=bit_dk))
        self.after(600, self._hayalet_sil)

    def _hayalet_ciz(self, bas_dk, bit_dk):
        self._hayalet_sil()
        _, _, y0, y1 = self._surukleme
        x0, x1 = self._x(bas_dk), self._x(bit_dk)
        self._hayalet = [
            self.govde.create_rectangle(x0, y0 + S(3), x1, y1 - S(3), outline=VURGU, width=2,
                                        dash=(3, 2)),
            self.govde.create_text((x0 + x1) / 2, y0 + S(10), fill=VURGU, font=(YAZI, 8, "bold"),
                                   text=f"{self._saat_yaz(bas_dk)}–{self._saat_yaz(bit_dk)}"),
        ]

    def _hayalet_sil(self):
        for oge in self._hayalet or []:
            self.govde.delete(oge)
        self._hayalet = None

    @staticmethod
    def _saat_yaz(dakika: int) -> str:
        toplam = GOSTERIM_BASI * 60 + dakika
        return f"{toplam // 60:02d}:{toplam % 60:02d}"

    def _sag_tik(self, olay):
        rez_id = self._etiketli_oge("rez:")
        if not rez_id:
            return
        self.u.rezervasyon_sec(rez_id)
        menu = tk.Menu(self, tearoff=0, font=(YAZI, 9))
        menu.add_command(label=f"{rez_id} — Giriş", command=lambda: self.u.eylem("giris", rez_id))
        menu.add_command(label=f"{rez_id} — Çıkış", command=lambda: self.u.eylem("cikis", rez_id))
        menu.add_separator()
        menu.add_command(label=f"{rez_id} — İptal", command=lambda: self.u.eylem("iptal", rez_id))
        menu.tk_popup(olay.x_root, olay.y_root)

    def _hareket(self, olay):
        s = self.u.sistem
        if s is None or self._surukleme:
            return
        metin = None
        rez_id = self._etiketli_oge("rez:")
        if rez_id and rez_id in s.rezervasyonlar:
            r = s.rezervasyonlar[rez_id]
            kisi = s.kullanicilar.get(r.kullanici)
            satirlar = [f"{r.id}  ·  {DURUM_ADI[r.durum]}",
                        f"{r.kullanici} {kisi.ad if kisi else ''}",
                        f"{r.kaynak}  {r.baslangic:%H:%M}–{r.bitis:%H:%M}",
                        f"Ücret: {r.ucret} KP"]
            if r.paket:
                satirlar.append(f"Paket: {r.paket}")
            metin = "\n".join(satirlar)
        elif (bakim := self._etiketli_oge("bakim:")) is not None:
            p = s.bakim_pencereleri[int(bakim)]
            metin = f"Bakım penceresi\n{p.baslangic:%d.%m %H:%M} – {p.bitis:%d.%m %H:%M}"
        elif (hz := self._etiketli_oge("hazirlik:")) is not None and hz in s.rezervasyonlar:
            r = s.rezervasyonlar[hz]
            sure = s.hazirlik_suresi(r.kaynak)
            metin = (f"Hazırlık süresi ({int(sure.total_seconds() // 60)} dk)\n"
                     f"{r.id} sonrası  {r.bitis:%H:%M}–{r.bitis + sure:%H:%M}")
        self.govde.configure(cursor="hand2" if rez_id else "crosshair")
        if metin:
            self.ipucu.goster(metin, olay.x_root, olay.y_root)
        else:
            self.ipucu.gizle()
