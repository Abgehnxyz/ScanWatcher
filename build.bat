@echo off
echo ============================================
echo  Scan Watcher – Build
echo  Nova Network
echo ============================================
echo.

echo [1/3] PyInstaller – EXE erstellen...
py -m PyInstaller ^
  --noconfirm ^
  --onedir ^
  --windowed ^
  --name ScanWatcher ^
  --icon assets\icon.ico ^
  --add-data "assets;assets" ^
  --add-data "D:\Program Files\Tesseract-OCR\tesseract.exe;tesseract" ^
  --add-data "D:\Program Files\Tesseract-OCR\tessdata\deu.traineddata;tesseract/tessdata" ^
  --add-data "D:\Program Files\Tesseract-OCR\tessdata\eng.traineddata;tesseract/tessdata" ^
  --collect-data customtkinter ^
  run.py

if errorlevel 1 (
    echo FEHLER beim Build!
    pause
    exit /b 1
)

echo.
echo [2/3] Inno Setup – Installer erstellen...
set ISCC="%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist %ISCC% set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist %ISCC% (
    %ISCC% installer\setup.iss
) else (
    echo HINWEIS: Inno Setup nicht gefunden – nur EXE erstellt.
    echo Download: https://jrsoftware.org/isdl.php
)

echo.
echo [3/3] Fertig!
echo   EXE:       dist\ScanWatcher\ScanWatcher.exe
echo   Installer: dist\installer\ScanWatcher_Setup_v1.0.0.exe
echo.
pause
