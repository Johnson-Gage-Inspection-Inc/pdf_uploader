# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['watcher.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('myenv/Lib/site-packages/pypdfium2_raw/pdfium.dll', 'pypdfium2_raw'),
        ('myenv/Lib/site-packages/pypdfium2_raw/version.json', 'pypdfium2_raw'),
        ('myenv/Lib/site-packages/pypdfium2/version.json', 'pypdfium2'),
        ('.env', '.'),
        ('app/version.py', 'app')
    ],
    hiddenimports=[],
    hookspath=[],
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
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
