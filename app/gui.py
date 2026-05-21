"""
gui.py - okno główne aplikacji MB-TC Configurator (PySide6).

Layout: zakładki (QTabWidget) zamiast jednego długiego okna.

Zakładki:
  1. Połączenie    - port COM, parametry portu, połącz/rozłącz
  2. Pomiar        - typ termopary, odczyt temperatur, log w czasie rzeczywistym
  3. Konfiguracja  - zapis ustawień do EEPROM urządzenia (D-1: pomiar, D-2: komunikacja)
  4. Diagnostyka   - log + info o urządzeniu

W zakładce Konfiguracja wszystkie pola są OPCJONALNE - można zapisać tylko
wybrane parametry zostawiając resztę bez zmian (wyczyszczone checkbox-y obok pól).
"""

import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from serial.tools import list_ports

from app.modbus_device import ModbusDeviceError, ModbusTemperatureDevice
from app.sensor_types import (
    SENSOR_DISPLAY_NAMES,
    SensorType,
    display_name_to_sensor_type,
    sensor_type_to_display_name,
)


# Mapowanie etykieta GUI <-> wartość pymodbus
PARITY_MAP = {"NONE": "N", "EVEN": "E", "ODD": "O"}
PARITY_REVERSE = {v: k for k, v in PARITY_MAP.items()}

BAUDRATES = ["1200", "2400", "4800", "9600", "19200", "38400", "57600", "115200"]
STOPBITS_OPTIONS = ["1", "1.5", "2"]


