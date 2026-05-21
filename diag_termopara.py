"""
diag_termopara.py - diagnostyka wykrywania odłączonej termopary (F&F MB-TC-1).

Cel: ustalić, czym urządzenie sygnalizuje odłączoną termoparę. Bez tego nie
da się pewnie wykryć rozłączenia w aplikacji - MB-TC-1 przy otwartym wejściu
nie podnosi oczywistej flagi, tylko zwraca temperaturę złącza zimnego.

UŻYCIE - uruchomić DWUKROTNIE w oknie dostępu do sprzętu, venv-owym Pythonem:

    .venv\\Scripts\\python diag_termopara.py podlaczona
    .venv\\Scripts\\python diag_termopara.py odlaczona

Każdy przebieg zapisuje diag_termopara_<etykieta>.txt. Oba pliki potem
porównujemy - różnica między stanami pokaże sygnał "termopara odłączona".

Wskazówka: dla stanu "podlaczona" najlepiej, żeby termopara mierzyła
temperaturę WYRAŹNIE inną niż otoczenie (np. potrzymać ją w dłoni) - wtedy
temperatura względna będzie wyraźnie niezerowa. Można też zrobić trzeci
przebieg "podlaczona_otoczenie" (termopara podpięta, ale w temp. otoczenia),
żeby sprawdzić ryzyko fałszywego alarmu heurystyki.

Parametry połączenia: COM7, 9600 N 1, adres Modbus 11 (egzemplarz testowy).
"""
import sys
import time

from app.modbus_device import ModbusTemperatureDevice, ModbusDeviceError

PORT, BAUD, PARITY, STOPBITS, ADDRESS = "COM7", 9600, "N", 1, 11
SAMPLES = 30
INTERVAL_S = 0.3

# Rejestry śledzone w czasie (nazwa -> adres) - pomiar i status.
WATCH = [
    ("abs_0x00", 0x00),
    ("rel_0x01", 0x01),
    ("cold_0x02", 0x02),
    ("max_0x03", 0x03),
    ("min_0x04", 0x04),
    ("status_0x05", 0x05),
]


def main() -> int:
    if len(sys.argv) < 2:
        print("Uzycie: python diag_termopara.py <etykieta_stanu>")
        print("Przyklady:  podlaczona  |  odlaczona  |  podlaczona_otoczenie")
        return 1
    state = sys.argv[1].strip().replace(" ", "_")

    out_lines = []

    def out(text=""):
        print(text)
        out_lines.append(text)

    dev = ModbusTemperatureDevice(port=PORT, baudrate=BAUD, parity=PARITY,
                                  stopbits=STOPBITS, slave=ADDRESS, timeout=1.0)
    try:
        dev.connect()
    except ModbusDeviceError as e:
        print(f"Blad otwarcia portu: {e}")
        return 2
    if not dev.ping():
        print(f"Urzadzenie nie odpowiada ({PORT} {BAUD}{PARITY}{STOPBITS}, adres {ADDRESS}).")
        dev.disconnect()
        return 2

    out(f"=== DIAGNOSTYKA TERMOPARY - STAN: {state.upper()} ===")
    out(f"{PORT} {BAUD} {PARITY} {STOPBITS}, adres {ADDRESS}, "
        f"{SAMPLES} probek co {INTERVAL_S}s")
    out()

    # --- seria próbek w czasie (pokazuje stabilność / szum) ---
    history = {name: [] for name, _ in WATCH}
    header = "proba | " + " | ".join(f"{n:>12}" for n, _ in WATCH)
    out(header)
    out("-" * len(header))
    for i in range(SAMPLES):
        cells = []
        for name, addr in WATCH:
            try:
                value = dev._read_holding_register(addr)
            except ModbusDeviceError:
                value = None
            history[name].append(value)
            cells.append(f"{str(value):>12}")
        out(f"{i + 1:5} | " + " | ".join(cells))
        time.sleep(INTERVAL_S)

    # --- analiza stabilności surowych wartości ---
    out()
    out("=== ANALIZA (surowe wartosci rejestrow) ===")
    for name, _ in WATCH:
        vals = [v for v in history[name] if v is not None]
        if not vals:
            out(f"  {name}: brak odczytow")
            continue
        uniq = sorted(set(vals))
        kind = "STALE" if len(uniq) == 1 else f"ZMIENNE ({len(uniq)} wartosci)"
        out(f"  {name}: min={min(vals)} max={max(vals)} {kind}")

    # --- status 0x05 rozbity na bity (szukamy flagi, ktora zmienia sie miedzy stanami) ---
    out()
    out("=== status 0x05 - unikalne wartosci bitowo ===")
    for v in sorted(set(x for x in history["status_0x05"] if x is not None)):
        out(f"  0x{v:04X} = {v:016b}  "
            f"(bit4={v >> 4 & 1} bit3={v >> 3 & 1} bit2={v >> 2 & 1} "
            f"bit1={v >> 1 & 1} bit0={v & 1})")

    # --- pełny skan 0x00-0x1F (raz) - na wypadek nieudokumentowanego rejestru/flagi ---
    out()
    out("=== pelny skan rejestrow 0x00-0x1F (jednokrotnie) ===")
    for addr in range(0x00, 0x20):
        try:
            v = dev._read_holding_register(addr)
            out(f"  0x{addr:04X} = {v:6d}  0x{v:04X}  {v:016b}")
        except ModbusDeviceError as e:
            out(f"  0x{addr:04X} = BLAD ({e})")

    dev.disconnect()

    fname = f"diag_termopara_{state}.txt"
    with open(fname, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines))
    print()
    print(f"Zapisano: {fname}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
