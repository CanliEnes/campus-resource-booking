@echo off
rem Kullanim: calistir.bat baslangic.json komutlar.jsonl > sonuclar.jsonl
where python >nul 2>nul && (python "%~dp0main.py" %*) || (py -3 "%~dp0main.py" %*)
