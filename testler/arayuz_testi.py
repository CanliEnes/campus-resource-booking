"""Arayüzü pencere açmadan sınar: örnek senaryonun 19 işlemini ekrandaki
düğmeler ve takvim üzerinden yapar, sonuçları beklenen dosyayla karşılaştırır.

Kullanım:  python testler/arayuz_testi.py [ekran_goruntusu_klasoru]
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QFont, QMouseEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from arayuz import tema  # noqa: E402
from arayuz.ana_pencere import AnaPencere  # noqa: E402
from arayuz.oturum import Oturum  # noqa: E402
from arayuz.paneller import YeniKaynakPenceresi, YeniUyePenceresi  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
app = QApplication(sys.argv)
app.setStyle("Fusion")
app.setFont(QFont("Segoe UI", 9))
tema.yonetici.renk = tema.ACIK
tema.yonetici.animasyon = False   # test hızlı ve kararlı olsun
app.setStyleSheet(tema.stil_sayfasi())
o = Oturum()
w = AnaPencere(o)
w.resize(1500, 880)
w.yukle(str(KOK / "ornek" / "baslangic.json"))
w.show()
app.processEvents()
hatalar = 0


def kontrol(ad, kosul):
    global hatalar
    hatalar += 0 if kosul else 1
    print(("  OK    " if kosul else "  HATA  ") + ad)


def D(saat, dakika, gun=8):
    return datetime(2027, 3, gun, saat, dakika)


def surukle(kaynak, bas, bit):
    tk = w.takvim
    satir = next(s for s in tk._satirlar if s.kaynak["id"] == kaynak)
    y = int(satir.y + 12)
    x1, x2 = int(tk._x(bas) + 3), int(tk._x(bit) - 3)
    QTest.mousePress(tk, Qt.LeftButton, Qt.NoModifier, QPoint(x1, y))
    tk.mouseMoveEvent(QMouseEvent(QEvent.MouseMove, QPointF(x2, y), QPointF(x2, y),
                                  Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
    QTest.mouseRelease(tk, Qt.LeftButton, Qt.NoModifier, QPoint(x2, y))
    app.processEvents()


def kullanici(uid):
    i = w.kullanici.secim.findData(uid)
    w.kullanici.secim.setCurrentIndex(i)
    w.kullanici.secim.activated.emit(i)
    app.processEvents()


def tikla(dugme):
    QTest.mouseClick(dugme, Qt.LeftButton)
    app.processEvents()


f = w.form
print("Örnek senaryo arayüzden:")
kontrol("açılışta günlük boş (fiyat önizlemesi kendiliğinden yazılmıyor)",
        all(k["komut"]["komut"] != "fiyat" for k in o.gunluk))
# 1-4: ekleme pencereleri
d = YeniUyePenceresi(o, w); d.kimlik.setText("u1"); d.ad.setText("Ayşe Kaya"); d._ekle()
kontrol("1  u1 eklendi", d.result() == 1)
d = YeniUyePenceresi(o, w); kontrol("   önerilen kimlik u2", d.kimlik.text() == "u2"); d.ad.setText("Mehmet Demir"); d._ekle()
d = YeniKaynakPenceresi(o, w); d.tur.setCurrentText("YAZICI")
kontrol("3  önerilen kaynak kimliği YAZ-1", d.kimlik.text() == "YAZ-1")
d.ad.setText("3B Yazıcı 1"); [c.setChecked(c.text() == "OGRENCI") for c in d.roller]; d._ekle()
d = YeniKaynakPenceresi(o, w); d.tur.setCurrentText("LAB"); d.kimlik.setText("LAB-1"); d.ad.setText("Laboratuvar 1"); d._ekle()
kontrol("4  takvimde YAZ-1 ve LAB-1 satırı", [s.kaynak["id"] for s in w.takvim._satirlar][-2:] == ["YAZ-1", "LAB-1"])
d = YeniUyePenceresi(o, w); d.kimlik.setText("u1"); d._ekle()
kontrol("   aynı kimlik: pencere açık kalıyor, ID_MEVCUT gösteriliyor",
        d.result() == 0 and d.sonuc.baslik.text() == "ID_MEVCUT")
o.gunluk.pop(); o._no -= 1   # bu deneme örnek senaryoda yok

# 5: takvimde sürükleyerek
kullanici("u1")
surukle("YAZ-1", D(11, 0), D(13, 0))
kontrol("5  sürükleme formu doldurdu (YAZ-1 11:00–13:00)",
        (f.kaynak.currentData(), f.bas.currentText(), f.bit.currentText()) == ("YAZ-1", "11:00", "13:00"))
kontrol("   fiyat önizlemesi 36 KP", f.fiyat_etiket.text() == "36 KP")
tikla(f.gonder)
kontrol("   r1 oluştu, yeni bakiye 84", f.tek_sonuc.baslik.text() == "r1 oluşturuldu" and "84" in f.tek_sonuc.metin.text())
kontrol("   kullanıcı panelinde bakiye 84", w.kullanici.bakiye.text() == "84")
# 6-10
kullanici("u2")
for kaynak, b, e, beklenen in (("YAZ-2", D(10, 0), D(12, 0), "r2 oluşturuldu"),
                               ("YAZ-2", D(12, 30), D(13, 30), "ARDISIK_KULLANIM"),
                               ("LAB-1", D(14, 0), D(15, 0), "SERTIFIKA_YOK")):
    f.aralik_doldur(kaynak, b, e); tikla(f.gonder)
    kontrol(f"   {kaynak} {b:%H:%M} → {beklenen}", f.tek_sonuc.baslik.text() == beklenen)
kullanici("u1")
f.aralik_doldur("YAZ-1", D(13, 0), D(14, 0)); f.bas.setCurrentText("13:10"); app.processEvents(); tikla(f.gonder)
kontrol("9  elle yazılan 13:10 → ZAMAN_ADIMI_HATASI", f.tek_sonuc.baslik.text() == "ZAMAN_ADIMI_HATASI")
f.aralik_doldur("YAZ-1", D(13, 15), D(14, 0)); tikla(f.gonder)
kontrol("10 HAZIRLIK_IHLALI ve Türkçe açıklama", f.tek_sonuc.baslik.text() == "HAZIRLIK_IHLALI"
        and "hazırlık" in f.tek_sonuc.metin.text())
kontrol("   bekleme kaydı seçeneği sunuldu", f.tek_sonuc.dugme.isVisibleTo(f))
# 11-12 paket
kullanici("u3")
f.aralik_doldur("CIH-1", D(14, 0), D(16, 0))
kontrol("11 fiyat 48 KP", f.fiyat_etiket.text() == "48 KP")
f.sekmeler.setCurrentIndex(1); app.processEvents()
k0, k1 = f.kalemler
f._kalem_odak(k0); f.aralik_doldur("CIH-1", D(14, 0), D(16, 0))
f._kalem_odak(k1); f.aralik_doldur("YAZ-2", D(14, 0), D(16, 0))
tikla(f.paket_gonder)
kontrol("   PAKET_RED: kalem 1 geçti, kalem 2 kendi satırında ROL_IZNI_YOK",
        k0.durum.text() == "Geçti" and k1.durum.text() == "ROL_IZNI_YOK")
o.gunluk.pop(); o._no -= 1
f._kalem_odak(k1); f.aralik_doldur("ODA-1", D(14, 0), D(16, 0)); tikla(f.paket_gonder)
kontrol("12 paket p1 [r3, r4], toplam 56, bakiye 244", f.paket_sonuc.baslik.text() == "Paket p1 oluşturuldu"
        and "56" in f.paket_sonuc.metin.text() and "244" in f.paket_sonuc.metin.text())
f.sekmeler.setCurrentIndex(0)
# 13-15
kullanici("u1")
f.aralik_doldur("CIH-1", D(16, 30), D(17, 30)); tikla(f.gonder)
kontrol("13 ROL_IZNI_YOK", f.tek_sonuc.baslik.text() == "ROL_IZNI_YOK")
f.aralik_doldur("ODA-2", D(9, 0, 16), D(10, 0, 16)); tikla(f.gonder)
kontrol("14 ILERI_TARIH_SINIRI", f.tek_sonuc.baslik.text() == "ILERI_TARIH_SINIRI")
kullanici("u2")
f.aralik_doldur("YAZ-1", D(12, 0), D(13, 0)); tikla(f.bekle)
kontrol("15 bekleme b1, sıra 1", f.tek_sonuc.baslik.text() == "Bekleme kaydı b1 açıldı")
kontrol("   kullanıcı panelinde bekleme kaydı görünüyor", w.kullanici.bekleme_tablo.rowCount() == 1)
# 16 saat
w.saat_secici.setDateTime(w.saat_secici.dateTime().fromString("08.03.2027 11:20", "dd.MM.yyyy HH:mm"))
tikla(next(b for b in w.findChildren(QPushButton) if b.text() == "İlerlet"))
kontrol("16 saat 11:20, olay bandında 3 olay", "11:20" in w.saat_etiket.text() and "3 olay" in w.olay_baslik.text())
kontrol("   otomatik atama bantta yazıyor", "b1 → r5 otomatik atandı" in w.olay_metni.text())
# 17-18 takvimden
tk = w.takvim
satir = next(s for s in tk._satirlar if s.kaynak["id"] == "YAZ-1")
kontrol("   YAZ-1 satırı iki alt satır: r5 üstte, gelinmeyen r1 altta",
        [[r.id for r in s] for s in satir.seritler] == [["r5"], ["r1"]])
QTest.mouseClick(tk, Qt.LeftButton, Qt.NoModifier, QPoint(int(tk._x(D(11, 30))), int(satir.y + 6 + 30 + 12)))
app.processEvents()
kontrol("17 takvimde r1'e tıklandı", w.kart.rid == "r1")
tikla(w.kart.dugmeler["giris"])
kontrol("   giriş → DURUM_HATASI", w.kart.sonuc.baslik.text() == "DURUM_HATASI")
satir = next(s for s in tk._satirlar if s.kaynak["id"] == "ODA-1")
QTest.mouseClick(tk, Qt.LeftButton, Qt.NoModifier, QPoint(int(tk._x(D(15, 0))), int(satir.y + 18)))
app.processEvents()
kontrol("18 takvimde r4'e tıklandı", w.kart.rid == "r4")
tikla(w.kart.dugmeler["iptal"])
kontrol("   iptal: iade 4, bakiye 248", "4 KP" in w.kart.sonuc.metin.text() and "248" in w.kart.sonuc.metin.text())
# 19
kullanici("u2")
kontrol("19 u2: bakiye 57, güvenilirlik 65, iki rezervasyon",
        w.kullanici.bakiye.text() == "57" and w.kullanici.guven.text() == "65" and w.kullanici.tablo.rowCount() == 2)

# Örnek senaryonun 19 sonucu günlükte aynı sırayla bulunmalı. Aralarda kullanıcı
# seçimi (sorgu) ve fiyat önizlemesi gibi ek satırlar olabilir.
beklenen = [json.loads(s) for s in (KOK / "ornek" / "sonuclar.jsonl").read_text("utf-8").splitlines()]
gunluk = iter(k["sonuc"] for k in o.gunluk)
def nosuz(d):
    return {a: b for a, b in d.items() if a != "no"}
ayni = all(any(nosuz(g) == nosuz(e) for g in gunluk) for e in beklenen)
kontrol("ornek/sonuclar.jsonl satırlarının 19'u da günlükte aynı sırayla var", ayni)

if len(sys.argv) > 1:
    klasor = Path(sys.argv[1])
    klasor.mkdir(parents=True, exist_ok=True)
    w._rezervasyon_sec("r5")
    app.processEvents()
    w.grab().save(str(klasor / "acik.png"))
    tema.yonetici.ayarla("koyu")
    app.processEvents()
    w.grab().save(str(klasor / "koyu.png"))
    w.resize(1280, 720)
    app.processEvents()
    w.grab().save(str(klasor / "koyu_kucuk.png"))
    tema.yonetici.renk = tema.ACIK
print(f"\nToplam hata: {hatalar}")
sys.exit(1 if hatalar else 0)
