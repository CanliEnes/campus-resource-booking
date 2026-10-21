# Kampüs Kaynak Rezervasyon Sistemi

Kocaeli Üniversitesi Yazılım Laboratuvarı I, 2026-2027 Güz, Proje I.
Python 3.11+ ile yazılmış rezervasyon modülü ve PySide6 masaüstü uygulaması.

## Kurulum

```
python -m pip install -r requirements.txt
```

Komut satırı (modül) yalnızca Python'un standart kütüphanesini kullanır; PySide6 sadece arayüz için gereklidir.

## Çalıştırma

**Komut satırı (gizli testler bu yolla çalışır):**

```
calistir.bat baslangic.json komutlar.jsonl > sonuclar.jsonl      (Windows)
./calistir.sh baslangic.json komutlar.jsonl > sonuclar.jsonl     (Linux / macOS)
```

**Masaüstü uygulaması:**

```
arayuz.bat                      (açılışta başlangıç dosyası seçilir)
python uygulama.py ornek/baslangic.json
```

**Testler** (örnek senaryo + kendi senaryolarımız, alan alan karşılaştırma):

```
python testler/karsilastir.py
python testler/arayuz_testi.py     (arayüz: örnek senaryo ekrandaki düğmelerle)
```

Arayüzde sağ üstteki ay/güneş düğmesi açık ve koyu tema arasında geçiş yapar; yanındaki
oktan animasyonlar kapatılabilir. Seçim bir sonraki açılışta hatırlanır.

## Klasör yapısı

| Yol | İçerik |
|---|---|
| `rezervasyon/motor.py` | Bütün kurallar (K1-K11). Arayüzden bağımsız. |
| `rezervasyon/mesajlar.py` | Hata kodlarının Türkçe açıklamaları |
| `main.py`, `calistir.bat`, `calistir.sh` | Komut satırı girişi |
| `arayuz/` | PySide6 masaüstü uygulaması (iş kuralı içermez) |
| `uygulama.py`, `arayuz.bat` | Uygulamayı başlatır |
| `ornek/` | Ödevle verilen 19 adımlık örnek senaryo |
| `testler/` | Kendi test senaryolarımız ve karşılaştırma betiği |

## Kendi test senaryolarımız

| Klasör | Ne sınıyor |
|---|---|
| `01_dogrulama_sirasi` | K10'daki 13 kodun her biri, ekleme kodları, sınır değerler (22:00 bitiş, ileri tarih sınırının tam kendisi, 0,5 yukarı yuvarlama) |
| `02_paket_iptal_bekleme` | Paket hata sırası, PAKET_RED kalem listesi, iade dilimleri, bekleme sırası, erken çıkışta ve iptalde otomatik atama, haftalık sıfırlama ve kota tavanı |
| `03_saat_doluluk_durum` | Giriş penceresi, tam olay anında saat, kaynak eklenince doluluğun değişmesi, erken çıkışta hazırlık, güvenilirlik 0-100 sınırı, düşük güvenilirlikte ileri tarih ve paket |
