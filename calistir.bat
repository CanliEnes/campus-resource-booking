@echo off
rem Kullanim: calistir.bat baslangic.json komutlar.jsonl > sonuclar.jsonl
setlocal
set "KOK=%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 "%KOK%calistir.py" %*
) else (
    python "%KOK%calistir.py" %*
)
exit /b %errorlevel%
