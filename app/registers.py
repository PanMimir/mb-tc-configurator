"""
registers.py - mapa rejestrów F&F MB-TC-1.

ZWERYFIKOWANE z oficjalną dokumentacją producenta (E230328).
Strona 10-15 dokumentacji:
- Rejestry podstawowe: 0x00-0x04
- Ustawienia przetwornika: 0x05-0x12
- Ustawienia komunikacji: 0x100-0x103
- Pozostałe: 0x104, 0x400-0x40F

Wszystkie temperatury są wartościami signed int16 pomnożonymi przez 10
(np. 253 = 25.3°C, -105 = -10.5°C).

Wszystkie rejestry są typu Holding Register:
- odczyt funkcją 0x03 (Read Holding Registers)
- zapis funkcją 0x06 (Write Single Register)
"""

# ===========================================================================
# REJESTRY PODSTAWOWE (tylko odczyt)
# ===========================================================================

REG_TEMPERATURE_ABSOLUTE = 0x0000   # Temperatura bezwzględna złącza gorącego
REG_TEMPERATURE_RELATIVE = 0x0001   # Temperatura względna (gorące - zimne)
REG_TEMPERATURE_COLD_JUNCTION = 0x0002  # Temperatura złącza zimnego (wewnątrz urządzenia)
REG_MAX_TEMPERATURE = 0x0003        # Zarejestrowane maksimum
REG_MIN_TEMPERATURE = 0x0004        # Zarejestrowane minimum

# Alias dla kompatybilności z istniejącym kodem GUI
REG_TEMPERATURE = REG_TEMPERATURE_ABSOLUTE

# ===========================================================================
# USTAWIENIA PRZETWORNIKA
# ===========================================================================

REG_ALARM_STATUS = 0x0005           # Status alarmów (R) - patrz BIT_ALARM_STATUS_*
REG_SENSOR_TYPE = 0x0006            # Rodzaj termopary (R/W) - patrz SensorType
REG_ALARM_MODE = 0x0007             # Tryb wyzwalania alarmów (R/W) - patrz BIT_ALARM_MODE_*

REG_ALARM_HYSTERESIS_1 = 0x0008     # Histereza alarmu 1 (0-255) (R/W)
REG_ALARM_HYSTERESIS_2 = 0x0009     # Histereza alarmu 2 (0-255) (R/W)
REG_ALARM_HYSTERESIS_3 = 0x000A     # Histereza alarmu 3 (0-255) (R/W)
REG_ALARM_HYSTERESIS_4 = 0x000B     # Histereza alarmu 4 (0-255) (R/W)

REG_ALARM_VALUE_1 = 0x000C          # Wartość alarmu 1 (-2048..2047) (R/W)
REG_ALARM_VALUE_2 = 0x000D          # Wartość alarmu 2 (-2048..2047) (R/W)
REG_ALARM_VALUE_3 = 0x000E          # Wartość alarmu 3 (-2048..2047) (R/W)
REG_ALARM_VALUE_4 = 0x000F          # Wartość alarmu 4 (-2048..2047) (R/W)

REG_AVERAGE_SAMPLES = 0x0010        # Liczba próbek do uśredniania (0-30, 0=wyłączony) (R/W)

# Alias dla kompatybilności z istniejącym kodem GUI
# UWAGA: w MB-TC-1 to jest LICZBA PRÓBEK, nie czas w sekundach!
REG_AVERAGE_TIME = REG_AVERAGE_SAMPLES

REG_CORRECTION = 0x0011             # Korekta temperatury bezwzględnej (-100..100°C) (R/W)
REG_RESET_MIN_MAX = 0x0012          # Wpisanie 1 = reset min/max (odczyt zawsze 0) (R/W)

# ===========================================================================
# USTAWIENIA KOMUNIKACJI (R/W) - ZMIANA WYMAGA RECONNECTU!
# ===========================================================================

REG_MODBUS_ADDRESS = 0x0100         # Adres Modbus (1-247)
REG_BAUDRATE = 0x0101               # Prędkość transmisji - patrz BAUDRATE_CODES
REG_PARITY = 0x0102                 # Parzystość - patrz PARITY_CODES
REG_STOPBITS = 0x0103               # Bity stopu - patrz STOPBITS_CODES

# ===========================================================================
# POZOSTAŁE REJESTRY (tylko odczyt)
# ===========================================================================