def _resource_path(filename: str) -> str:
    """Lokalizuje zasób (ikonę) zarówno w trybie deweloperskim, jak i pod PyInstallerem."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        candidate = os.path.join(base, filename)
        if os.path.exists(candidate):
            return candidate
    project_root = Path(__file__).resolve().parent.parent
    candidate = project_root / filename
    if candidate.exists():
        return str(candidate)
    return filename


def _stopbits_to_str(value) -> str:
    """1, 1.5, 2 -> '1', '1.5', '2'"""
    if value == 1.5:
        return "1.5"
    return str(int(value))


def _stopbits_from_str(text: str):
    """'1', '1.5', '2' -> 1, 1.5, 2"""
    if text == "1.5":
        return 1.5
    return int(text)


def _stopbits_to_serial(value):
    """Wartość bitów stopu -> stała pyserial."""
    import serial as _serial
    return {
        1: _serial.STOPBITS_ONE,
        1.5: _serial.STOPBITS_ONE_POINT_FIVE,
        2: _serial.STOPBITS_TWO,
    }.get(value, _serial.STOPBITS_ONE)


class MainWindow(QMainWindow):
    """Główne okno aplikacji MB-TC Configurator z zakładkami."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MB-TC Configurator by sincore.io")
        self.resize(820, 720)

        icon_path = _resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.device: ModbusTemperatureDevice | None = None

        self.read_timer = QTimer(self)
        self.read_timer.timeout.connect(self._on_periodic_read)

        self._build_ui()

        self._refresh_com_ports()
        self._update_buttons_state()

    # =====================================================================
    # BUDOWA GUI
    # =====================================================================
    def _build_ui(self):
        self._build_menu()

        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)

        # Pasek statusu (zawsze widoczny, niezależnie od zakładki)
        self.lbl_status = QLabel("Status: rozłączono")
        font = QFont()
        font.setBold(True)
        self.lbl_status.setFont(font)
        self.lbl_status.setStyleSheet("color: #b00020; padding: 6px; background: #fafafa; border-radius: 3px;")
        root.addWidget(self.lbl_status)

        # Zakładki
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_tab_connection(), "🔌 Połączenie")
        self.tabs.addTab(self._build_tab_measurement(), "🌡 Pomiar")
        self.tabs.addTab(self._build_tab_config(), "⚙ Konfiguracja")
        self.tabs.addTab(self._build_tab_diagnostics(), "📋 Diagnostyka")
        root.addWidget(self.tabs, stretch=1)

    def _build_menu(self):
        """Pasek menu - pozycja Pomoc z oknem "O programie"."""
        help_menu = self.menuBar().addMenu("Pomoc")
        about_action = help_menu.addAction("O programie")
        about_action.triggered.connect(self._show_about)

    # ---------------------------------------------------------------------
    # ZAKŁADKA 1: Połączenie
    # ---------------------------------------------------------------------
    def _build_tab_connection(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info = QLabel(
            "Parametry portu szeregowego, którymi aplikacja łączy się z urządzeniem.\n"
            "Muszą być zgodne z aktualnymi parametrami urządzenia."
        )
        info.setStyleSheet("color: #444; padding: 4px; background: #f4f4f4; border-radius: 3px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        box = QGroupBox("Parametry połączenia")
        grid = QGridLayout(box)

        grid.addWidget(QLabel("Port COM:"), 0, 0)
        self.cmb_port = QComboBox()
        grid.addWidget(self.cmb_port, 0, 1)
        self.btn_refresh_ports = QPushButton("Odśwież listę")
        self.btn_refresh_ports.clicked.connect(self._refresh_com_ports)
        grid.addWidget(self.btn_refresh_ports, 0, 2)

        grid.addWidget(QLabel("Prędkość (baud):"), 1, 0)
        self.cmb_baud = QComboBox()
        self.cmb_baud.addItems(BAUDRATES)
        self.cmb_baud.setCurrentText("9600")
        grid.addWidget(self.cmb_baud, 1, 1)

        grid.addWidget(QLabel("Parzystość:"), 2, 0)
        self.cmb_parity = QComboBox()
        self.cmb_parity.addItems(list(PARITY_MAP.keys()))
        self.cmb_parity.setCurrentText("NONE")
        grid.addWidget(self.cmb_parity, 2, 1)

        grid.addWidget(QLabel("Bity stopu:"), 3, 0)
        self.cmb_stopbits = QComboBox()
        self.cmb_stopbits.addItems(STOPBITS_OPTIONS)
        grid.addWidget(self.cmb_stopbits, 3, 1)

        grid.addWidget(QLabel("Adres Modbus (1-247):"), 4, 0)
        self.spn_slave = QSpinBox()
        self.spn_slave.setRange(1, 247)
        self.spn_slave.setValue(1)
        grid.addWidget(self.spn_slave, 4, 1)

        btn_row = QHBoxLayout()
        self.btn_connect = QPushButton("Połącz")
        self.btn_connect.setStyleSheet("font-weight: bold;")
        self.btn_connect.clicked.connect(self._on_connect)
        self.btn_disconnect = QPushButton("Rozłącz")
        self.btn_disconnect.clicked.connect(self._on_disconnect)
        btn_row.addWidget(self.btn_connect)
        btn_row.addWidget(self.btn_disconnect)
        grid.addLayout(btn_row, 5, 0, 1, 3)

        layout.addWidget(box)
        layout.addStretch(1)
        return tab

    # ---------------------------------------------------------------------
    # ZAKŁADKA 2: Pomiar
    # ---------------------------------------------------------------------
    def _build_tab_measurement(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Typ termopary - aktualny tryb roboczy
        sensor_box = QGroupBox("Typ termopary - tryb roboczy")
        sensor_layout = QHBoxLayout(sensor_box)
        sensor_layout.addWidget(QLabel("Typ:"))
        self.cmb_sensor = QComboBox()
        self.cmb_sensor.addItems(list(SENSOR_DISPLAY_NAMES.keys()))
        sensor_layout.addWidget(self.cmb_sensor, stretch=1)
        self.btn_read_sensor = QPushButton("Odczytaj typ")
        self.btn_read_sensor.clicked.connect(self._on_read_sensor_type)
        sensor_layout.addWidget(self.btn_read_sensor)
        self.btn_write_sensor = QPushButton("Zapisz typ")
        self.btn_write_sensor.clicked.connect(self._on_write_sensor_type)
        sensor_layout.addWidget(self.btn_write_sensor)
        layout.addWidget(sensor_box)

        # Odczyt temperatury
        temp_box = QGroupBox("Odczyt temperatury")
        grid = QGridLayout(temp_box)

        grid.addWidget(QLabel("Aktualna:"), 0, 0)
        self.lbl_temp = QLineEdit("--- °C")
        self.lbl_temp.setReadOnly(True)
        self.lbl_temp.setStyleSheet("font-size: 14pt; font-weight: bold;")
        grid.addWidget(self.lbl_temp, 0, 1)

        grid.addWidget(QLabel("Minimum:"), 1, 0)
        self.lbl_temp_min = QLineEdit("--- °C")
        self.lbl_temp_min.setReadOnly(True)
        grid.addWidget(self.lbl_temp_min, 1, 1)

        grid.addWidget(QLabel("Maksimum:"), 2, 0)
        self.lbl_temp_max = QLineEdit("--- °C")
        self.lbl_temp_max.setReadOnly(True)
        grid.addWidget(self.lbl_temp_max, 2, 1)

        grid.addWidget(QLabel("Złącze zimne (obudowa):"), 3, 0)
        self.lbl_cold = QLineEdit("--- °C")
        self.lbl_cold.setReadOnly(True)
        grid.addWidget(self.lbl_cold, 3, 1)

        ctl = QHBoxLayout()
        self.btn_read_now = QPushButton("Odczytaj teraz")
        self.btn_read_now.clicked.connect(self._on_read_now)
        ctl.addWidget(self.btn_read_now)

        self.chk_cyclic = QCheckBox("Odczyt cykliczny")
        self.chk_cyclic.toggled.connect(self._on_cyclic_toggled)
        ctl.addWidget(self.chk_cyclic)

        ctl.addWidget(QLabel("Interwał [ms]:"))
        self.spn_interval = QSpinBox()
        self.spn_interval.setRange(100, 600000)
        self.spn_interval.setSingleStep(100)
        self.spn_interval.setValue(1000)
        self.spn_interval.valueChanged.connect(self._on_interval_changed)
        ctl.addWidget(self.spn_interval)

        self.btn_reset_minmax = QPushButton("Zeruj Min/Max")
        self.btn_reset_minmax.clicked.connect(self._on_reset_min_max)
        ctl.addWidget(self.btn_reset_minmax)

        grid.addLayout(ctl, 4, 0, 1, 2)
        layout.addWidget(temp_box)

        tc_note = QLabel(
            "ℹ Aplikacja wykrywa niestabilny pomiar (luźny / przerywany styk "
            "termopary). UWAGA: czystego, całkowitego rozłączenia termopary "
            "MB-TC-1 nie sygnalizuje — daje wtedy stabilny odczyt zbliżony do "
            "temperatury otoczenia, nieodróżnialny od realnego pomiaru. "
            "Stabilny wynik bliski temperaturze pokojowej warto zweryfikować."
        )
        tc_note.setStyleSheet("color: #444; padding: 4px; background: #f4f4f4; border-radius: 3px;")
        tc_note.setWordWrap(True)
        layout.addWidget(tc_note)

        layout.addStretch(1)
        return tab

    # ---------------------------------------------------------------------
    # ZAKŁADKA 3: Konfiguracja przetwornika
    # ---------------------------------------------------------------------
    def _build_tab_config(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info = QLabel(
            "Trwały zapis konfiguracji do EEPROM urządzenia. "
            "Każdy parametr ma checkbox - zaznacz tylko te, które chcesz zmienić; "
            "reszta zostanie nietknięta. "
            "Po przeniesieniu urządzenia w inne miejsce uruchomi się z zapisanymi parametrami."
        )
        info.setStyleSheet("color: #444; padding: 4px; background: #f4f4f4; border-radius: 3px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        # ---------- D-1: Parametry pomiaru ----------
        meas_box = QGroupBox("D-1) Parametry pomiaru (bezpieczne, nie zrywają połączenia)")
        meas = QGridLayout(meas_box)

        meas.addWidget(QLabel("Zapisz?"), 0, 0)
        meas.addWidget(QLabel("Parametr"), 0, 1)
        meas.addWidget(QLabel("Wartość"), 0, 2)

        self.chk_dev_sensor = QCheckBox()
        meas.addWidget(self.chk_dev_sensor, 1, 0)
        meas.addWidget(QLabel("Typ termopary:"), 1, 1)
        self.cmb_dev_sensor = QComboBox()
        self.cmb_dev_sensor.addItems(list(SENSOR_DISPLAY_NAMES.keys()))
        meas.addWidget(self.cmb_dev_sensor, 1, 2)

        self.chk_dev_avg = QCheckBox()
        meas.addWidget(self.chk_dev_avg, 2, 0)
        meas.addWidget(QLabel("Liczba próbek do uśredniania (0-30):"), 2, 1)
        self.spn_avg_time = QSpinBox()
        self.spn_avg_time.setRange(0, 30)
        self.spn_avg_time.setValue(1)
        self.spn_avg_time.setToolTip("0 = przetwornik wyłączony")
        meas.addWidget(self.spn_avg_time, 2, 2)

        self.chk_dev_corr = QCheckBox()
        meas.addWidget(self.chk_dev_corr, 3, 0)
        meas.addWidget(QLabel("Korekcja temperatury [°C] (-100..100):"), 3, 1)
        self.spn_correction = QDoubleSpinBox()
        self.spn_correction.setRange(-100.0, 100.0)
        self.spn_correction.setSingleStep(0.1)
        self.spn_correction.setDecimals(1)
        self.spn_correction.setValue(0.0)
        meas.addWidget(self.spn_correction, 3, 2)

        meas_btns = QHBoxLayout()
        self.btn_read_meas = QPushButton("Odczytaj parametry pomiaru z urządzenia")
        self.btn_read_meas.clicked.connect(self._on_read_measurement_params)
        meas_btns.addWidget(self.btn_read_meas)

        self.btn_write_meas = QPushButton("Zapisz zaznaczone")
        self.btn_write_meas.setStyleSheet("font-weight: bold;")
        self.btn_write_meas.clicked.connect(self._on_write_measurement_params)
        meas_btns.addWidget(self.btn_write_meas)
        meas.addLayout(meas_btns, 4, 0, 1, 3)

        layout.addWidget(meas_box)

        # ---------- D-2: Parametry komunikacji ----------
        comm_box = QGroupBox("D-2) Parametry komunikacji (po zapisie urządzenie wymaga reconnectu)")
        comm = QGridLayout(comm_box)

        warn = QLabel(
            "⚠ Po zapisie urządzenie odpowie tylko z nowymi parametrami. "
            "Aplikacja automatycznie się rozłączy i poprosi o ponowne połączenie."
        )
        warn.setStyleSheet("color: #aa6600; padding: 4px; background: #fff8e0; border: 1px solid #d0b070; border-radius: 3px;")
        warn.setWordWrap(True)
        comm.addWidget(warn, 0, 0, 1, 3)

        comm.addWidget(QLabel("Zapisz?"), 1, 0)
        comm.addWidget(QLabel("Parametr"), 1, 1)
        comm.addWidget(QLabel("Wartość"), 1, 2)

        self.chk_dev_baud = QCheckBox()
        comm.addWidget(self.chk_dev_baud, 2, 0)
        comm.addWidget(QLabel("Prędkość (baud):"), 2, 1)
        self.cmb_dev_baud = QComboBox()
        self.cmb_dev_baud.addItems(BAUDRATES)
        self.cmb_dev_baud.setCurrentText("9600")
        comm.addWidget(self.cmb_dev_baud, 2, 2)

        self.chk_dev_parity = QCheckBox()
        comm.addWidget(self.chk_dev_parity, 3, 0)
        comm.addWidget(QLabel("Parzystość:"), 3, 1)
        self.cmb_dev_parity = QComboBox()
        self.cmb_dev_parity.addItems(list(PARITY_MAP.keys()))
        self.cmb_dev_parity.setCurrentText("NONE")
        comm.addWidget(self.cmb_dev_parity, 3, 2)

        self.chk_dev_stopbits = QCheckBox()
        comm.addWidget(self.chk_dev_stopbits, 4, 0)
        comm.addWidget(QLabel("Bity stopu:"), 4, 1)
        self.cmb_dev_stopbits = QComboBox()
        self.cmb_dev_stopbits.addItems(STOPBITS_OPTIONS)
        comm.addWidget(self.cmb_dev_stopbits, 4, 2)

        self.chk_dev_slave = QCheckBox()
        comm.addWidget(self.chk_dev_slave, 5, 0)
        comm.addWidget(QLabel("Adres Modbus (1-247):"), 5, 1)
        self.spn_dev_slave = QSpinBox()
        self.spn_dev_slave.setRange(1, 247)
        self.spn_dev_slave.setValue(1)
        comm.addWidget(self.spn_dev_slave, 5, 2)

        comm_btns = QHBoxLayout()
        self.btn_read_comm = QPushButton("Odczytaj parametry komunikacji")
        self.btn_read_comm.clicked.connect(self._on_read_communication_params)
        comm_btns.addWidget(self.btn_read_comm)

        self.btn_copy_from_a = QPushButton("Skopiuj z zakładki Połączenie")
        self.btn_copy_from_a.setToolTip(
            "Wypełnia pola wartościami używanymi obecnie przez aplikację (zaznaczając wszystkie checkboxy)."
        )
        self.btn_copy_from_a.clicked.connect(self._on_copy_from_section_a)
        comm_btns.addWidget(self.btn_copy_from_a)

        self.btn_write_comm = QPushButton("Zapisz zaznaczone")
        self.btn_write_comm.setStyleSheet("font-weight: bold; color: #aa6600;")
        self.btn_write_comm.clicked.connect(self._on_write_communication_params)
        comm_btns.addWidget(self.btn_write_comm)
        comm.addLayout(comm_btns, 6, 0, 1, 3)

        layout.addWidget(comm_box)

        # ---------- D-3: Alarmy ----------
        alarm_box = QGroupBox("D-3) Alarmy (bezpieczne, nie zrywają połączenia)")
        alarm = QGridLayout(alarm_box)

        alarm_info = QLabel(
            "Konfiguracja jednego z 4 niezależnych alarmów. Wybierz numer alarmu, "
            "ustaw próg, tryb i histerezę, a następnie zapisz. Przycisk "
            "„Odczytaj wybrany alarm\" wczytuje aktualne ustawienia z urządzenia."
        )
        alarm_info.setStyleSheet("color: #444; padding: 4px; background: #f4f4f4; border-radius: 3px;")
        alarm_info.setWordWrap(True)
        alarm.addWidget(alarm_info, 0, 0, 1, 2)

        alarm.addWidget(QLabel("Numer alarmu:"), 1, 0)
        self.cmb_alarm_no = QComboBox()
        self.cmb_alarm_no.addItems(["1", "2", "3", "4"])
        alarm.addWidget(self.cmb_alarm_no, 1, 1)

        alarm.addWidget(QLabel("Wartość progowa [°C] (-2048..2047):"), 2, 0)
        self.spn_alarm_value = QSpinBox()
        self.spn_alarm_value.setRange(-2048, 2047)
        alarm.addWidget(self.spn_alarm_value, 2, 1)

        alarm.addWidget(QLabel("Tryb wyzwalania:"), 3, 0)
        self.cmb_alarm_mode = QComboBox()
        self.cmb_alarm_mode.addItems(["Powyżej progu", "Poniżej progu"])
        alarm.addWidget(self.cmb_alarm_mode, 3, 1)

        alarm.addWidget(QLabel("Histereza [°C] (0-255):"), 4, 0)
        self.spn_alarm_hyst = QSpinBox()
        self.spn_alarm_hyst.setRange(0, 255)
        alarm.addWidget(self.spn_alarm_hyst, 4, 1)

        alarm_btns = QHBoxLayout()
        self.btn_read_alarm = QPushButton("Odczytaj wybrany alarm")
        self.btn_read_alarm.clicked.connect(self._on_read_alarm_config)
        alarm_btns.addWidget(self.btn_read_alarm)
        self.btn_write_alarm = QPushButton("Zapisz alarm")
        self.btn_write_alarm.setStyleSheet("font-weight: bold;")
        self.btn_write_alarm.clicked.connect(self._on_write_alarm_config)
        alarm_btns.addWidget(self.btn_write_alarm)
        alarm.addLayout(alarm_btns, 5, 0, 1, 2)

        layout.addWidget(alarm_box)

        layout.addStretch(1)
        return tab

    # ---------------------------------------------------------------------
    # ZAKŁADKA 4: Diagnostyka (log + info)
    # ---------------------------------------------------------------------
    def _build_tab_diagnostics(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Info o urządzeniu
        info_box = QGroupBox("Informacje o urządzeniu")
        info_grid = QGridLayout(info_box)

        info_grid.addWidget(QLabel("Identyfikator:"), 0, 0)
        self.lbl_dev_ident = QLineEdit("---")
        self.lbl_dev_ident.setReadOnly(True)
        info_grid.addWidget(self.lbl_dev_ident, 0, 1)

        info_grid.addWidget(QLabel("Numer seryjny:"), 1, 0)
        self.lbl_dev_serial = QLineEdit("---")
        self.lbl_dev_serial.setReadOnly(True)
        info_grid.addWidget(self.lbl_dev_serial, 1, 1)

        info_grid.addWidget(QLabel("Wersja firmware:"), 2, 0)
        self.lbl_dev_fw = QLineEdit("---")
        self.lbl_dev_fw.setReadOnly(True)
        info_grid.addWidget(self.lbl_dev_fw, 2, 1)

        info_grid.addWidget(QLabel("Czas pracy:"), 3, 0)
        self.lbl_dev_worktime = QLineEdit("---")
        self.lbl_dev_worktime.setReadOnly(True)
        info_grid.addWidget(self.lbl_dev_worktime, 3, 1)

        self.btn_read_info = QPushButton("Odczytaj informacje o urządzeniu")
        self.btn_read_info.clicked.connect(self._on_read_device_info)
        info_grid.addWidget(self.btn_read_info, 4, 0, 1, 2)

        layout.addWidget(info_box)

        # Alarmy - sprawdzenie stanu wszystkich 4 alarmów
        alarm_box = QGroupBox("Alarmy")
        alarm_layout = QVBoxLayout(alarm_box)
        self.btn_read_alarms = QPushButton("🔔 Sprawdź stan alarmów")
        self.btn_read_alarms.setToolTip(
            "Odczytuje status, próg, tryb i histerezę wszystkich 4 alarmów "
            "i wypisuje całą listę w logu poniżej."
        )
        self.btn_read_alarms.clicked.connect(self._on_read_alarms)
        alarm_layout.addWidget(self.btn_read_alarms)
        layout.addWidget(alarm_box)

        # Log
        log_box = QGroupBox("Log zdarzeń")
        log_layout = QVBoxLayout(log_box)
        self.txt_log = QPlainTextEdit()
        self.txt_log.setReadOnly(True)
        log_layout.addWidget(self.txt_log)

        log_btns = QHBoxLayout()
        btn_clear = QPushButton("Wyczyść log")
        btn_clear.clicked.connect(self.txt_log.clear)
        log_btns.addWidget(btn_clear)
        log_btns.addStretch(1)
        log_layout.addLayout(log_btns)

        layout.addWidget(log_box, stretch=1)
        return tab

    # =====================================================================
    # METODY POMOCNICZE
    # =====================================================================
    def _log(self, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.txt_log.appendPlainText(f"[{ts}] {message}")

    def _log_exception(self, where: str, exc: Exception) -> None:
        self._log(f"BŁĄD w {where}: {type(exc).__name__}: {exc}")
        for line in traceback.format_exc().splitlines():
            self._log(f"   {line}")

    def _refresh_com_ports(self) -> None:
        current = self.cmb_port.currentText()
        self.cmb_port.clear()
        ports = list_ports.comports()
        if not ports:
            self.cmb_port.addItem("(brak portów)")
            self._log("Nie znaleziono żadnych portów COM.")
            return

        for p in ports:
            label = f"{p.device} - {p.description}" if p.description else p.device
            self.cmb_port.addItem(label, userData=p.device)

        if current:
            idx = self.cmb_port.findText(current, Qt.MatchContains)
            if idx >= 0:
                self.cmb_port.setCurrentIndex(idx)

        self._log(f"Znaleziono {len(ports)} port(ów) COM.")

    def _selected_port_name(self) -> str | None:
        data = self.cmb_port.currentData()
        if data:
            return data
        text = self.cmb_port.currentText()
        if text and text.startswith("COM"):
            return text.split(" ")[0]
        return None

    def _update_buttons_state(self) -> None:
        connected = self.device is not None and self.device.is_connected()

        self.btn_connect.setEnabled(not connected)
        self.btn_disconnect.setEnabled(connected)
        self.cmb_port.setEnabled(not connected)
        self.cmb_baud.setEnabled(not connected)
        self.cmb_parity.setEnabled(not connected)
        self.cmb_stopbits.setEnabled(not connected)
        self.spn_slave.setEnabled(not connected)
        self.btn_refresh_ports.setEnabled(not connected)

        for btn in (
            self.btn_read_sensor, self.btn_write_sensor,
            self.btn_read_now, self.btn_reset_minmax,
            self.btn_read_meas, self.btn_write_meas,
            self.btn_read_comm, self.btn_write_comm,
            self.btn_read_info,
            self.btn_read_alarms, self.btn_read_alarm, self.btn_write_alarm,
            self.chk_cyclic,
        ):
            btn.setEnabled(connected)

        # "Skopiuj z zakładki Połączenie" działa zawsze - to tylko UI
        self.btn_copy_from_a.setEnabled(True)

        if connected:
            sb_str = _stopbits_to_str(self.device.stopbits)
            text = (
                f"Status: POŁĄCZONO  |  {self.device.port} @ {self.device.baudrate} "
                f"{self.device.bytesize}{self.device.parity}{sb_str}  |  "
                f"adres Modbus: {self.device.slave}"
            )
            self.lbl_status.setText(text)
            self.lbl_status.setStyleSheet("color: #006400; padding: 6px; background: #f0fff0; border-radius: 3px;")
        else:
            self.lbl_status.setText("Status: rozłączono")
            self.lbl_status.setStyleSheet("color: #b00020; padding: 6px; background: #fff0f0; border-radius: 3px;")

    def _require_connection(self) -> bool:
        if self.device is None or not self.device.is_connected():
            self._log("Operacja przerwana: brak połączenia z urządzeniem.")
            return False
        return True

    # =====================================================================
    # POŁĄCZENIE
    # =====================================================================
    def _on_connect(self) -> None:
        port = self._selected_port_name()
        if not port:
            self._log("Błąd: nie wybrano portu COM.")
            return

        try:
            baudrate = int(self.cmb_baud.currentText())
            parity = PARITY_MAP[self.cmb_parity.currentText()]
            stopbits_serial = _stopbits_to_serial(_stopbits_from_str(self.cmb_stopbits.currentText()))
            slave = self.spn_slave.value()
        except (ValueError, KeyError) as e:
            self._log(f"Błąd: nieprawidłowe parametry połączenia ({e}).")
            return

        self.device = ModbusTemperatureDevice(
            port=port, baudrate=baudrate, parity=parity,
            stopbits=stopbits_serial, slave=slave,
        )

        sb_str = self.cmb_stopbits.currentText()

        # Krok 1: otwarcie portu COM.
        try:
            self.device.connect()
        except ModbusDeviceError as e:
            self._log(f"Błąd otwarcia portu: {e}")
            self.device = None
            self._update_buttons_state()
            return
        except Exception as e:
            self._log_exception("connect()", e)
            self.device = None
            self._update_buttons_state()
            return

        # Krok 2: weryfikacja realnej komunikacji. Otwarty port jeszcze nic
        # nie znaczy - urządzenie musi faktycznie odpowiedzieć pod zadanym
        # adresem Modbus, zanim ogłosimy "połączono".
        if not self.device.ping():
            self._log(
                f"Port {port} otwarty, ale urządzenie NIE odpowiada pod adresem "
                f"Modbus {slave} ({baudrate} {parity}{sb_str}). "
                f"Sprawdź adres Modbus oraz parametry komunikacji."
            )
            self.device.disconnect()
            self.device = None
            self._update_buttons_state()
            return

        self._log(
            f"Połączono z {port} @ {baudrate} {parity}{sb_str}, "
            f"adres Modbus = {slave} - urządzenie odpowiada."
        )
        self._update_buttons_state()

    def _on_disconnect(self) -> None:
        if self.read_timer.isActive():
            self.read_timer.stop()
            self.chk_cyclic.setChecked(False)

        if self.device is not None:
            self.device.disconnect()
            self._log("Rozłączono.")
            self.device = None
        self._update_buttons_state()

    # =====================================================================
    # TYP TERMOPARY (tryb roboczy)
    # =====================================================================
    def _on_read_sensor_type(self) -> None:
        if not self._require_connection():
            return
        try:
            sensor = self.device.read_sensor_type()
            name = sensor_type_to_display_name(sensor)
            idx = self.cmb_sensor.findText(name)
            if idx >= 0:
                self.cmb_sensor.setCurrentIndex(idx)
            self._log(f"Odczytano typ termopary: {name} (kod {sensor.value}).")
        except ModbusDeviceError as e:
            self._log(f"Błąd odczytu typu termopary: {e}")
        except Exception as e:
            self._log_exception("read_sensor_type", e)

    def _on_write_sensor_type(self) -> None:
        if not self._require_connection():
            return
        try:
            sensor = display_name_to_sensor_type(self.cmb_sensor.currentText())
            self.device.write_sensor_type(sensor)
            self._log(f"Zapisano typ termopary: {self.cmb_sensor.currentText()}.")
        except KeyError:
            self._log("Błąd: nieprawidłowy typ termopary w GUI.")
        except ModbusDeviceError as e:
            self._log(f"Błąd zapisu typu termopary: {e}")
        except Exception as e:
            self._log_exception("write_sensor_type", e)

    # =====================================================================
    # ODCZYT TEMPERATURY
    # =====================================================================
    def _on_read_now(self) -> None:
        self._do_temperature_read(verbose=True)

    def _on_periodic_read(self) -> None:
        self._do_temperature_read(verbose=False)

    def _do_temperature_read(self, verbose: bool) -> None:
        if not self._require_connection():
            if self.read_timer.isActive():
                self.read_timer.stop()
                self.chk_cyclic.setChecked(False)
            return

        # Najpierw sprawdzamy, czy termopara jest w ogóle podłączona. Bez niej
        # urządzenie zwraca temperaturę złącza zimnego jako "pomiar" - to
        # mylące, więc zamiast wartości pokazujemy jednoznaczny błąd.
        try:
            if verbose:
                self._log("Sprawdzam stabilność pomiaru (seria próbek, ~3 s)...")
            if self.device.is_reading_unstable():
                for widget in (self.lbl_temp, self.lbl_temp_min, self.lbl_temp_max):
                    widget.setText("⚠ Niestabilny pomiar")
                # Złącze zimne to czujnik wewnętrzny - przy luźnym styku
                # termopary nadal jest wiarygodny, więc pokazujemy je normalnie.
                try:
                    self.lbl_cold.setText(f"{self.device.read_cold_junction():.1f} °C")
                except ModbusDeviceError:
                    self.lbl_cold.setText("BŁĄD")
                if verbose:
                    self._log("⚠ NIESTABILNY POMIAR - kanał termopary szumi, "
                              "prawdopodobnie luźny styk. Sprawdź połączenie.")
                return
        except ModbusDeviceError as e:
            if verbose:
                self._log(f"Nie udało się sprawdzić stabilności pomiaru: {e}")

        readings = {}
        errors = []

        for label, method, lbl_widget in [
            ("aktualna", self.device.read_temperature, self.lbl_temp),
            ("minimum", self.device.read_min_temperature, self.lbl_temp_min),
            ("maksimum", self.device.read_max_temperature, self.lbl_temp_max),
            ("złącze zimne", self.device.read_cold_junction, self.lbl_cold),
        ]:
            try:
                value = method()
                readings[label] = value
                lbl_widget.setText(f"{value:.1f} °C")
            except ModbusDeviceError as e:
                errors.append(f"{label}: {e}")
                lbl_widget.setText("BŁĄD")
            except Exception as e:
                errors.append(f"{label}: {type(e).__name__}: {e}")
                lbl_widget.setText("BŁĄD")
                if verbose and label == "aktualna":
                    self._log_exception("read_temperature", e)

        if verbose:
            if readings:
                parts = [f"{k}={v:.1f}" for k, v in readings.items()]
                self._log("Odczyt: " + ", ".join(parts) + " °C")
            if errors:
                for err in errors:
                    self._log(f"Błąd odczytu - {err}")

        try:
            if self.device.is_measurement_out_of_range():
                if verbose:
                    self._log("⚠ Pomiar poza zakresem wybranego typu termopary!")
        except ModbusDeviceError:
            pass
        except Exception:
            pass

        if not readings and self.read_timer.isActive():
            self.read_timer.stop()
            self.chk_cyclic.setChecked(False)
            self._log("Zatrzymano odczyt cykliczny - wszystkie odczyty zwracają błąd.")

    def _on_cyclic_toggled(self, checked: bool) -> None:
        if checked:
            if not self._require_connection():
                self.chk_cyclic.setChecked(False)
                return
            self.read_timer.start(self.spn_interval.value())
            self._log(f"Włączono odczyt cykliczny ({self.spn_interval.value()} ms).")
        else:
            self.read_timer.stop()
            self._log("Wyłączono odczyt cykliczny.")

    def _on_interval_changed(self, value: int) -> None:
        if self.read_timer.isActive():
            self.read_timer.setInterval(value)

    def _on_reset_min_max(self) -> None:
        if not self._require_connection():
            return
        try:
            self.device.reset_min_max()
            self._log("Wyzerowano Min/Max.")
            self._do_temperature_read(verbose=False)
        except ModbusDeviceError as e:
            self._log(f"Błąd resetu Min/Max: {e}")
        except Exception as e:
            self._log_exception("reset_min_max", e)

    # =====================================================================
    # D-1) PARAMETRY POMIARU
    # =====================================================================
    def _on_read_measurement_params(self) -> None:
        """Odczytuje aktualne wartości i automatycznie zaznacza wszystkie checkboxy."""
        if not self._require_connection():
            return
        try:
            sensor = self.device.read_sensor_type()
            avg = self.device.read_average_time()
            corr = self.device.read_correction()

            sensor_name = sensor_type_to_display_name(sensor)
            idx = self.cmb_dev_sensor.findText(sensor_name)
            if idx >= 0:
                self.cmb_dev_sensor.setCurrentIndex(idx)
            self.spn_avg_time.setValue(avg)
            self.spn_correction.setValue(corr)

            self.chk_dev_sensor.setChecked(True)
            self.chk_dev_avg.setChecked(True)
            self.chk_dev_corr.setChecked(True)

            self._log(
                f"Odczytano parametry pomiaru: typ = {sensor_name}, "
                f"liczba próbek = {avg}, korekcja = {corr:.1f}°C."
            )
        except ModbusDeviceError as e:
            self._log(f"Błąd odczytu parametrów pomiaru: {e}")
        except Exception as e:
            self._log_exception("read_measurement_params", e)

    def _on_write_measurement_params(self) -> None:
        """Zapisuje TYLKO te parametry, których checkbox jest zaznaczony."""
        if not self._require_connection():
            return

        to_write = []
        if self.chk_dev_sensor.isChecked():
            to_write.append("typ termopary")
        if self.chk_dev_avg.isChecked():
            to_write.append("liczba próbek")
        if self.chk_dev_corr.isChecked():
            to_write.append("korekcja")

        if not to_write:
            self._log("Nic nie zaznaczono do zapisu (sekcja D-1).")
            return

        self._log(f"Zapis do urządzenia: {', '.join(to_write)}")

        if self.chk_dev_sensor.isChecked():
            try:
                sensor_name = self.cmb_dev_sensor.currentText()
                sensor = display_name_to_sensor_type(sensor_name)
                self.device.write_sensor_type(sensor)
                self._log(f"  ✔ Typ termopary = {sensor_name}")
            except KeyError:
                self._log("  ✘ Błąd: nieprawidłowy typ termopary w GUI")
            except ModbusDeviceError as e:
                self._log(f"  ✘ Błąd zapisu typu termopary: {e}")
            except Exception as e:
                self._log_exception("write_sensor_type", e)

        if self.chk_dev_avg.isChecked():
            try:
                avg = self.spn_avg_time.value()
                self.device.write_average_time(avg)
                self._log(f"  ✔ Liczba próbek = {avg}")
            except ModbusDeviceError as e:
                self._log(f"  ✘ Błąd zapisu liczby próbek: {e}")
            except Exception as e:
                self._log_exception("write_average_time", e)

        if self.chk_dev_corr.isChecked():
            try:
                corr = self.spn_correction.value()
                self.device.write_correction(corr)
                self._log(f"  ✔ Korekcja = {corr:+.1f}°C")
            except ModbusDeviceError as e:
                self._log(f"  ✘ Błąd zapisu korekcji: {e}")
            except Exception as e:
                self._log_exception("write_correction", e)

    # =====================================================================
    # D-2) PARAMETRY KOMUNIKACJI
    # =====================================================================
    def _on_copy_from_section_a(self) -> None:
        """Kopiuje wartości z zakładki Połączenie i zaznacza wszystkie checkboxy."""
        idx = self.cmb_dev_baud.findText(self.cmb_baud.currentText())
        if idx >= 0:
            self.cmb_dev_baud.setCurrentIndex(idx)
        idx = self.cmb_dev_parity.findText(self.cmb_parity.currentText())
        if idx >= 0:
            self.cmb_dev_parity.setCurrentIndex(idx)
        idx = self.cmb_dev_stopbits.findText(self.cmb_stopbits.currentText())
        if idx >= 0:
            self.cmb_dev_stopbits.setCurrentIndex(idx)
        self.spn_dev_slave.setValue(self.spn_slave.value())

        self.chk_dev_baud.setChecked(True)
        self.chk_dev_parity.setChecked(True)
        self.chk_dev_stopbits.setChecked(True)
        self.chk_dev_slave.setChecked(True)
        self._log("Skopiowano wartości z zakładki Połączenie - wszystkie checkboxy zaznaczone.")

    def _on_read_communication_params(self) -> None:
        """Odczytuje aktualne parametry komunikacji i zaznacza checkboxy."""
        if not self._require_connection():
            return
        try:
            addr = self.device.read_modbus_address()
            baud = self.device.read_baudrate()
            par = self.device.read_parity()
            sb = self.device.read_stopbits()

            self.spn_dev_slave.setValue(addr)
            idx = self.cmb_dev_baud.findText(str(baud))
            if idx >= 0:
                self.cmb_dev_baud.setCurrentIndex(idx)
            par_label = PARITY_REVERSE.get(par, "NONE")
            idx = self.cmb_dev_parity.findText(par_label)
            if idx >= 0:
                self.cmb_dev_parity.setCurrentIndex(idx)
            sb_str = _stopbits_to_str(sb)
            idx = self.cmb_dev_stopbits.findText(sb_str)
            if idx >= 0:
                self.cmb_dev_stopbits.setCurrentIndex(idx)

            self.chk_dev_slave.setChecked(True)
            self.chk_dev_baud.setChecked(True)
            self.chk_dev_parity.setChecked(True)
            self.chk_dev_stopbits.setChecked(True)

            self._log(
                f"Odczytano parametry komunikacji urządzenia: adres = {addr}, "
                f"baud = {baud}, parzystość = {par_label}, stop bits = {sb_str}."
            )
        except ModbusDeviceError as e:
            self._log(f"Błąd odczytu parametrów komunikacji: {e}")
        except Exception as e:
            self._log_exception("read_communication_params", e)

    def _on_write_communication_params(self) -> None:
        """
        Zapisuje TYLKO zaznaczone parametry komunikacji do urządzenia.
        Po zapisie automatycznie rozłącza i pyta o reconnect.
        """
        if not self._require_connection():
            return

        to_write = []
        if self.chk_dev_stopbits.isChecked():
            to_write.append("bity stopu")
        if self.chk_dev_parity.isChecked():
            to_write.append("parzystość")
        if self.chk_dev_baud.isChecked():
            to_write.append("baudrate")
        if self.chk_dev_slave.isChecked():
            to_write.append("adres Modbus")

        if not to_write:
            self._log("Nic nie zaznaczono do zapisu (sekcja D-2).")
            return

        try:
            new_sb = _stopbits_from_str(self.cmb_dev_stopbits.currentText())
            new_par_label = self.cmb_dev_parity.currentText()
            new_par = PARITY_MAP[new_par_label]
            new_baud = int(self.cmb_dev_baud.currentText())
            new_addr = self.spn_dev_slave.value()
        except (ValueError, KeyError) as e:
            self._log(f"Błąd: nieprawidłowe wartości w sekcji D-2 ({e}).")
            return

        details = []
        if self.chk_dev_slave.isChecked():
            details.append(f"  • Adres Modbus: {new_addr}")
        if self.chk_dev_baud.isChecked():
            details.append(f"  • Baudrate: {new_baud}")
        if self.chk_dev_parity.isChecked():
            details.append(f"  • Parzystość: {new_par_label}")
        if self.chk_dev_stopbits.isChecked():
            details.append(f"  • Bity stopu: {self.cmb_dev_stopbits.currentText()}")

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Potwierdź zapis parametrów komunikacji")
        msg.setText(
            "Zapis parametrów komunikacji do urządzenia.\n\n"
            "Zostaną zmienione (tylko zaznaczone):\n"
            + "\n".join(details) +
            "\n\n"
            "Po zapisie urządzenie odpowie tylko z nowymi parametrami.\n"
            "Aplikacja automatycznie się rozłączy i zapyta o ponowne połączenie.\n\n"
            "Kontynuować?"
        )
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        if msg.exec() != QMessageBox.Yes:
            self._log("Zapis parametrów komunikacji anulowany.")
            return

        wrote_any = False

        if self.chk_dev_stopbits.isChecked():
            try:
                self.device.write_stopbits(new_sb)
                self._log(f"  ✔ Bity stopu = {self.cmb_dev_stopbits.currentText()}")
                wrote_any = True
            except ModbusDeviceError as e:
                self._log(f"  ✘ Błąd zapisu bitów stopu: {e}")
            except Exception as e:
                self._log_exception("write_stopbits", e)

        if self.chk_dev_parity.isChecked():
            try:
                self.device.write_parity(new_par)
                self._log(f"  ✔ Parzystość = {new_par_label}")
                wrote_any = True
            except ModbusDeviceError as e:
                self._log(f"  ✘ Błąd zapisu parzystości: {e}")
            except Exception as e:
                self._log_exception("write_parity", e)

        if self.chk_dev_baud.isChecked():
            try:
                self.device.write_baudrate(new_baud)
                self._log(f"  ✔ Baudrate = {new_baud}")
                wrote_any = True
            except ModbusDeviceError as e:
                self._log(f"  ✘ Błąd zapisu baudrate: {e}")
            except Exception as e:
                self._log_exception("write_baudrate", e)

        if self.chk_dev_slave.isChecked():
            try:
                self.device.write_modbus_address(new_addr)
                self._log(f"  ✔ Adres Modbus = {new_addr}")
                wrote_any = True
            except ModbusDeviceError as e:
                self._log(f"  ✘ Błąd zapisu adresu Modbus: {e}")
            except Exception as e:
                self._log_exception("write_modbus_address", e)

        if not wrote_any:
            self._log("Żaden parametr komunikacji nie został zapisany - nie rozłączam.")
            return

        self._on_disconnect()

        if self.chk_dev_baud.isChecked():
            idx = self.cmb_baud.findText(str(new_baud))
            if idx >= 0:
                self.cmb_baud.setCurrentIndex(idx)
        if self.chk_dev_parity.isChecked():
            idx = self.cmb_parity.findText(new_par_label)
            if idx >= 0:
                self.cmb_parity.setCurrentIndex(idx)
        if self.chk_dev_stopbits.isChecked():
            idx = self.cmb_stopbits.findText(self.cmb_dev_stopbits.currentText())
            if idx >= 0:
                self.cmb_stopbits.setCurrentIndex(idx)
        if self.chk_dev_slave.isChecked():
            self.spn_slave.setValue(new_addr)

        reconnect_msg = QMessageBox(self)
        reconnect_msg.setIcon(QMessageBox.Question)
        reconnect_msg.setWindowTitle("Połączyć ponownie?")
        reconnect_msg.setText(
            "Parametry zostały zapisane, aplikacja została rozłączona.\n"
            "Zakładka Połączenie została zaktualizowana.\n\n"
            "Czy połączyć ponownie z nowymi parametrami?"
        )
        reconnect_msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        reconnect_msg.setDefaultButton(QMessageBox.Yes)
        if reconnect_msg.exec() == QMessageBox.Yes:
            self._on_connect()
            if self.device is not None and self.device.is_connected():
                self.tabs.setCurrentIndex(1)
        else:
            self._log("Reconnect pominięty - kliknij Połącz w zakładce Połączenie gdy będziesz gotów.")
            self.tabs.setCurrentIndex(0)

    # =====================================================================
    # INFO O URZĄDZENIU
    # =====================================================================
    def _on_read_device_info(self) -> None:
        if not self._require_connection():
            return
        try:
            info = self.device.read_device_info()
            self.lbl_dev_serial.setText(str(info.get("serial", "---")))
            self.lbl_dev_fw.setText(info.get("firmware", "---"))

            wt = info.get("work_time_s", 0)
            days = wt // 86400
            hours = (wt % 86400) // 3600
            minutes = (wt % 3600) // 60
            seconds = wt % 60
            self.lbl_dev_worktime.setText(f"{wt} s  ({days}d {hours:02d}:{minutes:02d}:{seconds:02d})")

            try:
                ident_chars = []
                for i in range(6):
                    raw = self.device._read_holding_register(0x0406 + i)
                    ident_chars.append(chr((raw >> 8) & 0xFF))
                    ident_chars.append(chr(raw & 0xFF))
                ident = "".join(ident_chars).rstrip("\x00 ")
                self.lbl_dev_ident.setText(ident)
            except Exception:
                self.lbl_dev_ident.setText("---")

            self._log(f"Odczyt info: S/N={info.get('serial')}, FW={info.get('firmware')}, "
                      f"czas pracy={wt}s")
        except ModbusDeviceError as e:
            self._log(f"Błąd odczytu informacji: {e}")
        except Exception as e:
            self._log_exception("read_device_info", e)

    # =====================================================================
    # ALARMY
    # =====================================================================
    def _on_read_alarms(self) -> None:
        """Odczytuje pełny stan 4 alarmów i wypisuje całą listę w logu (Diagnostyka)."""
        if not self._require_connection():
            return
        try:
            ov = self.device.read_alarms_overview()
            self._log("=== STAN ALARMÓW (status: rejestr 0x0005) ===")
            for a in ov["alarms"]:
                stan = "⚠ WYZWOLONY" if a["triggered"] else "nieaktywny"
                tryb = "powyżej progu" if a["above"] else "poniżej progu"
                self._log(
                    f"  Alarm {a['alarm']}  [{stan}]  -  "
                    f"próg = {a['value']}°C ({tryb}), histereza = {a['hysteresis']}°C  "
                    f"(rej. wartości 0x{a['value_register']:04X}, "
                    f"histerezy 0x{a['hysteresis_register']:04X})"
                )
            if ov["out_of_range"]:
                self._log("  Pomiar: ⚠ POZA ZAKRESEM wybranego typu termopary (0x0005 bit 4)")
            else:
                self._log("  Pomiar: w zakresie wybranego typu termopary")
            self._log("=== koniec listy alarmów ===")
        except ModbusDeviceError as e:
            self._log(f"Błąd odczytu stanu alarmów: {e}")
        except Exception as e:
            self._log_exception("read_alarms", e)

    def _on_read_alarm_config(self) -> None:
        """Wczytuje konfigurację wybranego alarmu do pól sekcji D-3."""
        if not self._require_connection():
            return
        alarm = int(self.cmb_alarm_no.currentText())
        try:
            value = self.device.read_alarm_value(alarm)
            above = self.device.read_alarm_mode(alarm)
            hyst = self.device.read_alarm_hysteresis(alarm)

            self.spn_alarm_value.setValue(value)
            self.cmb_alarm_mode.setCurrentIndex(0 if above else 1)
            self.spn_alarm_hyst.setValue(hyst)

            self._log(
                f"Odczytano alarm {alarm}: próg = {value}°C, "
                f"tryb = {'powyżej progu' if above else 'poniżej progu'}, "
                f"histereza = {hyst}°C."
            )
        except ModbusDeviceError as e:
            self._log(f"Błąd odczytu alarmu {alarm}: {e}")
        except Exception as e:
            self._log_exception("read_alarm_config", e)

    def _on_write_alarm_config(self) -> None:
        """Zapisuje konfigurację wybranego alarmu: próg, tryb i histerezę."""
        if not self._require_connection():
            return

        alarm = int(self.cmb_alarm_no.currentText())
        value = self.spn_alarm_value.value()
        above = self.cmb_alarm_mode.currentIndex() == 0   # 0 = "Powyżej progu"
        hyst = self.spn_alarm_hyst.value()

        self._log(f"Zapis alarmu {alarm} do urządzenia:")

        try:
            self.device.write_alarm_value(alarm, value)
            self._log(f"  ✔ Wartość progowa = {value}°C")
        except ModbusDeviceError as e:
            self._log(f"  ✘ Błąd zapisu wartości progowej: {e}")
        except Exception as e:
            self._log_exception("write_alarm_value", e)

        try:
            self.device.write_alarm_mode(alarm, above)
            self._log(f"  ✔ Tryb wyzwalania = {'powyżej progu' if above else 'poniżej progu'}")
        except ModbusDeviceError as e:
            self._log(f"  ✘ Błąd zapisu trybu: {e}")
        except Exception as e:
            self._log_exception("write_alarm_mode", e)

        try:
            self.device.write_alarm_hysteresis(alarm, hyst)
            self._log(f"  ✔ Histereza = {hyst}°C")
        except ModbusDeviceError as e:
            self._log(f"  ✘ Błąd zapisu histerezy: {e}")
        except Exception as e:
            self._log_exception("write_alarm_hysteresis", e)

    # =====================================================================
    # OKNO "O PROGRAMIE"
    # =====================================================================
    def _show_about(self):
        QMessageBox.about(
            self,
            "O programie",
            "<b>MB-TC Configurator</b><br>"
            "Wersja 1.0.2<br><br>"
            "Konfigurator przetwornika temperatury F&amp;F MB-TC-1 (Modbus RTU).<br><br>"
            "Producent: <a href='https://sincore.io'>sincore.io</a><br>"
            "Kontakt: <a href='mailto:contact@sincore.io'>contact@sincore.io</a>",
        )

    # =====================================================================
    # ZAMKNIĘCIE OKNA
    # =====================================================================
    def closeEvent(self, event):
        if self.read_timer.isActive():
            self.read_timer.stop()
        if self.device is not None:
            self.device.disconnect()
        super().closeEvent(event)
