##############################################################################
#
#  MB-TC Configurator (F&F MB-TC-1) — Skrypt diagnostyczny
#  ========================================================
#
#  Testuje wszystkie warstwy polaczenia od portu COM do urzadzenia.
#  Uzyj tego skryptu po zainstalowaniu programu na nowym komputerze
#  (lub przy podejrzeniu problemu z komunikacja) zanim odpalisz GUI.
#
#  INSTRUKCJA:
#  1. Skopiuj ten plik do katalogu projektu mb_tc_configurator
#  2. Otworz PowerShell w tym katalogu
#  3. Uruchom: .\diagnose_mb_tc.ps1
#
#  WYMAGANIA:
#  - Python 3.11+ z bibliotekami: pyserial, pymodbus, PySide6
#  - LUB aktywny venv z projektu MB-TC Configurator (.venv\Scripts\activate)
#
##############################################################################

$ErrorActionPreference = "Continue"

# Kolory
function Write-OK     { param($msg) Write-Host "  [OK]    $msg" -ForegroundColor Green }
function Write-FAIL   { param($msg) Write-Host "  [FAIL]  $msg" -ForegroundColor Red }
function Write-WARN   { param($msg) Write-Host "  [WARN]  $msg" -ForegroundColor Yellow }
function Write-INFO   { param($msg) Write-Host "  [INFO]  $msg" -ForegroundColor Cyan }
function Write-Header { param($msg) Write-Host "`n============================================" -ForegroundColor White; Write-Host "  $msg" -ForegroundColor White; Write-Host "============================================" -ForegroundColor White }

Write-Host ""
Write-Host "  MB-TC Configurator (F&F MB-TC-1)" -ForegroundColor Cyan
Write-Host "  DIAGNOSTYKA POLACZENIA" -ForegroundColor Cyan
Write-Host "  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
Write-Host ""

# ===========================================================================
# TEST 1: Python
# ===========================================================================
Write-Header "TEST 1: Srodowisko Python"

$pythonCmd = $null

# Szukaj python w venv
if (Test-Path ".\.venv\Scripts\python.exe") {
    $pythonCmd = ".\.venv\Scripts\python.exe"
    Write-OK "Znaleziono Python w .venv: $pythonCmd"
} elseif (Test-Path ".\venv\Scripts\python.exe") {
    $pythonCmd = ".\venv\Scripts\python.exe"
    Write-OK "Znaleziono Python w venv: $pythonCmd"
} else {
    # Szukaj systemowego
    try {
        $ver = python --version 2>&1
        if ($ver -match "Python 3") {
            $pythonCmd = "python"
            Write-OK "Znaleziono systemowy Python: $ver"
        }
    } catch {}
}

if (-not $pythonCmd) {
    Write-FAIL "Python nie znaleziony! Zainstaluj Python 3.11+ lub aktywuj venv."
    Write-INFO "Komendy: python -m venv .venv ; .venv\Scripts\activate ; pip install -r requirements.txt"
    exit 1
}

# Sprawdz wersje
$pyVer = & $pythonCmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>&1
Write-INFO "Wersja Python: $pyVer"

# Sprawdz czy to nie WSL python
$pyPath = & $pythonCmd -c "import sys; print(sys.executable)" 2>&1
if ($pyPath -match "/usr/bin") {
    Write-FAIL "UWAGA: To jest Python z WSL ($pyPath)! Uzyj windowsowego Pythona."
    Write-INFO "Rozwiazanie: Zainstaluj Python ze strony python.org i utworz nowy venv"
    exit 1
}
Write-OK "Sciezka Python: $pyPath"

# ===========================================================================
# TEST 2: Biblioteki
# ===========================================================================
Write-Header "TEST 2: Wymagane biblioteki"