REG_FACTORY_RESET = 0x0104          # Wpisanie 1 przywraca konfigurację domyślną (R/W)
REG_WORK_TIME_LSW = 0x0400          # Czas pracy [s] - młodsza część 32-bit (R)
REG_WORK_TIME_MSW = 0x0401          # Czas pracy [s] - starsza część 32-bit (R)
REG_SERIAL_HIGH = 0x0402            # Numer seryjny - starsza część (R)
REG_SERIAL_LOW = 0x0403             # Numer seryjny - młodsza część (R)
REG_PRODUCTION_DATE = 0x0404        # Data produkcji (5b dzień, 4b miesiąc, 7b rok-2000) (R)
REG_FIRMWARE_VERSION = 0x0405       # Wersja firmware (10 = "1.0") (R)
REG_DEVICE_ID_START = 0x0406        # Początek napisu "F&F_MB-TC-1" (6 rejestrów = 12 znaków, R)
REG_DEVICE_ID_LENGTH = 6
REG_JUMPER_STATE = 0x040F           # Stan zworki konfiguracyjnej (0=zdjęta, 1=założona) (R)

# ===========================================================================
# WARTOŚCI ZAPISYWANE DO REJESTRÓW POLECEŃ
# ===========================================================================

RESET_MIN_MAX_COMMAND = 1           # Wpisz 1 do REG_RESET_MIN_MAX żeby zresetować min/max
FACTORY_RESET_COMMAND = 1           # Wpisz 1 do REG_FACTORY_RESET żeby przywrócić ustawienia

# ===========================================================================
# KODY PARAMETRÓW KOMUNIKACJI (zgodnie z dokumentacją str. 14)
# ===========================================================================

# REG_BAUDRATE (0x0101)
BAUDRATE_CODES = {
    1200:   0,
    2400:   1,
    4800:   2,
    9600:   3,
    19200:  4,
    38400:  5,
    57600:  6,
    115200: 7,
}
BAUDRATE_FROM_CODE = {v: k for k, v in BAUDRATE_CODES.items()}

# REG_PARITY (0x0102)
PARITY_CODES = {
    "N": 0,   # NONE / brak
    "E": 1,   # EVEN / parzysta
    "O": 2,   # ODD / nieparzysta
}
PARITY_FROM_CODE = {v: k for k, v in PARITY_CODES.items()}

# REG_STOPBITS (0x0103)
# Dokumentacja MB-TC-1: 0=1 bit, 1=1.5 bita, 2=2 bity
STOPBITS_CODES = {
    1: 0,      # 1 bit stopu
    1.5: 1,    # 1.5 bita stopu (nietypowe, ale obsługiwane przez urządzenie)
    2: 2,      # 2 bity stopu
}
STOPBITS_FROM_CODE = {0: 1, 1: 1.5, 2: 2}

# ===========================================================================
# BITY W REJESTRZE STATUSU ALARMÓW (REG_ALARM_STATUS, 0x0005)
# ===========================================================================
# UWAGA: dla bitów alarmów 0-3: 0 = wyzwolony, 1 = nieaktywny
# Dla bitu 4: 1 = pomiar POZA ZAKRESEM (błąd)

BIT_ALARM_STATUS_OUT_OF_RANGE = 4
BIT_ALARM_STATUS_ALARM_4 = 3
BIT_ALARM_STATUS_ALARM_3 = 2
BIT_ALARM_STATUS_ALARM_2 = 1
BIT_ALARM_STATUS_ALARM_1 = 0

# ===========================================================================
# BITY W REJESTRZE TRYBU ALARMÓW (REG_ALARM_MODE, 0x0007)
# ===========================================================================
# 1 = wyzwalany powyżej zadanej temperatury, 0 = poniżej
#
# ZWERYFIKOWANE NA SPRZĘCIE 2026-05-21: bit=1 -> wyzwala gdy temp >= próg,
# bit=0 -> wyzwala gdy temp <= próg. UWAGA: str. 2 instrukcji (przykłady
# ustawień) ma to ODWROTNIE - to błąd producenta. Prawidłowa jest tabela
# rejestrów (str. 12). Wartość alarmu (0x0C-0x0F) jest w SUROWYCH °C, nie ×10
# - również zweryfikowane na sprzęcie.

BIT_ALARM_MODE_ALARM_4 = 3
BIT_ALARM_MODE_ALARM_3 = 2
BIT_ALARM_MODE_ALARM_2 = 1
BIT_ALARM_MODE_ALARM_1 = 0

# ===========================================================================
# Domyślne parametry komunikacji
# ===========================================================================

DEFAULT_TIMEOUT = 1.0               # timeout odpowiedzi Modbus [s]
DEFAULT_SLAVE_ADDRESS = 1           # domyślny adres Modbus urządzenia (1-247)
