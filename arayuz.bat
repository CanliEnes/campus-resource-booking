@echo off
rem Masaustu uygulamasini baslatir. Istege bagli: arayuz.bat baslangic.json
where python >nul 2>nul && (python "%~dp0uygulama.py" %*) || (py -3 "%~dp0uygulama.py" %*)
