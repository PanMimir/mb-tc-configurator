"""
sensor_types.py - typy termopar obsługiwanych przez F&F MB-TC-1.

Kody numeryczne zgodne z dokumentacją producenta (E230328, str. 11):
    0 - K
    1 - J
    2 - T
    3 - N
    4 - S
    5 - E
    6 - B
    7 - R

UWAGA: MB-TC-1 obsługuje WYŁĄCZNIE termopary. Nie obsługuje czujników
rezystancyjnych (PT100/PT500/PT1000) - dla nich należy użyć innego modułu
F&F (np. MB-RTD).
"""

from enum import Enum


class SensorType(Enum):
    """
    Typ termopary - wartości to kody zapisywane do REG_SENSOR_TYPE (0x0006).
    """
    THERMOCOUPLE_K = 0   # Termopara typu K (NiCr-Ni) - najczęściej używana
    THERMOCOUPLE_J = 1   # Termopara typu J (Fe-CuNi)
    THERMOCOUPLE_T = 2   # Termopara typu T (Cu-CuNi)
    THERMOCOUPLE_N = 3   # Termopara typu N (NiCrSi-NiSi)
    THERMOCOUPLE_S = 4   # Termopara typu S (Pt10Rh-Pt)
    THERMOCOUPLE_E = 5   # Termopara typu E (NiCr-CuNi)
    THERMOCOUPLE_B = 6   # Termopara typu B (Pt30Rh-Pt6Rh)
    THERMOCOUPLE_R = 7   # Termopara typu R (Pt13Rh-Pt)


# Mapa: nazwa pokazywana w GUI -> SensorType
# Kolejność elementów decyduje o kolejności na liście rozwijanej.
SENSOR_DISPLAY_NAMES = {
    "Termopara K": SensorType.THERMOCOUPLE_K,
    "Termopara J": SensorType.THERMOCOUPLE_J,
    "Termopara T": SensorType.THERMOCOUPLE_T,
    "Termopara N": SensorType.THERMOCOUPLE_N,
    "Termopara S": SensorType.THERMOCOUPLE_S,
    "Termopara E": SensorType.THERMOCOUPLE_E,
    "Termopara B": SensorType.THERMOCOUPLE_B,
    "Termopara R": SensorType.THERMOCOUPLE_R,
}


def sensor_type_to_display_name(sensor: SensorType) -> str:
    """Zwraca nazwę GUI dla SensorType, lub fallback ze stringiem dla nieznanych."""
    for name, value in SENSOR_DISPLAY_NAMES.items():
        if value == sensor:
            return name
    return f"Nieznany ({sensor})"


def display_name_to_sensor_type(name: str) -> SensorType:
    """Zwraca SensorType dla nazwy z GUI. Rzuca KeyError jeśli nie znaleziono."""
    return SENSOR_DISPLAY_NAMES[name]
