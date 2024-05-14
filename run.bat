@echo off
REM Run the Python script
start /B "" python main.py

REM Wait for a few seconds to ensure the server starts
timeout /t 2 /nobreak > NUL

REM Open the URL in the default web browser
start "" http://127.0.0.1:5000/

exit /b 0