$testLibs = @'
import sys
libs = {
    "serial": "pyserial",
    "pymodbus": "pymodbus",
    "PySide6": "PySide6",
}
ok = True
for module, pip_name in libs.items():
    try:
        m = __import__(module)
        ver = getattr(m, "__version__", getattr(m, "VERSION", "?"))
        print(f"OK|{pip_name}|{ver}")
    except ImportError:
        print(f"FAIL|{pip_name}|nie zainstalowana")
        ok = False

# Sprawdz pymodbus API (rozne wersje uzywaja: device_id / slave / unit)
try:
    from pymodbus.client import ModbusSerialClient
    import inspect
    sig = inspect.signature(ModbusSerialClient.read_holding_registers)
    params = list(sig.parameters.keys())
    if "device_id" in params:
        print(f"WARN|pymodbus-api|parametr: device_id (pymodbus 3.7+) - aplikacja uzywa 'slave', moze wymagac update")
    elif "slave" in params:
        print(f"OK|pymodbus-api|parametr: slave (zgodne z aplikacja)")
    elif "unit" in params:
        print(f"WARN|pymodbus-api|parametr: unit (starsza wersja pymodbus < 3.0)")
    else:
        print(f"WARN|pymodbus-api|nieznany parametr slave ID: {params}")
except Exception as e:
    print(f"FAIL|pymodbus-api|{e}")

if not ok:
    sys.exit(1)
'@

$testLibs | Set-Content -Path "$env:TEMP\mb_tc_test_libs.py" -Encoding UTF8

& $pythonCmd "$env:TEMP\mb_tc_test_libs.py" 2>&1 | ForEach-Object {
    $parts = $_ -split '\|'
    if ($parts[0] -eq "OK")   { Write-OK   "$($parts[1]): $($parts[2])" }
    if ($parts[0] -eq "FAIL") { Write-FAIL "$($parts[1]): $($parts[2])" }
    if ($parts[0] -eq "WARN") { Write-WARN "$($parts[1]): $($parts[2])" }
}

Remove-Item "$env:TEMP\mb_tc_test_libs.py" -ErrorAction SilentlyContinue

# ===========================================================================
# TEST 3: Porty COM
# ===========================================================================
Write-Header "TEST 3: Porty szeregowe (COM)"

$testPorts = @'
import serial
import serial.tools.list_ports

ports = list(serial.tools.list_ports.comports())
if not ports:
    print("WARN|Brak portow COM w systemie")
    print("INFO|Sprawdz: konwerter USB-RS485 podlaczony? Sterownik zainstalowany (CH340/FTDI)?")
else:
    for p in sorted(ports, key=lambda x: x.device):
        vid = f"VID:{p.vid:04X}" if p.vid else ""
        pid = f"PID:{p.pid:04X}" if p.pid else ""
        usb = f" [{vid} {pid}]" if vid else ""
        print(f"OK|{p.device}: {p.description}{usb}")

        # Sprawdz czy mozna otworzyc
        try:
            s = serial.Serial(p.device)
            s.close()
            print(f"OK|  -> Port {p.device} dostepny (mozna otworzyc)")
        except serial.SerialException as e:
            print(f"FAIL|  -> Port {p.device} ZABLOKOWANY: {e}")
        except Exception as e:
            print(f"FAIL|  -> Port {p.device} BLAD: {e}")
'@

$testPorts | Set-Content -Path "$env:TEMP\mb_tc_test_ports.py" -Encoding UTF8

& $pythonCmd "$env:TEMP\mb_tc_test_ports.py" 2>&1 | ForEach-Object {
    $parts = $_ -split '\|', 2
    if ($parts.Count -ge 2) {
        if ($parts[0] -eq "OK")   { Write-OK   $parts[1] }
        if ($parts[0] -eq "FAIL") { Write-FAIL $parts[1] }
        if ($parts[0] -eq "WARN") { Write-WARN $parts[1] }
        if ($parts[0] -eq "INFO") { Write-INFO $parts[1] }
    } else {
        Write-Host "  $_" -ForegroundColor Gray
    }
}

