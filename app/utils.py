"""
utils.py - funkcje pomocnicze do skalowania i konwersji wartości
odczytywanych/zapisywanych do rejestrów Modbus urządzenia MB-TC-1.

UWAGA: Założenie - temperatura w rejestrze jest zapisana jako 16-bitowa
liczba całkowita ze znakiem (signed int16) pomnożona ×10.
Przykład: 253 = 25.3°C, -105 = -10.5°C.

Skalowanie należy potwierdzić w dokumentacji urządzenia (możliwe są
inne mnożniki, np. ×100, lub format float w 2 rejestrach).
"""

# Mnożnik skalowania - wszystkie wartości temperatury są mnożone przez ten
# współczynnik przed zapisem do rejestru i dzielone po odczycie.
# SPRAWDŹ W DOKUMENTACJI MB-TC-1 — niektóre urządzenia używają ×1 lub ×100.
TEMP_SCALE = 10.0


def to_signed_16(value: int) -> int:
    """
    Konwertuje wartość 16-bitową unsigned (0..65535) na signed (-32768..32767).
    Modbus zwraca rejestry jako unsigned, ale temperatury bywają ujemne.
    """
    value = value & 0xFFFF
    if value >= 0x8000:
        return value - 0x10000
    return value


def to_unsigned_16(value: int) -> int:
    """
    Konwertuje signed int16 na unsigned int16 — postać wymagana przy zapisie
    do rejestru Modbus.
    """
    if value < 0:
        value = value + 0x10000
    return value & 0xFFFF


def raw_to_temperature(raw_value: int) -> float:
    """
    Zamienia wartość surową z rejestru (unsigned int16 zwracany przez pymodbus)
    na temperaturę w stopniach Celsjusza.

    Zakłada signed int16 ×10. Skalowanie należy potwierdzić w dokumentacji urządzenia.
    """
    signed = to_signed_16(raw_value)
    return signed / TEMP_SCALE


def temperature_to_raw(temp: float) -> int:
    """
    Zamienia temperaturę w °C na wartość surową do zapisu w rejestrze.
    Zwraca unsigned int16 (zgodnie z formatem przyjmowanym przez pymodbus).

    Skalowanie należy potwierdzić w dokumentacji urządzenia.
    """
    scaled = int(round(temp * TEMP_SCALE))
    # Ograniczenie do zakresu signed int16
    if scaled > 32767:
        scaled = 32767
    elif scaled < -32768:
        scaled = -32768
    return to_unsigned_16(scaled)
