@echo off
rem Lanzador del sender (lo usa iniciar_sender.vbs para ejecutarlo sin ventana)
cd /d "%~dp0"
set PY=python
where python >nul 2>nul || set PY=py
:loop
%PY% -u elite_sender.py > elite_sender.log 2>&1
timeout /t 5 >nul
goto loop