Remove-Item "$env:TEMP\mb_tc_test_ports.py" -ErrorAction SilentlyContinue

# ===========================================================================
# TEST 4: Komunikacja Modbus RTU z urzadzeniem
# ===========================================================================
Write-Header "TEST 4: Komunikacja Modbus RTU z MB-TC-1"

$comPort = Read-Host "  Podaj port COM do testu (np. COM3, Enter = pomin)"
if ([string]::IsNullOrEmpty($comPort)) {
    Write-INFO "Pominieto test komunikacji"
} else {

$baudrate = Read-Host "  Baudrate (Enter = 9600)"
if ([string]::IsNullOrEmpty($baudrate)) { $baudrate = "9600" }

$parity = Read-Host "  Parzystosc: N/E/O (Enter = N)"
if ([string]::IsNullOrEmpty($parity)) { $parity = "N" }
$parity = $parity.ToUpper()

$stopbits = Read-Host "  Stop bits: 1 lub 2 (Enter = 1)"
if ([string]::IsNullOrEmpty($stopbits)) { $stopbits = "1" }

$slaveAddr = Read-Host "  Adres Modbus urzadzenia (Enter = 1)"
if ([string]::IsNullOrEmpty($slaveAddr)) { $slaveAddr = "1" }

# Generuj skrypt testowy
$testComm = @"
import serial
import struct
import time
import sys

PORT = "$comPort"
BAUD = $baudrate
PARITY = "$parity"
STOP = $stopbits
SLAVE = $slaveAddr

print(f"INFO|Test {PORT} @ {BAUD} {PARITY}{STOP}, slave addr={SLAVE}")

# --- Test otwarcia portu ---
parity_map = {"N": serial.PARITY_NONE, "E": serial.PARITY_EVEN, "O": serial.PARITY_ODD}
stopbits_map = {"1": serial.STOPBITS_ONE, "2": serial.STOPBITS_TWO}

try:
    s = serial.Serial(
        port=PORT,
        baudrate=BAUD,
        timeout=1.5,
        parity=parity_map.get(PARITY, serial.PARITY_NONE),
        stopbits=stopbits_map.get(str(STOP), serial.STOPBITS_ONE),
        bytesize=serial.EIGHTBITS,
    )
    print(f"OK|Port {PORT} otwarty pomyslnie")
except Exception as e:
    print(f"FAIL|Nie mozna otworzyc portu {PORT}: {e}")
    sys.exit(1)


def crc16_modbus(data: bytes) -> bytes:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return struct.pack("<H", crc)


def to_signed_16(value: int) -> int:
    return value - 0x10000 if value >= 0x8000 else value


def read_holding(slave, addr, count=1):
    """Wyslij Modbus RTU read holding (0x03) i zwroc liste rejestrow lub None."""
    frame = struct.pack(">BBHH", slave, 0x03, addr, count)
    frame += crc16_modbus(frame)
    s.reset_input_buffer()
    s.write(frame)
    time.sleep(0.2)
    resp = s.read(5 + 2 * count)
    if len(resp) < 5:
        return None, resp
    if resp[1] & 0x80:
        # exception response
        return None, resp
    if len(resp) < 3 + 2 * count:
        return None, resp
    regs = []
    for i in range(count):
        hi = resp[3 + 2 * i]
        lo = resp[4 + 2 * i]
        regs.append((hi << 8) | lo)
    return regs, resp


# --- Test 1: czy urzadzenie pod podanym adresem odpowiada? ---
print(f"INFO|")
print(f"INFO|--- Test odczytu rejestru REG_TEMPERATURE (0x0000) ---")
regs, resp = read_holding(SLAVE, 0x0000, 1)
if regs is not None:
    raw = regs[0]
    signed = to_signed_16(raw)
    temp = signed / 10.0
    print(f"OK|Slave {SLAVE} ODPOWIADA. Rejestr 0x0000 = 0x{raw:04X} (raw={raw}, signed={signed}, /10 = {temp:.1f} st.C)")
    if -50 <= temp <= 1000:
        print(f"OK|  Wartosc {temp:.1f} st.C wyglada na poprawna temperature (skala /10)")
    else:
        print(f"WARN|  Wartosc {temp:.1f} st.C wyglada nietypowo - moze inna skala lub inny rejestr")
else:
    print(f"WARN|Slave {SLAVE}: brak odpowiedzi lub blad. Surowe bajty: {resp.hex() if resp else 'BRAK'}")
    if resp and len(resp) >= 2 and resp[1] & 0x80:
        ec = resp[2] if len(resp) > 2 else 0
        ec_map = {1: "Illegal Function", 2: "Illegal Data Address", 3: "Illegal Data Value", 4: "Slave Device Failure"}
        print(f"FAIL|  Modbus exception code {ec}: {ec_map.get(ec, 'unknown')}")


# --- Test 2: odczyt wszystkich kluczowych rejestrow ---
print(f"INFO|")
print(f"INFO|--- Odczyt rejestrow konfiguracyjnych ---")
reg_map = [
    (0x0000, "REG_TEMPERATURE",     True),
    (0x0001, "REG_MIN_TEMPERATURE", True),
    (0x0002, "REG_MAX_TEMPERATURE", True),
    (0x0003, "REG_SENSOR_TYPE",     False),
    (0x0004, "REG_AVERAGE_TIME",    False),
    (0x0005, "REG_CORRECTION",      True),
]
for addr, name, is_temp in reg_map:
    regs, _ = read_holding(SLAVE, addr, 1)
    if regs is not None:
        raw = regs[0]
        if is_temp:
            signed = to_signed_16(raw)
            print(f"OK|  0x{addr:04X} {name:22s} = 0x{raw:04X} ({signed/10.0:+.1f} st.C)")
        else:
            print(f"OK|  0x{addr:04X} {name:22s} = 0x{raw:04X} ({raw})")
    else:
        print(f"WARN|  0x{addr:04X} {name:22s} = BRAK ODPOWIEDZI / blad rejestru")


# --- Test 3: porownaj 2 odczyty temperatury (czy sie zmienia / stabilna) ---
print(f"INFO|")
print(f"INFO|--- Test stabilnosci odczytu (2 odczyty co 1s) ---")
samples = []
for i in range(2):
    regs, _ = read_holding(SLAVE, 0x0000, 1)
    if regs is not None:
        t = to_signed_16(regs[0]) / 10.0
        samples.append(t)
        print(f"OK|  Odczyt {i+1}: {t:.1f} st.C")
    time.sleep(1.0)

if len(samples) == 2:
    diff = abs(samples[1] - samples[0])
    if diff < 0.1:
        print(f"OK|  Stabilny odczyt (delta {diff:.2f})")
    elif diff < 5.0:
        print(f"OK|  Naturalna wariacja (delta {diff:.2f})")
    else:
        print(f"WARN|  Duza wariacja (delta {diff:.2f}) - sprawdz polaczenie i czy czujnik podlaczony")


s.close()
print(f"INFO|")
print(f"INFO|--- Test zakonczony ---")
"@

$testComm | Set-Content -Path "$env:TEMP\mb_tc_test_comm.py" -Encoding UTF8

& $pythonCmd "$env:TEMP\mb_tc_test_comm.py" 2>&1 | ForEach-Object {
    $parts = $_ -split '\|', 2
    if ($parts.Count -ge 2) {
        if ($parts[0] -eq "OK")   { Write-OK   $parts[1] }
        if ($parts[0] -eq "FAIL") { Write-FAIL $parts[1] }
        if ($parts[0] -eq "WARN") { Write-WARN $parts[1] }
        if ($parts[0] -eq "INFO") { Write-INFO $parts[1] }
    } else {
        Write-Host "  $_" -ForegroundColor Gray
    }
}

Remove-Item "$env:TEMP\mb_tc_test_comm.py" -ErrorAction SilentlyContinue
}

