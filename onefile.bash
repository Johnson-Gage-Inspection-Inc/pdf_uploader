./myenv/Scripts/activate
# pip install pyinstaller  # NOTE: This is not needed if you have already installed pyinstaller
pyinstaller --onefile  --clean --add-data "myenv/Lib/site-packages/pypdfium2_raw/pdfium.dll;pypdfium2_raw" --add-data "myenv/Lib/site-packages/pypdfium2_raw/version.json;pypdfium2_raw" --add-data "myenv/Lib/site-packages/pypdfium2/version.json;pypdfium2" --add-data "app/dict.json.gz;_internal" watcher.py
