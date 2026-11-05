@echo off
REM Double-click to scrape the catalogue and build a fresh Excel report.
cd /d "%~dp0"
python scrape.py
echo.
echo The report is in the "output" folder.
pause
