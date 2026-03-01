# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['watcher.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('.venv/Lib/site-packages/pypdfium2_raw/pdfium.dll', 'pypdfium2_raw'),
        ('.venv/Lib/site-packages/pypdfium2_raw/version.json', 'pypdfium2_raw'),
        ('.venv/Lib/site-packages/pypdfium2/version.json', 'pypdfium2'),
        ('.env', '.'),
        ('app/version.py', 'app'),
        ('app/po_validator/stamps/*.png', 'app/po_validator/stamps'),
        ('config.yaml', '.'),
    ],
    hiddenimports=[
        'httpx', 'httpcore', 'qualer_sdk', 'h11', 'anyio',
        'pdfplumber', 'google.genai', 'pydantic', 'fitz',
        'PyQt6', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets', 'PyQt6.sip',
        'yaml',
    ],
    hookspath=['hooks'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='PDF_Uploader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
