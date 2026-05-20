# -*- mode: python ; coding: utf-8 -*-
"""
mb_tc_configurator.spec - konfiguracja PyInstallera dla MB-TC Configurator.

Buduje pojedynczy plik wykonywalny .exe (one-file mode) bez konsoli.

Użycie (Windows):
    .venv\\Scripts\\activate
    pip install pyinstaller
    pyinstaller mb_tc_configurator.spec

Wynik powstanie w: dist\\MB-TC-Configurator.exe
"""

block_cipher = None


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    # Dołączamy ikonę także jako data, żeby była dostępna w runtime (gui.py)
    datas=[('icon.ico', '.')],
    hiddenimports=[
        # Niektóre moduły pymodbus / pyserial bywają ładowane dynamicznie
        'pymodbus.client.serial',
        'pymodbus.framer.rtu',
        'pymodbus.transaction',
        'serial.tools.list_ports',
        'serial.tools.list_ports_windows',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Wyłączamy duże, niepotrzebne moduły żeby zmniejszyć rozmiar .exe
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'pytest',
        'IPython',
        'jupyter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='MB-TC-Configurator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,                  # kompresja UPX (jeśli dostępna)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,             # NIE pokazuj konsoli - aplikacja GUI
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',           # ikona pliku .exe
    version='version_info.txt',
)
