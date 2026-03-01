# -*- mode: python ; coding: utf-8 -*-


import importlib
import os

def _pkg_data(package_name, filename):
    """Locate a data file inside an installed package."""
    pkg = importlib.import_module(package_name)
    pkg_dir = os.path.dirname(pkg.__file__)
    return (os.path.join(pkg_dir, filename), package_name)

a = Analysis(
    ['watcher.py'],
    pathex=[],
    binaries=[],
    datas=[
        _pkg_data('pypdfium2_raw', 'pdfium.dll'),
        _pkg_data('pypdfium2_raw', 'version.json'),
        _pkg_data('pypdfium2', 'version.json'),
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
