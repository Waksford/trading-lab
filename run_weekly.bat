@echo off
setlocal

cd /d C:\Users\Jaime\Documents\trading-lab

if not exist data mkdir data

echo. >> data\weekly.log
echo ================================================== >> data\weekly.log
echo [%date% %time%] INICIO WEEKLY REPORT >> data\weekly.log

call .venv\Scripts\activate.bat >> data\weekly.log 2>&1

echo [%date% %time%] VENV ACTIVADO >> data\weekly.log

python weekly_report.py >> data\weekly.log 2>&1

set EXITCODE=%ERRORLEVEL%

echo [%date% %time%] FIN WEEKLY REPORT - Exit code: %EXITCODE% >> data\weekly.log
echo ================================================== >> data\weekly.log

endlocal & exit /b %EXITCODE%