@echo off
cd /d "%~dp0"
rem Use the real Python install; plain "python" can hit the Microsoft Store placeholder
set "PY=%LOCALAPPDATA%\Python\bin\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" -m streamlit run app.py
pause
