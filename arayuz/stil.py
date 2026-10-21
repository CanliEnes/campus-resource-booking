"""Metin biçimlendirme yardımcıları (yalnızca görünüm). Renkler tema.py içindedir."""
from datetime import datetime

DURUM_AD = {
    "ONAYLI": "Onaylı", "KULLANIMDA": "Kullanımda", "TAMAMLANDI": "Tamamlandı",
    "IPTAL": "İptal", "GELMEDI": "Gelmedi",
}

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


def olay_metni(olay: dict) -> str:
    z = zaman_metinden(olay.get("zaman"))
    tur = olay.get("tur")
    if tur == "GELMEDI":
        return f"{z} · {olay['rezervasyon']} gelinmedi, {olay['kullanici']} güvenilirliği {olay['guvenilirlik']} oldu"
    if tur == "TAMAMLANDI":
        return f"{z} · {olay['rezervasyon']} tamamlandı, {olay['kullanici']} güvenilirliği {olay['guvenilirlik']} oldu"
    if tur == "OTOMATIK_ATAMA":
        return (f"{z} · Bekleme {olay['bekleme']} → {olay['rezervasyon']} otomatik atandı: "
                f"{olay['kullanici']}, {olay['ucret']} KP, bakiye {olay['bakiye']}")
    if tur == "HAFTALIK_SIFIRLAMA":
        return f"{z} · Haftalık kota yenilendi, bütün bakiyeler kotaya eşitlendi"
    return f"{z} · {tur}"


def olaylar_html(olaylar: list[dict]) -> str:
    return "<br>".join(f"• {olay_metni(o)}" for o in olaylar)


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
        return f"bakiye {sonuc['bakiye']} · güv {sonuc['guvenilirlik']}" if "bakiye" in sonuc else "sorgu"
    return ""
