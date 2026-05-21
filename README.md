# MB-TC Configurator

Prosta aplikacja desktopowa do konfiguracji i odczytu z przetwornika temperatury
**F&F MB-TC-1** (lub innego kompatybilnego modułu Modbus RTU) podłączonego
przez konwerter **RS-485 / USB**.

Aplikacja ma być prostszym i czytelniejszym odpowiednikiem programu *MB Config*.

> **📖 Pełna dokumentacja:** patrz [`DOCUMENTATION.md`](DOCUMENTATION.md) —
> opis architektury, API, mapy rejestrów, troubleshooting i FAQ.

## Funkcje

- Otwieranie / zamykanie portu COM (RS-485) z wyborem prędkości, parzystości,
  liczby bitów stopu i adresu Modbus urządzenia.
- Odczyt aktualnej temperatury, minimum i maksimum.
- Odczyt cykliczny z konfigurowalnym interwałem.
- Reset Min/Max.
- Odczyt i zapis typu czujnika (K, N, PT100, J, T, E, R, S, B, PT500, PT1000).
- Odczyt i zapis konfiguracji: czas uśredniania, korekcja (offset) temperatury.
- Podgląd stanu 4 alarmów temperaturowych (Diagnostyka) — status, próg, tryb, histereza.
- Konfiguracja alarmów — zapis progu, trybu wyzwalania (powyżej / poniżej) i histerezy.
- Weryfikacja połączenia — „Połącz" potwierdza, że urządzenie faktycznie odpowiada.
- Log zdarzeń ze znacznikami czasu (połączenia, błędy, timeouty, zapisy).
- Wykrywanie niestabilnego pomiaru — sygnalizuje luźny / przerywany styk termopary.

> **Uwaga — wykrywanie odłączonej termopary:** aplikacja wykrywa *luźny / przerywany
> styk* (odczyt zaczyna chaotycznie szumieć). Natomiast **czystego, całkowitego
> rozłączenia** termopary MB-TC-1 nie sygnalizuje w żaden sposób — przy otwartym
> wejściu podaje stabilną wartość zbliżoną do temperatury otoczenia, nieodróżnialną
> od realnego pomiaru. To ograniczenie sprzętu. Stabilny odczyt bliski temperaturze
> pokojowej warto zweryfikować fizycznie.

## Najszybszy start (Windows)

### Wariant 1: pobierz gotowy .exe (zalecane)

Pobierz najnowszy `MB-TC-Configurator.exe` z
**[GitHub Releases](https://github.com/PanMimir/mb-tc-configurator/releases/latest)**
i uruchom dwuklikiem. Nie wymaga instalacji Pythona ani żadnych zależności.

- **Wymagania:** Windows 10 / 11 (64-bit)
- Plik nie jest podpisany cyfrowo — jeśli pojawi się ekran **SmartScreen**,
  kliknij „Więcej informacji" → „Uruchom mimo to".

### Wariant 2: zbuduj .exe samodzielnie

```cmd
build_exe.bat
```

Skrypt sam stworzy virtualenv, zainstaluje zależności, zbuduje
`dist\MB-TC-Configurator.exe`. Szczegóły: [DOCUMENTATION.md §5](DOCUMENTATION.md#5-budowanie-pliku-exe).

### Wariant 3: uruchom ze źródeł

## Wymagania

- Python 3.11+ (tylko jeśli uruchamiasz ze źródeł lub budujesz .exe)
- Windows (testowane), powinno też działać na Linuksie / macOS.
- Konwerter USB ↔ RS-485 (np. CH340, FT232, Moxa).

## Instalacja ze źródeł

```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Na Linuksie / macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Podłączenie RS-485

- **A** urządzenia ↔ **A** konwertera (czasem oznaczane jako **D+**)
- **B** urządzenia ↔ **B** konwertera (czasem oznaczane jako **D-**)
- **GND** urządzenia ↔ **GND** konwertera — jeśli wymagane (zwiększa
  niezawodność, szczególnie przy długich kablach lub różnicach potencjałów).
- **Terminacja 120 Ω** — jeśli magistrala jest długa lub urządzenie znajduje
  się na końcu linii, zalecane jest dodanie rezystora 120 Ω między A i B
  (na obu końcach magistrali).

Domyślne parametry transmisji wielu modułów F&F MB-TC-1: **9600 N 1**, adres **1**.
Jeśli urządzenie nie odpowiada — sprawdź dokumentację oraz fabryczne ustawienia.

## Struktura projektu

```
mb_tc_configurator/
│
├── main.py                     # punkt wejścia
├── requirements.txt            # zależności runtime
├── requirements-build.txt      # zależności do budowy .exe (PyInstaller)
├── mb_tc_configurator.spec     # konfiguracja PyInstallera
├── build_exe.bat               # one-click build na Windowsie
├── icon.ico                    # ikona aplikacji
├── README.md                   # ten plik (skrót)
├── DOCUMENTATION.md            # PEŁNA DOKUMENTACJA
│
└── app/
    ├── __init__.py
    ├── gui.py                  # interfejs PySide6
    ├── modbus_device.py        # klasa ModbusTemperatureDevice
    ├── registers.py            # mapa rejestrów (zweryfikowane z E230328)
    ├── sensor_types.py         # Enum SensorType + mapowania nazw
    └── utils.py                # skalowanie i konwersja signed/unsigned
```

