@echo off
REM ============================================================
REM  Buchhaltung Desktop -- Build-Skript fuer Windows
REM  Erzeugt eine einzelne .exe-Datei in dist\Buchhaltung.exe
REM ============================================================

echo [1/3] Installiere Abhaengigkeiten ...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo [2/3] Baue die exe mit PyInstaller ...
pyinstaller --noconfirm --onefile --windowed ^
    --name "Buchhaltung" ^
    --collect-all ttkbootstrap ^
    --hidden-import PIL._tkinter_finder ^
    main.py

echo [3/3] Fertig!
echo Die fertige Datei liegt unter: dist\Buchhaltung.exe
pause
