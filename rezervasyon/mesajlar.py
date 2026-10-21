"""Hata kodlarının Türkçe açıklamaları (arayüzde gösterilir)."""

ACIKLAMALAR = {
    "BULUNAMADI": "Kullanıcı, kaynak veya rezervasyon bulunamadı.",
    "ZAMAN_ADIMI_HATASI": "Saatler 15 dakikalık adımlara (:00, :15, :30, :45) oturmalı ve bitiş başlangıçtan sonra olmalı.",
    "GECMIS_ZAMAN": "Başlangıç, simüle saatten önce olamaz.",
    "CALISMA_SAATI_DISI": "Rezervasyon aynı gün içinde 08:00-22:00 arasında kalmalı.",
    "SURE_SINIRI": "Süre en az 30 dakika, en fazla rolün azami süresi kadar olabilir.",
    "ILERI_TARIH_SINIRI": "Rolün ileri tarih sınırı aşıldı (güvenilirlik 50'nin altındaysa sınır 1 gün).",
    "ROL_IZNI_YOK": "Bu kullanıcının rolü bu kaynağı rezerve edemez.",
    "SERTIFIKA_YOK": "Bu kaynak türü için gereken sertifika kullanıcıda yok.",
    "BAKIM": "İstenen aralık kaynağın bakım penceresiyle çakışıyor.",
    "KESISME": "Bu aralıkta kaynakta başka bir rezervasyon var.",
    "HAZIRLIK_IHLALI": "Önceki/sonraki kullanımla arada hazırlık süresi kadar boşluk yok.",
    "ARDISIK_KULLANIM": "Aynı kişinin aynı kaynaktaki iki rezervasyonu arasında en az 60 dakika olmalı.",
    "BAKIYE_YETERSIZ": "Bakiye ücreti karşılamıyor.",
    "PAKET_BOYUTU": "Paket 2 ile 4 arasında kalem içermeli.",
    "GUVENILIRLIK_DUSUK": "Güvenilirlik 50'nin altında olduğu için paket rezervasyon yapılamaz.",
    "PAKET_RED": "Paketteki en az bir kalem doğrulamadan geçemedi.",
    "PAKET_ICI_KESISME": "Paketteki aynı kaynağa ait kalemler birbiriyle çakışıyor (kesişme, hazırlık veya art arda kullanım).",
    "DURUM_HATASI": "Rezervasyon bu işlem için uygun durumda değil.",
    "GIRIS_PENCERESI_DISI": "Giriş yalnızca başlangıçtan 10 dakika önce ile 15 dakika sonra arasında yapılabilir.",
    "BEKLEME_GEREKSIZ": "Bu talep zaten geçerli; bekleme yerine doğrudan rezervasyon yapılabilir.",
    "SAAT_GERI": "Simüle saat geri alınamaz.",
    "ID_MEVCUT": "Bu kimlikle bir kayıt zaten var.",
    "TANIMSIZ_DEGER": "Rol, tür veya izinli rollerden biri başlangıç dosyasında tanımlı değil.",
    "GECERSIZ_DEGER": "Bakiye 0 ile haftalık kota arasında, güvenilirlik 0-100 arası tam sayı olmalı.",
    "GECERSIZ_KOMUT": "Komut eksik veya hatalı alan içeriyor.",
    "BILINMEYEN_KOMUT": "Böyle bir komut yok.",
}


def aciklama(kod: str | None) -> str:
    return ACIKLAMALAR.get(kod or "", "Bilinmeyen hata.")
