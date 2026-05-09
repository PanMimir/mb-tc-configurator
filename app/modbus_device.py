"""
modbus_device.py - klasa ModbusTemperatureDevice do komunikacji z F&F MB-TC-1
przez Modbus RTU / RS-485.

Wszystkie metody zwracają wartość przy sukcesie lub rzucają ModbusDeviceError
z czytelnym komunikatem przy problemie.

Adresy rejestrów - zgodne z dokumentacją MB-TC-1 (E230328), patrz registers.py.

OBSŁUGA RÓŻNYCH WERSJI PYMODBUS:
- pymodbus 3.7+ używa parametru `device_id`
- pymodbus 3.0-3.6 używa parametru `slave`
- pymodbus < 3.0 używa parametru `unit`
Klasa wykrywa to automatycznie przy pierwszym wywołaniu.
"""

from typing import Optional
import inspect

from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException

from app import registers
from app.sensor_types import SensorType
from app.utils import (
    raw_to_temperature,
    temperature_to_raw,
    to_signed_16,
    to_unsigned_16,
)


class ModbusDeviceError(Exception):
    """Wyjątek rzucany przy każdym błędzie komunikacji z urządzeniem."""
    pass


def _detect_slave_kwarg() -> str:
    """
    Wykrywa, jak nazywa się parametr identyfikatora slave w aktualnej
    wersji pymodbus (device_id / slave / unit). Wynik jest używany przy
    każdym wywołaniu read_holding_registers / write_register.
    """
    try:
        sig = inspect.signature(ModbusSerialClient.read_holding_registers)
        params = list(sig.parameters.keys())
        if "device_id" in params:
            return "device_id"
        if "slave" in params:
            return "slave"
        if "unit" in params:
            return "unit"
    except Exception:
        pass
    return "slave"  # fallback


# Wykrywamy raz przy ładowaniu modułu
_SLAVE_KWARG = _detect_slave_kwarg()


