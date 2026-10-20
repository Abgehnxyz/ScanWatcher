@echo off
setlocal
echo ============================================
echo  Scan Watcher – Build
echo  Nova Network
echo ============================================
echo.

rem Version aus src\__init__.py (einzige Quelle)
for /f "delims=" %%v in ('py -c "from src import __version__; print(__version__)"') do set VERSION=%%v
if "%VERSION%"=="" (
    echo FEHLER: Version konnte nicht gelesen werden.
    pause
    exit /b 1
)
echo Version: %VERSION%

rem Tesseract-Installationspfad aus der Registry (Fallback: Standardpfad)
set "TESS=C:\Program Files\Tesseract-OCR"
for /f "tokens=2,*" %%a in ('reg query "HKLM\SOFTWARE\Tesseract-OCR" /v InstallDir 2^>nul ^| findstr InstallDir') do set "TESS=%%b"
if not exist "%TESS%\tesseract.exe" (
    echo FEHLER: tesseract.exe nicht gefunden unter "%TESS%".
    pause
    exit /b 1
)

echo.
echo [1/4] Tests...
py -m pytest tests\ -q
if errorlevel 1 (
    echo FEHLER: Tests fehlgeschlagen!
    pause
    exit /b 1
)

echo.
echo [2/4] PyInstaller – EXE erstellen...
rem tesseract.exe braucht die DLLs aus seinem Ordner – ohne sie startet es
rem auf Rechnern ohne eigene Tesseract-Installation nicht (STATUS_DLL_NOT_FOUND).
py -m PyInstaller ^
  --noconfirm ^
  --onedir ^
  --windowed ^
  --name ScanWatcher ^
  --icon assets\icon.ico ^
  --add-data "assets;assets" ^
  --add-data "%TESS%\tesseract.exe;tesseract" ^
  --add-data "%TESS%\*.dll;tesseract" ^
  --add-data "%TESS%\tessdata\deu.traineddata;tesseract/tessdata" ^
  --add-data "%TESS%\tessdata\eng.traineddata;tesseract/tessdata" ^
  --collect-data customtkinter ^
  run.py

if errorlevel 1 (
    echo FEHLER beim Build!
    pause
    exit /b 1
)

echo.
echo [3/4] Inno Setup – Installer erstellen...
set ISCC="%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist %ISCC% set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist %ISCC% (
    %ISCC% /DAppVersion=%VERSION% installer\setup.iss
) else (
    echo HINWEIS: Inno Setup nicht gefunden – nur EXE erstellt.
    echo Download: https://jrsoftware.org/isdl.php
)

echo.
echo [4/4] Fertig!
echo   EXE:       dist\ScanWatcher\ScanWatcher.exe
echo   Installer: dist\installer\ScanWatcher_Setup_v%VERSION%.exe
echo.
pause