# ===========================================================================
# TEST 5: Skanowanie adresow Modbus (1-247)
# ===========================================================================
if (-not [string]::IsNullOrEmpty($comPort)) {

$doScan = Read-Host "  Skanowac adresy Modbus 1-247? (znajdzie urzadzenie jesli nie znasz adresu) (t/n, Enter = n)"
if ($doScan -eq "t") {

Write-Header "TEST 5: Skan adresow Modbus 1-247"

$rangeAns = Read-Host "  Skanowac pelny zakres 1-247 czy szybki 1-32? (p=pelny, Enter=szybki)"
if ($rangeAns -eq "p") {
    $scanRange = "247"
} else {
    $scanRange = "32"
}

$testScan = @"
import serial
import struct
import time
import sys

PORT = "$comPort"
BAUD = $baudrate
PARITY = "$parity"
STOP = $stopbits
MAX_ADDR = $scanRange

parity_map = {"N": serial.PARITY_NONE, "E": serial.PARITY_EVEN, "O": serial.PARITY_ODD}
stopbits_map = {"1": serial.STOPBITS_ONE, "2": serial.STOPBITS_TWO}

s = serial.Serial(
    port=PORT, baudrate=BAUD, timeout=0.3,
    parity=parity_map.get(PARITY, serial.PARITY_NONE),
    stopbits=stopbits_map.get(str(STOP), serial.STOPBITS_ONE),
    bytesize=serial.EIGHTBITS,
)
print(f"INFO|Skanuje adresy 1-{MAX_ADDR} na {PORT} @ {BAUD} {PARITY}{STOP}...")

def crc16_modbus(data: bytes) -> bytes:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return struct.pack("<H", crc)

found = []
for addr in range(1, MAX_ADDR + 1):
    frame = struct.pack(">BBHH", addr, 0x03, 0x0000, 0x0001)
    frame += crc16_modbus(frame)
    s.reset_input_buffer()
    s.write(frame)
    time.sleep(0.1)
    resp = s.read(20)
    # Poprawna odpowiedz: addr | 0x03 | byte_count | hi | lo | crc_lo | crc_hi (7 B)
    # Exception:           addr | 0x83 | code | crc_lo | crc_hi (5 B)  - tez znaczy ze urzadzenie istnieje!
    if len(resp) >= 5 and resp[0] == addr:
        if resp[1] == 0x03 and len(resp) >= 7:
            raw = (resp[3] << 8) | resp[4]
            signed = raw - 0x10000 if raw >= 0x8000 else raw
            print(f"OK|Adres {addr}: ODPOWIADA, rejestr 0x0000 = {raw} (= {signed/10.0:+.1f} st.C)")
            found.append(addr)
        elif resp[1] == 0x83:
            print(f"OK|Adres {addr}: urzadzenie istnieje ale rejestr 0x0000 niedostepny (exception)")
            found.append(addr)
    if (addr % 25) == 0:
        print(f"INFO|  ...sprawdzono {addr}/{MAX_ADDR}")

s.close()
print(f"INFO|")
if found:
    print(f"OK|Znaleziono urzadzenia pod adresami: {found}")
else:
    print(f"WARN|Nie znaleziono zadnych urzadzen w zakresie 1-{MAX_ADDR}")
    print(f"INFO|Sprawdz: zasilanie, polaczenie A/B (moze byc zamienione), baudrate, parzystosc")
"@

$testScan | Set-Content -Path "$env:TEMP\mb_tc_test_scan.py" -Encoding UTF8

& $pythonCmd "$env:TEMP\mb_tc_test_scan.py" 2>&1 | ForEach-Object {
    $parts = $_ -split '\|', 2
    if ($parts.Count -ge 2) {
        if ($parts[0] -eq "OK")   { Write-OK   $parts[1] }
        if ($parts[0] -eq "FAIL") { Write-FAIL $parts[1] }
        if ($parts[0] -eq "WARN") { Write-WARN $parts[1] }
        if ($parts[0] -eq "INFO") { Write-INFO $parts[1] }
    }
}

Remove-Item "$env:TEMP\mb_tc_test_scan.py" -ErrorAction SilentlyContinue
}
}

