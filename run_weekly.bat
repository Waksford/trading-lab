@echo off

cd /d C:\Users\Jaime\Documents\trading-lab

call .venv\Scripts\activate.bat

python weekly_report.py >> data\weekly.log 2>&1

exit /b %ERRORLEVEL%