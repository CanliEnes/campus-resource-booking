@echo off
rem Masaustu uygulamasini baslatir. Istege bagli: arayuz.bat baslangic.json
setlocal
set "KOK=%~dp0"
where pyw >nul 2>nul
if %errorlevel%==0 (
    start "" pyw -3 "%KOK%masaustu.py" %*
) else (
    start "" pythonw "%KOK%masaustu.py" %*
)