# ===========================================================================
# TEST 6: Autodetekcja baudrate / parzystosci
# ===========================================================================
if (-not [string]::IsNullOrEmpty($comPort)) {

$doBaud = Read-Host "  Przetestowac rozne baudrate i parzystosci? (t/n, Enter = n)"
if ($doBaud -eq "t") {

Write-Header "TEST 6: Autodetekcja parametrow transmisji"

$testBaud = @"
import serial
import struct
import time

PORT = "$comPort"
SLAVE = $slaveAddr
STOP = $stopbits

stopbits_map = {"1": serial.STOPBITS_ONE, "2": serial.STOPBITS_TWO}
sb = stopbits_map.get(str(STOP), serial.STOPBITS_ONE)

def crc16_modbus(data: bytes) -> bytes:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return struct.pack("<H", crc)


print(f"INFO|Testowanie roznych kombinacji baudrate/parzystosci na {PORT}...")
print(f"INFO|(uzywam adresu Modbus = {SLAVE}, stop bits = {STOP})")

combos = []
for baud in [1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200]:
    for par_name, par_code in [("N", serial.PARITY_NONE), ("E", serial.PARITY_EVEN), ("O", serial.PARITY_ODD)]:
        combos.append((baud, par_name, par_code))

found_any = False
for baud, par_name, par_code in combos:
    try:
        s = serial.Serial(PORT, baud, timeout=0.5,
                          parity=par_code, stopbits=sb, bytesize=serial.EIGHTBITS)
        frame = struct.pack(">BBHH", SLAVE, 0x03, 0x0000, 0x0001)
        frame += crc16_modbus(frame)
        s.reset_input_buffer()
        s.write(frame)
        time.sleep(0.2)
        resp = s.read(20)
        s.close()

        if len(resp) >= 5 and resp[0] == SLAVE and resp[1] in (0x03, 0x83):
            print(f"OK|BAUD {baud:>6}  PAR {par_name}  STOP {STOP}: ODPOWIADA ({len(resp)} B: {resp.hex()})")
            found_any = True
    except Exception as e:
        print(f"FAIL|BAUD {baud} PAR {par_name}: {e}")

print(f"INFO|")
if not found_any:
    print(f"WARN|Zadna kombinacja baudrate/parzystosci nie dziala")
    print(f"INFO|Mozliwe przyczyny: zly adres slave, zamiana A/B, zle stop bits, brak zasilania")
else:
    print(f"OK|Wpisz parametry powyzej do GUI")
"@

$testBaud | Set-Content -Path "$env:TEMP\mb_tc_test_baud.py" -Encoding UTF8

& $pythonCmd "$env:TEMP\mb_tc_test_baud.py" 2>&1 | ForEach-Object {
    $parts = $_ -split '\|', 2
    if ($parts.Count -ge 2) {
        if ($parts[0] -eq "OK")   { Write-OK   $parts[1] }
        if ($parts[0] -eq "FAIL") { Write-FAIL $parts[1] }
        if ($parts[0] -eq "WARN") { Write-WARN $parts[1] }
        if ($parts[0] -eq "INFO") { Write-INFO $parts[1] }
    }
}

Remove-Item "$env:TEMP\mb_tc_test_baud.py" -ErrorAction SilentlyContinue
}
}

