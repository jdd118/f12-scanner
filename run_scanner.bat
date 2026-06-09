@echo off
REM Run the Ferrari F12 Canada Scanner
cd /d "C:\Users\m3nbtp\Downloads\F12 scanner"
py -3.13 scanner.py >> scanner_log.txt 2>&1
