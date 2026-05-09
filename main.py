"""
main.py - punkt wejścia aplikacji MB-TC Configurator.

Uruchomienie:
    python main.py

Aplikacja służy do konfiguracji i odczytu danych z przetwornika temperatury
F&F MB-TC-1 (lub podobnego modułu Modbus RTU) podłączonego przez konwerter RS-485/USB.
"""

import sys
from PySide6.QtWidgets import QApplication

from app.gui import MainWindow


def main():
    """
    Główna funkcja uruchamiająca aplikację Qt.
    Tworzy instancję QApplication oraz okno główne i przekazuje sterowanie do pętli zdarzeń Qt.
    """
    app = QApplication(sys.argv)
    app.setApplicationName("MB-TC Configurator")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
