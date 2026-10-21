"""Masaüstü uygulamasını başlatır: python uygulama.py [baslangic.json]

Dosya verilmezse açılışta seçim penceresi gelir; vazgeçilirse ornek/baslangic.json yüklenir.
"""
import sys
from pathlib import Path

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from arayuz.ana_pencere import AnaPencere
from arayuz.oturum import Oturum
from arayuz.stil import STIL


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 9))
    app.setStyleSheet(STIL)
    oturum = Oturum()
    pencere = AnaPencere(oturum)

    yol = sys.argv[1] if len(sys.argv) > 1 else pencere.dosya_sec(ilk=True)
    if not yol:
        ornek = Path(__file__).resolve().parent / "ornek" / "baslangic.json"
        if not ornek.exists():
            return 0
        yol = str(ornek)
    if not pencere.yukle(yol):
        return 1
    pencere.showMaximized()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