# ===========================================================================
# TEST 7: Skaner rejestrow - mapa pamieci urzadzenia
# ===========================================================================
if (-not [string]::IsNullOrEmpty($comPort)) {

$doRegScan = Read-Host "  Zeskanowac rejestry 0x0000-0x003F? (pokaze co jest w ktorym - pomaga ustalic mape) (t/n, Enter = n)"
if ($doRegScan -eq "t") {

Write-Header "TEST 7: Skaner rejestrow Holding (0x0000-0x003F)"

$testRegScan = @"
import serial
import struct
import time

PORT = "$comPort"
BAUD = $baudrate
PARITY = "$parity"
STOP = $stopbits
SLAVE = $slaveAddr

parity_map = {"N": serial.PARITY_NONE, "E": serial.PARITY_EVEN, "O": serial.PARITY_ODD}
stopbits_map = {"1": serial.STOPBITS_ONE, "2": serial.STOPBITS_TWO}

s = serial.Serial(
    port=PORT, baudrate=BAUD, timeout=0.5,
    parity=parity_map.get(PARITY, serial.PARITY_NONE),
    stopbits=stopbits_map.get(str(STOP), serial.STOPBITS_ONE),
    bytesize=serial.EIGHTBITS,
)

def crc16_modbus(data: bytes) -> bytes:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return struct.pack("<H", crc)

def to_signed_16(value: int) -> int:
    return value - 0x10000 if value >= 0x8000 else value

def read_one(addr):
    frame = struct.pack(">BBHH", SLAVE, 0x03, addr, 1)
    frame += crc16_modbus(frame)
    s.reset_input_buffer()
    s.write(frame)
    time.sleep(0.1)
    resp = s.read(20)
    if len(resp) >= 7 and resp[0] == SLAVE and resp[1] == 0x03:
        return (resp[3] << 8) | resp[4], "OK"
    if len(resp) >= 3 and resp[0] == SLAVE and resp[1] == 0x83:
        return None, f"EXC{resp[2]}"
    return None, "TIMEOUT"


print(f"INFO|Skanowanie rejestrow Holding 0x0000-0x003F na slave={SLAVE}...")
print(f"INFO|Format: ADDR  HEX     DEC      SIGNED   /10 (jako temp.)   STATUS")
print(f"INFO|       ----  ----    ----     ------   ----------------   ------")

found_count = 0
for addr in range(0x00, 0x40):
    raw, status = read_one(addr)
    if raw is not None:
        signed = to_signed_16(raw)
        as_temp = signed / 10.0
        # Zaznacz wartosci ktore wygladaja na temperature (zakres rozsadny)
        marker = ""
        if -50 <= as_temp <= 1000 and abs(raw) > 0:
            marker = "  <-- mozliwa temperatura?"
        elif raw == 0:
            marker = ""
        elif 0 < raw <= 20:
            marker = "  <-- moze typ czujnika lub czas usredniania?"
        print(f"OK|0x{addr:04X}  0x{raw:04X}  {raw:6}   {signed:+7}    {as_temp:+8.1f}            {marker}")
        found_count += 1
    elif status.startswith("EXC"):
        print(f"INFO|0x{addr:04X}  ----    ----     ------   ----              [Modbus exception {status}]")
    # TIMEOUT - cicho pomijamy zeby nie zaspamowac

s.close()
print(f"INFO|")
print(f"OK|Zeskanowano. Dostepnych rejestrow: {found_count}")
print(f"INFO|")
print(f"INFO|Co teraz zrobic:")
print(f"INFO|  1. Znajdz rejestr z aktualna temperatura (najczesciej zmienia sie z czasem)")
print(f"INFO|     - Powtorz Test 7, zobacz ktore wartosci sa rozne miedzy uruchomieniami")
print(f"INFO|  2. Znajdz rejestr typu czujnika - powinien miec mala wartosc 0-15")
print(f"INFO|  3. Znajdz rejestr czasu usredniania - mala wartosc np. 1, 5, 10")
print(f"INFO|  4. Wpisz znalezione adresy do app/registers.py")
"@

$testRegScan | Set-Content -Path "$env:TEMP\mb_tc_test_regscan.py" -Encoding UTF8

& $pythonCmd "$env:TEMP\mb_tc_test_regscan.py" 2>&1 | ForEach-Object {
    $parts = $_ -split '\|', 2
    if ($parts.Count -ge 2) {
        if ($parts[0] -eq "OK")   { Write-OK   $parts[1] }
        if ($parts[0] -eq "FAIL") { Write-FAIL $parts[1] }
        if ($parts[0] -eq "WARN") { Write-WARN $parts[1] }
        if ($parts[0] -eq "INFO") { Write-INFO $parts[1] }
    }
}

Remove-Item "$env:TEMP\mb_tc_test_regscan.py" -ErrorAction SilentlyContinue
}
}