class ModbusTemperatureDevice:
    """
    Komunikacja z przetwornikiem F&F MB-TC-1 przez Modbus RTU.

    Przykład użycia:
        dev = ModbusTemperatureDevice(port="COM3", baudrate=9600,
                                      parity="N", stopbits=1, slave=1)
        dev.connect()
        temp = dev.read_temperature()
        dev.disconnect()
    """

    def __init__(
        self,
        port: str,
        baudrate: int = 9600,
        parity: str = "N",          # "N", "E" lub "O"
        stopbits: int = 1,          # 1 lub 2
        bytesize: int = 8,
        slave: int = registers.DEFAULT_SLAVE_ADDRESS,
        timeout: float = registers.DEFAULT_TIMEOUT,
    ):
        """
        Konstruktor - przygotowuje parametry połączenia. NIE otwiera portu.

        Parametry użytkownika z GUI:
        - port:     nazwa portu COM (np. "COM3")
        - baudrate: 1200..115200
        - parity:   "N" (NONE), "E" (EVEN), "O" (ODD)
        - stopbits: 1 lub 2
        - slave:    adres Modbus urządzenia (1-247)
        """
        self.port = port
        self.baudrate = baudrate
        self.parity = parity
        self.stopbits = stopbits
        self.bytesize = bytesize
        self.slave = slave
        self.timeout = timeout

        self._client: Optional[ModbusSerialClient] = None

    # ------------------------------------------------------------------
    # Połączenie / rozłączenie
    # ------------------------------------------------------------------
    def connect(self) -> None:
        """Otwiera port szeregowy. Rzuca ModbusDeviceError przy niepowodzeniu."""
        try:
            self._client = ModbusSerialClient(
                port=self.port,
                baudrate=self.baudrate,
                parity=self.parity,
                stopbits=self.stopbits,
                bytesize=self.bytesize,
                timeout=self.timeout,
            )
            ok = self._client.connect()
            if not ok:
                raise ModbusDeviceError(
                    f"Nie udało się otworzyć portu {self.port}. "
                    f"Sprawdź czy port istnieje i nie jest zajęty."
                )
        except ModbusDeviceError:
            raise
        except Exception as e:
            raise ModbusDeviceError(f"Błąd otwarcia portu: {e}")

    def disconnect(self) -> None:
        """Zamyka port. Bezpieczna do wielokrotnego wywołania."""
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    def is_connected(self) -> bool:
        """Zwraca True jeśli klient Modbus jest aktywny."""
        return self._client is not None and self._client.connected

    # ------------------------------------------------------------------
    # Odczyt temperatury - rejestry podstawowe
    # ------------------------------------------------------------------
    def read_temperature(self) -> float:
        """Aktualna temperatura bezwzględna złącza gorącego (rejestr 0x0000)."""
        raw = self._read_holding_register(registers.REG_TEMPERATURE_ABSOLUTE)
        return raw_to_temperature(raw)

    def read_temperature_relative(self) -> float:
        """Temperatura względna = gorące - zimne (rejestr 0x0001)."""
        raw = self._read_holding_register(registers.REG_TEMPERATURE_RELATIVE)
        return raw_to_temperature(raw)

    def read_cold_junction(self) -> float:
        """Temperatura złącza zimnego = wewnątrz urządzenia (rejestr 0x0002)."""
        raw = self._read_holding_register(registers.REG_TEMPERATURE_COLD_JUNCTION)
        return raw_to_temperature(raw)

    def read_min_temperature(self) -> float:
        """Zarejestrowane minimum (rejestr 0x0004)."""
        raw = self._read_holding_register(registers.REG_MIN_TEMPERATURE)
        return raw_to_temperature(raw)

    def read_max_temperature(self) -> float:
        """Zarejestrowane maksimum (rejestr 0x0003)."""
        raw = self._read_holding_register(registers.REG_MAX_TEMPERATURE)
        return raw_to_temperature(raw)

    def reset_min_max(self) -> None:
        """Zeruje min/max przez zapis 1 do rejestru 0x0012."""
        self._write_register(registers.REG_RESET_MIN_MAX, registers.RESET_MIN_MAX_COMMAND)

    # ------------------------------------------------------------------
    # Status i alarmy
    # ------------------------------------------------------------------
    def read_alarm_status(self) -> int:
        """Surowy status alarmów (rejestr 0x0005). Bity wg dokumentacji str. 11."""
        return self._read_holding_register(registers.REG_ALARM_STATUS)

    def is_measurement_out_of_range(self) -> bool:
        """True = pomiar poza zakresem aktualnego typu termopary (bit 4)."""
        status = self.read_alarm_status()
        return bool(status & (1 << registers.BIT_ALARM_STATUS_OUT_OF_RANGE))

    # ------------------------------------------------------------------
    # Typ termopary
    # ------------------------------------------------------------------
    def read_sensor_type(self) -> SensorType:
        """Aktualny typ termopary (rejestr 0x0006)."""
        raw = self._read_holding_register(registers.REG_SENSOR_TYPE)
        try:
            return SensorType(raw)
        except ValueError:
            raise ModbusDeviceError(
                f"Urządzenie zwróciło nieznany kod typu termopary: {raw}. "
                f"Zgodnie z dokumentacją powinien być 0-7."
            )

    def write_sensor_type(self, sensor: SensorType) -> None:
        """Zapisuje typ termopary do urządzenia (rejestr 0x0006)."""
        self._write_register(registers.REG_SENSOR_TYPE, sensor.value)

    # ------------------------------------------------------------------
    # Uśrednianie i korekcja
    # ------------------------------------------------------------------
    def read_average_time(self) -> int:
        """
        Liczba próbek do uśredniania (rejestr 0x0010).
        UWAGA: nazwa metody zachowana dla zgodności z GUI.
        Zakres: 0-30, gdzie 0 = przetwornik wyłączony.
        """
        return self._read_holding_register(registers.REG_AVERAGE_SAMPLES)

    def write_average_time(self, samples: int) -> None:
        """Liczba próbek do uśredniania (rejestr 0x0010, zakres 0-30)."""
        if samples < 0 or samples > 30:
            raise ModbusDeviceError(
                "Liczba próbek do uśredniania musi mieścić się w zakresie 0-30."
            )
        self._write_register(registers.REG_AVERAGE_SAMPLES, samples)

    def read_correction(self) -> float:
        """Korekta temperatury bezwzględnej w °C (rejestr 0x0011)."""
        raw = self._read_holding_register(registers.REG_CORRECTION)
        return raw_to_temperature(raw)

    def write_correction(self, correction: float) -> None:
        """Korekta temperatury w °C (rejestr 0x0011, zakres -100..100°C)."""
        if correction < -100 or correction > 100:
            raise ModbusDeviceError(
                "Korekta temperatury musi mieścić się w zakresie -100..100°C."
            )
        raw = temperature_to_raw(correction)
        self._write_register(registers.REG_CORRECTION, raw)

    # ------------------------------------------------------------------
    # USTAWIENIA KOMUNIKACJI - zapis zmienia parametry urządzenia,
    # po zapisie urządzenie nie odpowie na obecnym połączeniu!
    # ------------------------------------------------------------------
    def read_modbus_address(self) -> int:
        """Adres Modbus urządzenia (rejestr 0x0100)."""
        return self._read_holding_register(registers.REG_MODBUS_ADDRESS)

    def write_modbus_address(self, address: int) -> None:
        """
        Nowy adres Modbus urządzenia (rejestr 0x0100, zakres 1-247).
        UWAGA: po zapisie urządzenie odpowie tylko pod nowym adresem!
        """
        if address < 1 or address > 247:
            raise ModbusDeviceError("Adres Modbus musi być w zakresie 1-247.")
        self._write_register(registers.REG_MODBUS_ADDRESS, address)

    def read_baudrate(self) -> int:
        """Baudrate jako liczba bps (np. 9600). Czyta rejestr 0x0101 i dekoduje."""
        code = self._read_holding_register(registers.REG_BAUDRATE)
        if code not in registers.BAUDRATE_FROM_CODE:
            raise ModbusDeviceError(
                f"Urządzenie zwróciło nieznany kod baudrate: {code} (oczekiwane 0-7)."
            )
        return registers.BAUDRATE_FROM_CODE[code]

    def write_baudrate(self, baudrate: int) -> None:
        """
        Nowy baudrate (rejestr 0x0101). Argument w bps (np. 9600).
        UWAGA: po zapisie urządzenie odpowie tylko z nową prędkością!
        """
        if baudrate not in registers.BAUDRATE_CODES:
            raise ModbusDeviceError(
                f"Niedozwolony baudrate {baudrate}. "
                f"Dozwolone: {sorted(registers.BAUDRATE_CODES.keys())}."
            )
        self._write_register(registers.REG_BAUDRATE, registers.BAUDRATE_CODES[baudrate])

    def read_parity(self) -> str:
        """Parzystość jako 'N'/'E'/'O'. Czyta rejestr 0x0102 i dekoduje."""
        code = self._read_holding_register(registers.REG_PARITY)
        if code not in registers.PARITY_FROM_CODE:
            raise ModbusDeviceError(
                f"Urządzenie zwróciło nieznany kod parzystości: {code}."
            )
        return registers.PARITY_FROM_CODE[code]

    def write_parity(self, parity: str) -> None:
        """
        Nowa parzystość (rejestr 0x0102). Argument: 'N', 'E' lub 'O'.
        UWAGA: po zapisie urządzenie odpowie tylko z nową parzystością!
        """
        parity = parity.upper()
        if parity not in registers.PARITY_CODES:
            raise ModbusDeviceError(
                f"Niedozwolona parzystość '{parity}'. Dozwolone: N, E, O."
            )
        self._write_register(registers.REG_PARITY, registers.PARITY_CODES[parity])

    def read_stopbits(self) -> float:
        """
        Bity stopu (rejestr 0x0103). Zwraca 1, 1.5 lub 2.
        """
        code = self._read_holding_register(registers.REG_STOPBITS)
        if code in registers.STOPBITS_FROM_CODE:
            return registers.STOPBITS_FROM_CODE[code]
        raise ModbusDeviceError(
            f"Urządzenie zwróciło nieznany kod bitów stopu: {code}."
        )

    def write_stopbits(self, stopbits) -> None:
        """
        Nowe bity stopu (rejestr 0x0103). Argument: 1, 1.5 lub 2.
        UWAGA: po zapisie urządzenie odpowie tylko z nową konfiguracją!
        """
        if stopbits not in registers.STOPBITS_CODES:
            raise ModbusDeviceError(
                f"Niedozwolone bity stopu: {stopbits}. Dozwolone: 1, 1.5 lub 2."
            )
        self._write_register(registers.REG_STOPBITS, registers.STOPBITS_CODES[stopbits])

    # ------------------------------------------------------------------
    # Reset fabryczny
    # ------------------------------------------------------------------
    def factory_reset(self) -> None:
        """
        Przywraca konfigurację domyślną (zapis 1 do rejestru 0x0104).
        UWAGA: zmienia adres na 1, baudrate na 9600 N 1 - urządzenie nie
        odpowie na obecnym połączeniu!
        """
        self._write_register(registers.REG_FACTORY_RESET, registers.FACTORY_RESET_COMMAND)

    # ------------------------------------------------------------------
    # Informacje o urządzeniu (rejestry 0x0400-0x040F)
    # ------------------------------------------------------------------
    def read_device_info(self) -> dict:
        """
        Czyta zestaw informacji o urządzeniu i zwraca jako słownik.
        Klucze: 'serial', 'firmware', 'production_date', 'work_time_s', 'jumper'.
        """
        try:
            sn_high = self._read_holding_register(registers.REG_SERIAL_HIGH)
            sn_low = self._read_holding_register(registers.REG_SERIAL_LOW)
            serial = (sn_high << 16) | sn_low

            fw = self._read_holding_register(registers.REG_FIRMWARE_VERSION)
            firmware = f"{fw // 10}.{fw % 10}"

            date_raw = self._read_holding_register(registers.REG_PRODUCTION_DATE)
            day = date_raw & 0x1F
            month = (date_raw >> 5) & 0x0F
            year = ((date_raw >> 9) & 0x7F) + 2000
            production_date = f"{day:02d}.{month:02d}.{year}"

            wt_lsw = self._read_holding_register(registers.REG_WORK_TIME_LSW)
            wt_msw = self._read_holding_register(registers.REG_WORK_TIME_MSW)
            work_time_s = (wt_msw << 16) | wt_lsw

            jumper = self._read_holding_register(registers.REG_JUMPER_STATE)

            return {
                "serial": serial,
                "firmware": firmware,
                "production_date": production_date,
                "work_time_s": work_time_s,
                "jumper": "założona" if jumper else "zdjęta",
            }
        except ModbusDeviceError:
            raise

    # ==================================================================
    # METODY POMOCNICZE (prywatne)
    # ==================================================================
    def _read_holding_register(self, address: int) -> int:
        """
        Odczyt jednego rejestru typu Holding Register (funkcja Modbus 0x03).
        Zwraca wartość 16-bit unsigned. Rzuca ModbusDeviceError przy każdym problemie.
        """
        if not self.is_connected():
            raise ModbusDeviceError("Brak połączenia z urządzeniem.")

        # Buduj kwargs zgodne z wykrytą wersją pymodbus (device_id / slave / unit)
        kwargs = {"address": address, "count": 1, _SLAVE_KWARG: self.slave}

        try:
            result = self._client.read_holding_registers(**kwargs)
        except ModbusException as e:
            raise ModbusDeviceError(f"Wyjątek Modbus przy odczycie 0x{address:04X}: {e}")
        except Exception as e:
            raise ModbusDeviceError(f"Błąd odczytu rejestru 0x{address:04X}: {e}")

        if result is None:
            raise ModbusDeviceError(
                f"Brak odpowiedzi od urządzenia (timeout) - rejestr 0x{address:04X}."
            )
        if result.isError():
            raise ModbusDeviceError(
                f"Urządzenie zgłosiło błąd przy odczycie rejestru 0x{address:04X}: {result}"
            )
        if not getattr(result, "registers", None):
            raise ModbusDeviceError(
                f"Pusta odpowiedź urządzenia - rejestr 0x{address:04X}."
            )

        return result.registers[0]

    def _write_register(self, address: int, value: int) -> None:
        """Zapis jednego rejestru (funkcja Modbus 0x06)."""
        if not self.is_connected():
            raise ModbusDeviceError("Brak połączenia z urządzeniem.")

        # Konwersja signed -> unsigned
        value = to_unsigned_16(value) if value < 0 else (value & 0xFFFF)

        # Buduj kwargs zgodne z wykrytą wersją pymodbus
        kwargs = {"address": address, "value": value, _SLAVE_KWARG: self.slave}

        try:
            result = self._client.write_register(**kwargs)
        except ModbusException as e:
            raise ModbusDeviceError(f"Wyjątek Modbus przy zapisie 0x{address:04X}: {e}")
        except Exception as e:
            raise ModbusDeviceError(f"Błąd zapisu rejestru 0x{address:04X}: {e}")

        if result is None:
            raise ModbusDeviceError(
                f"Brak odpowiedzi od urządzenia (timeout) - zapis rejestru 0x{address:04X}."
            )
        if result.isError():
            raise ModbusDeviceError(
                f"Urządzenie zgłosiło błąd przy zapisie rejestru 0x{address:04X}: {result}"
            )
