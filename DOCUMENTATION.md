# MB-TC Configurator — pełna dokumentacja

Aplikacja desktopowa do konfiguracji i odczytu z przetwornika temperatury
**F&F MB-TC-1** (lub innego kompatybilnego modułu Modbus RTU) podłączonego
przez konwerter **RS-485 / USB**.

Spis treści:

1. [Opis ogólny i przeznaczenie](#1-opis-ogólny-i-przeznaczenie)
2. [Wymagania](#2-wymagania)
3. [Instalacja krok po kroku (Windows)](#3-instalacja-krok-po-kroku-windows)
4. [Instalacja na Linux / macOS](#4-instalacja-na-linux--macos)
5. [Budowanie pliku .exe](#5-budowanie-pliku-exe)
6. [Podłączenie sprzętu (RS-485)](#6-podłączenie-sprzętu-rs-485)
7. [Pierwsze uruchomienie](#7-pierwsze-uruchomienie)
8. [Opis interfejsu graficznego](#8-opis-interfejsu-graficznego)
9. [Architektura kodu](#9-architektura-kodu)
10. [API klasy `ModbusTemperatureDevice`](#10-api-klasy-modbustemperaturedevice)
11. [Funkcje pomocnicze (`utils.py`)](#11-funkcje-pomocnicze-utilspy)
12. [Mapa rejestrów (`registers.py`) — jak weryfikować i poprawiać](#12-mapa-rejestrów-registerspy--jak-weryfikować-i-poprawiać)
13. [Typy czujników (`sensor_types.py`)](#13-typy-czujników-sensor_typespy)
14. [Rozwiązywanie problemów (troubleshooting)](#14-rozwiązywanie-problemów-troubleshooting)
15. [FAQ](#15-faq)
16. [Słownik pojęć](#16-słownik-pojęć)

---

## 1. Opis ogólny i przeznaczenie

MB-TC Configurator powstał jako uproszczony, czytelny zamiennik programu
**MB Config** producenta. Pozwala na:

- nawiązanie połączenia z urządzeniem przez RS-485 (Modbus RTU),
- odczyt aktualnej, minimalnej i maksymalnej temperatury,
- cykliczny odczyt z konfigurowalnym interwałem,
- wybór typu czujnika (K, N, PT100 i inne),
- ustawienie czasu uśredniania i korekcji (offsetu) temperatury,
- log zdarzeń ze znacznikami czasowymi (przydatny przy diagnostyce).

Aplikacja celowo **nie ma** zaawansowanych funkcji takich jak skanowanie
magistrali, edytor mapy rejestrów czy wykresy — żeby pozostać prosta.

> **Ważne:** mapę rejestrów Modbus dla MB-TC-1 należy zweryfikować z
> oficjalną dokumentacją producenta przed pierwszym **zapisem** parametrów.
> Patrz [§12](#12-mapa-rejestrów-registerspy--jak-weryfikować-i-poprawiać).

---

## 2. Wymagania

**Sprzętowe:**

- Komputer z portem USB (lub RS-485, jeśli komputer dysponuje natywnym).
- Konwerter USB ↔ RS-485 (np. CH340, FT232, Moxa UPort).
- Przewód dwużyłowy (skrętka wystarczy) do połączenia A/B.
- Opcjonalnie: rezystor 120 Ω do terminacji.

**Programowe (do uruchamiania ze źródeł):**

- Python **3.11+** (zalecane 3.12).
- pip / venv.

**Programowe (jeśli używasz gotowego .exe):**

- Windows 10 lub 11 (64-bit).
- Brak innych wymagań — `MB-TC-Configurator.exe` zawiera wszystko, co potrzebne.

---

## 3. Instalacja krok po kroku (Windows)

### Wariant A — gotowy `.exe` (rekomendowany dla użytkownika końcowego)

1. Otrzymaj plik `MB-TC-Configurator.exe`.
2. Skopiuj go w dowolne miejsce (np. `C:\Programy\MB-TC\`).
3. (Opcjonalnie) Stwórz skrót na pulpicie: prawy klik na pliku → **Wyślij do →
   Pulpit (utwórz skrót)**.
4. Uruchom dwuklikiem.

Aplikacja jest **portable** — nie wymaga instalacji ani uprawnień
administratora.

### Wariant B — uruchamianie ze źródeł

1. Zainstaluj Pythona 3.11+ ze [strony oficjalnej](https://www.python.org/downloads/).
   Podczas instalacji zaznacz **„Add Python to PATH”**.
2. Rozpakuj projekt do dowolnego katalogu (np. `C:\Projects\mb_tc_configurator`).
3. Otwórz wiersz poleceń (`cmd`) w tym katalogu.
4. Wykonaj kolejno:

   ```cmd
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   python main.py
   ```

5. Aplikacja powinna się uruchomić.

Aby zamknąć virtualenv: `deactivate`.

---

## 4. Instalacja na Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

**Linux — uprawnienia do portu szeregowego:**

Pod Linuksem dostęp do `/dev/ttyUSB0` (lub `/dev/ttyACM0`) wymaga członkostwa
w grupie `dialout` (Debian/Ubuntu) lub `uucp` (Arch). Dodaj się jednorazowo:

```bash
sudo usermod -a -G dialout $USER
```

…i wyloguj/zaloguj. Inaczej `pyserial` zwróci `Permission denied`.

---

## 5. Budowanie pliku .exe

### Wymagania

- Python 3.11+ na Windowsie z aktywnym virtualenv.
- Pakiet `pyinstaller` (zainstaluje się automatycznie ze skryptu).

### Krok po kroku — najprostsza droga

1. Rozpakuj projekt.
2. Otwórz katalog projektu w Eksploratorze plików.
3. Kliknij dwukrotnie plik `build_exe.bat`.
4. Po zakończeniu otrzymasz plik wykonywalny w:

   ```
   dist\MB-TC-Configurator.exe
   ```

Skrypt sam:

- utworzy virtualenv `.venv` (jeśli nie istnieje),
- zainstaluje wszystkie zależności runtime + PyInstaller,
- skompiluje aplikację do jednego pliku `.exe`,
- ustawi ikonę termometru,
- włączy `--noconsole` (brak okna konsoli).

### Krok po kroku — ręcznie

```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-build.txt
pyinstaller --clean mb_tc_configurator.spec
```

Wynik: `dist\MB-TC-Configurator.exe`.

### Modyfikacja konfiguracji budowy

Plik `mb_tc_configurator.spec` zawiera:

- `console=False` — brak okna konsoli. Zmień na `True` jeśli chcesz widzieć
  ewentualne błędy `print()`/`stderr`.
- `icon='icon.ico'` — ścieżka do ikony.
- `excludes=[...]` — lista modułów wyłączonych z paczki, żeby zmniejszyć rozmiar.
- `upx=True` — kompresja UPX (jeśli `upx.exe` jest w PATH; nie jest wymagana).

### Co robić, jeśli antywirus blokuje `.exe`?

PyInstaller czasami daje fałszywe alarmy (zwłaszcza Windows Defender / SmartScreen).
Dwa rozwiązania:

1. Dodaj plik do wykluczeń antywirusa.
2. Podpisz `.exe` certyfikatem (Authenticode). To jest poza zakresem tego
   projektu — wymaga zakupu certyfikatu od CA (np. Sectigo, DigiCert).

---

## 6. Podłączenie sprzętu (RS-485)

```
+----------------+              +-------------------+
| Komputer + USB |              |   F&F MB-TC-1     |
|                |              |                   |
|   USB - 485    |              |   RS-485 (A,B)    |
|   konwerter    |              |   GND             |
|   [A][B][GND]  |              |   [A][B][GND]     |
+--------+-------+              +---------+---------+
         |                                |
    A ---+--------------------------------+--- A
    B ---+--------------------------------+--- B
   GND --+--------------------------------+--- GND  (jeśli wymagane)
```

**Najczęstsze pomyłki:**

- Zamiana A↔B — najczęstszy problem; objawia się brakiem komunikacji lub
  losowymi błędami CRC. Zamień przewody i spróbuj ponownie.
- Pomylenie linii: niektóre konwertery mają oznaczenia `D+`/`D-` zamiast
  `A`/`B`. Standard RS-485: **A = D+ (HIGH spoczynkowe)**, **B = D- (LOW)**.
- Brak GND — przy dłuższych kablach lub różnicach potencjałów (różne
  zasilacze) komunikacja potrafi „odpływać”. Połącz GND.
- Brak terminacji — w długich magistralach lub przy dużych prędkościach
  dodaj rezystor 120 Ω między A i B na obu końcach linii.
- Wiele urządzeń z tym samym adresem Modbus na jednej magistrali — kolizja
  odpowiedzi. Każde urządzenie musi mieć unikalny adres (1-247).

**Domyślne parametry MB-TC-1 (typowe):** `9600 N 1`, adres `1`. Sprawdź w
dokumentacji konkretnego egzemplarza.

---

## 7. Pierwsze uruchomienie

1. Podłącz konwerter USB-RS485 do komputera. Windows powinien wykryć go
   jako port COM (np. `COM3`).
2. Uruchom aplikację (`MB-TC-Configurator.exe` lub `python main.py`).
3. W sekcji **A) Połączenie**:
   - Wybierz port COM z listy. Jeśli nie widać, kliknij **Odśwież listę**.
   - Wybierz parametry transmisji (domyślnie `9600 / NONE / 1`).
   - Wpisz adres Modbus urządzenia (domyślnie `1`).
   - Kliknij **Połącz**.
4. Status na górze powinien zmienić się na zielone „POŁĄCZONO”.
5. W sekcji **C) Odczyt temperatury** kliknij **Odczytaj teraz**.
   Powinieneś zobaczyć aktualną temperaturę.

Jeśli odczyt się nie udaje — patrz [§14 Troubleshooting](#14-rozwiązywanie-problemów-troubleshooting).

---

## 8. Opis interfejsu graficznego

### Sekcja A — Połączenie

| Pole | Opis |
|------|------|
| Port COM | Lista wykrytych portów szeregowych. Aktualizuje się po **Odśwież listę**. |
| Prędkość (baud) | 1200..115200. Musi pasować do ustawienia urządzenia. |
| Parzystość | NONE / EVEN / ODD. Najczęściej NONE. |
| Bity stopu | 1 lub 2. Najczęściej 1. |
| Adres Modbus | 1-247. Adres urządzenia w sieci. |
| Połącz / Rozłącz | Otwiera/zamyka port szeregowy. |

### Sekcja B — Typ czujnika

| Element | Opis |
|---------|------|
| Lista typów | K, N, PT100, J, T, E, R, S, B, PT500, PT1000. |
| Odczytaj typ | Wczytuje aktualne ustawienie z urządzenia. |
| Zapisz typ | Wysyła wybrany typ do urządzenia. |

### Sekcja C — Odczyt temperatury

| Element | Opis |
|---------|------|
| Aktualna / Minimum / Maksimum | Trzy pola z odczytami w °C. |
| Odczytaj teraz | Pojedyncze pobranie wszystkich trzech wartości. |
| Odczyt cykliczny | Włącza odczyt co X ms. |
| Interwał [ms] | 100..600000. Zmiana działa „w locie”. |
| Zeruj Min/Max | Resetuje zarejestrowane skrajne wartości. |

### Sekcja D — Konfiguracja

| Element | Opis |
|---------|------|
| Czas uśredniania [s] | 0..3600. Liczba sekund, przez które urządzenie uśrednia odczyt. |
| Korekcja temperatury [°C] | Offset. Dodawany do każdego odczytu. |
| Odczytaj konfigurację | Wczytuje obie wartości z urządzenia. |
| Zapisz konfigurację | Wysyła obie wartości do urządzenia. |

### Sekcja E — Log zdarzeń

Każda akcja użytkownika oraz każdy błąd jest dopisywany z czasem
(`HH:MM:SS`). Przycisk **Wyczyść log** czyści okno.

---

## 9. Architektura kodu

```
mb_tc_configurator/
├── main.py                 # punkt wejścia - tworzy QApplication i MainWindow
├── requirements.txt        # zależności runtime
├── requirements-build.txt  # zależności do budowy .exe
├── mb_tc_configurator.spec # konfiguracja PyInstallera
├── build_exe.bat           # one-click build na Windowsie
├── icon.ico                # ikona aplikacji
├── README.md               # krótki opis
├── DOCUMENTATION.md        # ten plik
└── app/
    ├── __init__.py
    ├── gui.py              # MainWindow + budowa wszystkich sekcji
    ├── modbus_device.py    # ModbusTemperatureDevice (warstwa komunikacji)
    ├── registers.py        # adresy rejestrów (DO WERYFIKACJI!)
    ├── sensor_types.py     # Enum SensorType + nazwy do GUI
    └── utils.py            # konwersje signed/unsigned, skalowanie temperatury
```

**Przepływ danych — przykład „Odczytaj teraz”:**

```
[Kliknięcie przycisku]
        │
        ▼
gui.py: _on_read_now()
        │  → wywołuje device.read_temperature()
        ▼
modbus_device.py: read_temperature()
        │  → _read_holding_register(REG_TEMPERATURE)
        ▼
pymodbus: read_holding_registers(address=0x0000, count=1, slave=1)
        │  → wysyła ramkę RTU przez port COM
        ▼
[Konwerter USB→RS-485 → urządzenie → odpowiedź ramką RTU]
        ▼
pymodbus zwraca obiekt ReadHoldingRegistersResponse
        │
        ▼
modbus_device.py: zwraca raw_value (int 0..65535)
        │
        ▼
utils.py: raw_to_temperature() → float w °C
        │
        ▼
gui.py: aktualizuje QLineEdit + log
```

---

## 10. API klasy `ModbusTemperatureDevice`

Plik: `app/modbus_device.py`

### Konstruktor

```python
ModbusTemperatureDevice(
    port: str,                         # np. "COM3"
    baudrate: int = 9600,
    parity: str = "N",                 # "N" | "E" | "O"
    stopbits: int = 1,                 # 1 | 2
    bytesize: int = 8,
    slave: int = 1,                    # 1..247
    timeout: float = 1.0,              # sekundy
)
```

Tylko zapamiętuje parametry — **nie otwiera** portu. Aby otworzyć, wywołaj
`connect()`.

### Metody publiczne

| Metoda | Zwraca | Opis |
|--------|--------|------|
| `connect()` | `None` | Otwiera port. Rzuca `ModbusDeviceError` przy niepowodzeniu. |
| `disconnect()` | `None` | Zamyka port. Bezpieczna do wielokrotnego wywołania. |
| `is_connected()` | `bool` | Czy port jest otwarty i klient połączony. |
| `read_temperature()` | `float` (°C) | Aktualna temperatura. |
| `read_min_temperature()` | `float` (°C) | Zarejestrowane minimum. |
| `read_max_temperature()` | `float` (°C) | Zarejestrowane maksimum. |
| `reset_min_max()` | `None` | Zeruje min/max. |
| `read_sensor_type()` | `SensorType` | Aktualny typ czujnika. |
| `write_sensor_type(sensor)` | `None` | Ustawia typ czujnika. |
| `read_average_time()` | `int` (s) | Czas uśredniania. |
| `write_average_time(seconds)` | `None` | Ustawia czas uśredniania. |
| `read_correction()` | `float` (°C) | Korekcja (offset). |
| `write_correction(correction)` | `None` | Ustawia korekcję. |

### Wyjątki

Wszystkie metody publiczne mogą rzucić `ModbusDeviceError` z opisowym
komunikatem po polsku. Sytuacje, w których to się dzieje:

- Brak połączenia (próba odczytu/zapisu bez wcześniejszego `connect()`).
- Timeout — urządzenie nie odpowiada w `timeout` sekundach.
- Błąd CRC / błąd ramki — przekłamanie na linii.
- Odpowiedź wyjątkowa Modbus (`isError() == True`) — np. urządzenie
  zgłasza nieznany rejestr lub niedozwoloną wartość.
- Wartość zwrócona przez `read_sensor_type()` nie pasuje do żadnego elementu
  Enuma `SensorType` — patrz [§13](#13-typy-czujników-sensor_typespy).

### Przykład użycia poza GUI (skrypt CLI)

```python
from app.modbus_device import ModbusTemperatureDevice, ModbusDeviceError

dev = ModbusTemperatureDevice(port="COM3", baudrate=9600, slave=1)
try:
    dev.connect()
    print("Aktualna T:", dev.read_temperature(), "°C")
    print("Min:",       dev.read_min_temperature(), "°C")
    print("Max:",       dev.read_max_temperature(), "°C")
except ModbusDeviceError as e:
    print("Błąd Modbus:", e)
finally:
    dev.disconnect()
```

---

## 11. Funkcje pomocnicze (`utils.py`)

| Funkcja | Opis |
|---------|------|
| `to_signed_16(value)` | Konwertuje unsigned int16 (0..65535) na signed (-32768..32767). |
| `to_unsigned_16(value)` | Odwrotność powyższej. |
| `raw_to_temperature(raw)` | Zamienia wartość rejestru na °C. Zakłada signed int16 ×10. |
| `temperature_to_raw(temp)` | Zamienia °C na wartość rejestru. |

**Stała kluczowa:**

```python
TEMP_SCALE = 10.0  # 253 -> 25.3°C
```

Jeśli urządzenie używa innego skalowania (np. ×1 lub ×100), zmień tylko
tę stałą — wszystkie miejsca w kodzie, które przeliczają temperaturę,
korzystają z `raw_to_temperature` / `temperature_to_raw`.

**Przykłady:**

```python
raw_to_temperature(253)      # → 25.3
raw_to_temperature(0xFF97)   # → -10.5  (signed: -105 / 10)
temperature_to_raw(25.3)     # → 253
temperature_to_raw(-10.5)    # → 65431 (czyli 0xFF97)
```

---

## 12. Mapa rejestrów (`registers.py`) — jak weryfikować i poprawiać

To jest **najważniejsza** sekcja dokumentacji. Wszystkie adresy w
`registers.py` są **wstępnym założeniem** i muszą zostać zweryfikowane z
oficjalną dokumentacją MB-TC-1.

### Aktualna zawartość pliku

```python
REG_TEMPERATURE      = 0x0000  # aktualna temperatura
REG_MIN_TEMPERATURE  = 0x0001  # minimum
REG_MAX_TEMPERATURE  = 0x0002  # maksimum
REG_SENSOR_TYPE      = 0x0003  # typ czujnika
REG_AVERAGE_TIME     = 0x0004  # czas uśredniania
REG_CORRECTION       = 0x0005  # korekcja (offset)
REG_RESET_MIN_MAX    = 0x0006  # rejestr polecenia "reset min/max"
RESET_MIN_MAX_COMMAND = 1      # wartość zapisywana do rejestru powyżej
```

### Jak zweryfikować, że adres jest dobry?

**Metoda 1 — porównanie z dokumentacją (najpewniejsza).**

Otwórz dokumentację techniczną MB-TC-1 (PDF od F&F). Powinna zawierać
tabelę typu:

| Adres | Funkcja | Opis | Typ |
|-------|---------|------|-----|
| 0x0000 | 0x03 | Temperatura | int16 |
| 0x0001 | 0x03 | Min | int16 |
| ... | ... | ... | ... |

Porównaj liczba po liczbie ze stałymi w `registers.py` i popraw te, które
się różnią.

**Metoda 2 — eksperymentalna (jeśli nie masz dokumentacji).**

> ⚠️ Ryzyko: zapis pod nieznany adres może uszkodzić konfigurację urządzenia.
> Tej metody używaj **tylko do odczytów**, nigdy do zapisów.

1. Połącz się z urządzeniem.
2. W konsoli Pythona:

   ```python
   from pymodbus.client import ModbusSerialClient
   c = ModbusSerialClient(port="COM3", baudrate=9600)
   c.connect()
   for addr in range(0, 32):
       r = c.read_holding_registers(address=addr, count=1, slave=1)
       if not r.isError() and r.registers:
           print(f"0x{addr:04X}: {r.registers[0]} (signed: {r.registers[0]-65536 if r.registers[0]>32767 else r.registers[0]})")
   ```

3. Porównaj odczytane wartości z fizyczną temperaturą. Adres, który zwraca
   liczbę bliską temperaturze otoczenia × 10 (np. 235 przy 23.5°C), to
   prawdopodobnie `REG_TEMPERATURE`.

### Jak zmienić adres

Edytuj plik `app/registers.py`, zmień wartość heksadecymalną przy danej
stałej, zapisz, uruchom aplikację ponownie. Nie trzeba przebudowywać `.exe` —
ale jeśli masz tylko `.exe` (bez źródeł), musisz wrócić do źródeł.

### Co jeśli urządzenie używa Input Registers (funkcja 0x04) zamiast Holding (0x03)?

Otwórz `app/modbus_device.py`, w metodzie `_read_holding_register()` zmień:

```python
result = self._client.read_holding_registers(...)
# na
result = self._client.read_input_registers(...)
```

(lub stwórz osobną metodę `_read_input_register` i przerouteruj wybrane
metody publiczne).

### Co jeśli wartość jest 32-bitowa (np. float w 2 rejestrach)?

To wymaga większej zmiany w `_read_holding_register()` — odczytu `count=2`
i złożenia bajtów. Skontaktuj się z autorem albo zmodyfikuj samodzielnie:

```python
result = self._client.read_holding_registers(address=addr, count=2, slave=self.slave)
high, low = result.registers
combined = (high << 16) | low
# jeśli IEEE 754 float:
import struct
value = struct.unpack(">f", struct.pack(">I", combined))[0]
```

---

## 13. Typy czujników (`sensor_types.py`)

Klasa `SensorType` — wartości liczbowe to kody zapisywane do rejestru
`REG_SENSOR_TYPE`. **Zweryfikuj w dokumentacji**, bo różni producenci kodują
typy różnie:

```python
class SensorType(Enum):
    THERMOCOUPLE_K = 1
    THERMOCOUPLE_N = 2
    PT100 = 3
    THERMOCOUPLE_J = 4
    THERMOCOUPLE_T = 5
    THERMOCOUPLE_E = 6
    THERMOCOUPLE_R = 7
    THERMOCOUPLE_S = 8
    THERMOCOUPLE_B = 9
    PT500 = 10
    PT1000 = 11
```

**Przykład poprawki**, jeśli dokumentacja MB-TC-1 mówi że K=0, N=1, PT100=2:

```python
class SensorType(Enum):
    THERMOCOUPLE_K = 0
    THERMOCOUPLE_N = 1
    PT100 = 2
    # ...
```

Słownik `SENSOR_DISPLAY_NAMES` mapuje nazwy z GUI na wartości Enuma — można
go przeporządkować, żeby zmienić kolejność na liście rozwijanej.

### Co zrobić, jeśli urządzenie zwraca kod, którego nie ma w Enumie?

`read_sensor_type()` rzuci `ModbusDeviceError` z komunikatem typu
*"Urządzenie zwróciło nieznany kod typu czujnika: 12"*. Wtedy:

1. Sprawdź dokumentację — może to inny typ, którego brakuje w Enumie.
2. Dodaj brakującą pozycję do `SensorType` i `SENSOR_DISPLAY_NAMES`.

---

## 14. Rozwiązywanie problemów (troubleshooting)

### „Nie znaleziono żadnych portów COM”

- Sprawdź, czy konwerter USB-RS485 jest podłączony.
- W Menedżerze urządzeń sprawdź, czy widać go jako port COM. Jeśli nie —
  zainstaluj sterowniki (CH340, FTDI, Prolific zależnie od układu).
- Kliknij **Odśwież listę** w aplikacji.

### „Nie udało się otworzyć portu COMx”

- Port jest zajęty przez inny program (np. terminal, MB Config, Realterm).
  Zamknij konkurencję.
- Brak uprawnień (Linux): patrz [§4](#4-instalacja-na-linux--macos).

### „Brak odpowiedzi od urządzenia (timeout)”

To najczęstszy błąd. Możliwe przyczyny:

1. **Złe parametry transmisji** — baudrate, parzystość, stop bits muszą
   pasować do ustawień urządzenia. Sprawdź dokumentację lub fabryczne
   ustawienia.
2. **Zły adres Modbus** — jeśli wpisałeś `1`, a urządzenie ma adres `5`,
   nie odpowie. Spróbuj różnych adresów (1, 2, ... 247) lub zresetuj
   urządzenie do ustawień fabrycznych.
3. **Zamiana A↔B** — patrz [§6](#6-podłączenie-sprzętu-rs-485).
4. **Brak zasilania urządzenia** — banalne, ale często.
5. **Brak terminacji 120 Ω** — zwłaszcza przy długich kablach.
6. **Złe sterowanie kierunkiem transmisji** — niektóre tańsze konwertery
   wymagają „pauzy” między TX i RX. Spróbuj zmniejszyć baudrate.

### „Urządzenie zgłosiło błąd przy odczycie 0xXXXX”

- Adres rejestru jest nieprawidłowy. Patrz [§12](#12-mapa-rejestrów-registerspy--jak-weryfikować-i-poprawiać).
- Urządzenie wymaga innej funkcji Modbus (Input Registers vs Holding).

### „Urządzenie zwróciło nieznany kod typu czujnika”

Patrz [§13](#13-typy-czujników-sensor_typespy).

### Aplikacja zamarza po kliknięciu „Odczytaj”

To znaczy, że urządzenie nie odpowiada, a timeout został ustawiony zbyt
długo. Domyślnie 1 sekunda — można zmienić w `registers.py`:
`DEFAULT_TIMEOUT = 0.5`.

### Antywirus blokuje `MB-TC-Configurator.exe`

Patrz [§5 - antywirus](#5-budowanie-pliku-exe).

### Przy odczycie cyklicznym log szybko się zapełnia

Cykliczny odczyt **nie loguje** standardowych odczytów (tylko błędy). Jeśli
mimo to log puchnie — sprawdź, czy nie ma serii błędów (timeoutów). Aplikacja
sama zatrzymuje cykliczny odczyt po pierwszym błędzie.

---

## 15. FAQ

**Q: Czy aplikacja działa z modułami innych producentów (nie F&F)?**
A: Tak, jeśli używają Modbus RTU. Wystarczy poprawić mapę rejestrów w
`registers.py` i ewentualnie kody typów czujników w `sensor_types.py`.

**Q: Czy mogę używać aplikacji równocześnie z MB Config producenta?**
A: Nie. Port szeregowy w danym momencie obsługuje tylko jedna aplikacja.

**Q: Czy aplikacja pamięta ostatnie ustawienia (port, baudrate)?**
A: Nie. Pierwsza wersja świadomie nie zapisuje konfiguracji — aby zachować
prostotę. To jest naturalne rozszerzenie do dodania (np. `QSettings`).

**Q: Czy mogę odczytywać kilka urządzeń jednocześnie?**
A: Aplikacja obsługuje **jedno** urządzenie naraz na danym porcie COM. Aby
odpytać kolejne, rozłącz się i zmień adres Modbus, potem połącz ponownie.
Wszystkie urządzenia na tej samej magistrali muszą mieć **różne** adresy.

**Q: Co z eksportem danych do CSV / wykresami?**
A: Nie ma ich w tej wersji (świadoma decyzja - prostota). Można dodać:
- gui.py: dopisać przycisk „Zapisz log do CSV”,
- albo użyć skryptu Python z [§10](#10-api-klasy-modbustemperaturedevice) i
  loggować do pliku.

**Q: Plik .exe ma 50+ MB — czy można zmniejszyć?**
A: Tak, jeśli zainstalujesz UPX (`upx.exe` z [upx.github.io](https://upx.github.io/))
i dodasz go do PATH przed budową. Plik `.spec` ma już `upx=True`. UPX
potrafi zmniejszyć rozmiar o 40-60%.

**Q: Jak dodać autorefresh listy COM przy podłączeniu konwertera?**
A: Wymagałoby to nasłuchiwania zdarzeń systemowych (WM_DEVICECHANGE na
Windowsie). Prostsze rozwiązanie: użytkownik klika **Odśwież listę**.

---

## 16. Słownik pojęć

| Pojęcie | Wyjaśnienie |
|---------|-------------|
| **Modbus RTU** | Binarny protokół komunikacyjny, najczęściej po RS-485. Każda ramka zawiera adres slave, kod funkcji, dane, CRC. |
| **Slave / adres Modbus** | Numer identyfikujący urządzenie na magistrali (1-247). |
| **Holding Register** | Rejestr 16-bitowy do odczytu/zapisu. Funkcje 0x03 (read), 0x06 (write single), 0x10 (write multiple). |
| **Input Register** | Rejestr 16-bitowy tylko do odczytu. Funkcja 0x04. |
| **CRC** | 16-bitowa suma kontrolna na końcu każdej ramki Modbus RTU. |
| **Termopara** | Czujnik temperatury wykorzystujący zjawisko Seebecka (różnica potencjałów dwóch metali). |
| **PT100/PT500/PT1000** | Czujniki rezystancyjne z platyny — rezystancja rośnie liniowo z temperaturą. |
| **RS-485** | Standard transmisji szeregowej różnicowej, do 1200 m, do 32 (lub więcej) urządzeń. |
| **Terminacja** | Rezystor 120 Ω między A i B na końcach magistrali — eliminuje odbicia sygnału. |
| **Baudrate** | Liczba zmian sygnału na sekundę (≈ liczba bitów/s w prostym kodowaniu). |
| **Parzystość** | Dodatkowy bit kontroli błędów: NONE/EVEN/ODD. |
| **Timeout** | Maksymalny czas oczekiwania na odpowiedź. |
| **PyInstaller** | Narzędzie pakujące skrypt Pythona w samodzielny plik wykonywalny. |
| **Virtualenv (venv)** | Izolowane środowisko Pythona — nie zaśmieca systemowej instalacji. |

---

*Dokumentacja dla wersji 1.0 — `mb_tc_configurator`. W razie błędów lub
braków w mapie rejestrów: patrz [§12](#12-mapa-rejestrów-registerspy--jak-weryfikować-i-poprawiać).*