# ===========================================================================
# PODSUMOWANIE
# ===========================================================================
Write-Header "PODSUMOWANIE"

Write-Host ""
Write-INFO "Diagnostyka zakonczona. Jesli masz problemy:"
Write-Host ""
Write-Host "  1. Port COM nie widoczny:" -ForegroundColor Yellow
Write-Host "     - Sprawdz Menedzer urzadzen > Porty (COM i LPT)" -ForegroundColor Gray
Write-Host "     - Zainstaluj sterownik konwertera (CH340, FT232, Prolific)" -ForegroundColor Gray
Write-Host "     - Wypnij i wepnij konwerter ponownie" -ForegroundColor Gray
Write-Host ""
Write-Host "  2. Port COM zablokowany:" -ForegroundColor Yellow
Write-Host "     - Zamknij MB Config, Realterm, Putty, terminale" -ForegroundColor Gray
Write-Host "     - Zamknij wczesniejsza instancje GUI MB-TC Configurator" -ForegroundColor Gray
Write-Host ""
Write-Host "  3. Port otwiera sie ale brak odpowiedzi z urzadzenia:" -ForegroundColor Yellow
Write-Host "     - Najczestszy blad: zamiana linii A i B - zamien przewody" -ForegroundColor Gray
Write-Host "     - Sprawdz zasilanie urzadzenia MB-TC-1" -ForegroundColor Gray
Write-Host "     - Sprawdz adres Modbus (fabrycznie 1, ale moze byc inny)" -ForegroundColor Gray
Write-Host "     - Uruchom Test 5 (skan adresow) zeby znalezc adres" -ForegroundColor Gray
Write-Host "     - Uruchom Test 6 (autodetekcja baudrate)" -ForegroundColor Gray
Write-Host "     - Sprawdz terminacje 120 Ohm jesli kabel dluzszy niz kilka metrow" -ForegroundColor Gray
Write-Host "     - Sprawdz GND - przy dluzszych kablach lub roznych zasilaczach" -ForegroundColor Gray
Write-Host ""
Write-Host "  4. Modbus exception 'Illegal Data Address' przy odczycie:" -ForegroundColor Yellow
Write-Host "     - Mapa rejestrow w app/registers.py jest WSTEPNYM zalozeniem" -ForegroundColor Gray
Write-Host "     - Sprawdz dokumentacje MB-TC-1 i popraw adresy" -ForegroundColor Gray
Write-Host "     - Niektore urzadzenia uzywaja Input Registers (0x04) zamiast Holding (0x03)" -ForegroundColor Gray
Write-Host ""
Write-Host "  5. Wartosc temperatury wyglada nietypowo (np. 2530 zamiast 25.3):" -ForegroundColor Yellow
Write-Host "     - Inne skalowanie - zmien TEMP_SCALE w app/utils.py (np. 100.0 lub 1.0)" -ForegroundColor Gray
Write-Host "     - Mozliwe ze wartosc jest w 2 rejestrach (float 32-bit)" -ForegroundColor Gray
Write-Host ""
Write-Host "  6. Brak biblioteki pymodbus / PySide6:" -ForegroundColor Yellow
Write-Host "     - Aktywuj venv: .venv\Scripts\activate" -ForegroundColor Gray
Write-Host "     - Zainstaluj: pip install -r requirements.txt" -ForegroundColor Gray
Write-Host ""
Write-Host "============================================" -ForegroundColor White
Write-Host ""
