@echo off

REM ==========================================================
REM UTF-8
REM ==========================================================

chcp 65001 >nul

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8


REM ==========================================================
REM DIRECTORIO DEL PROYECTO
REM ==========================================================

cd /d C:\Users\Jaime\Documents\trading-lab

call .venv\Scripts\activate.bat


REM ==========================================================
REM FECHA DEL LOG
REM ==========================================================

for /f "tokens=1-3 delims=/" %%a in ("%date%") do (
    set FECHA=%%c-%%b-%%a
)

set LOG=data\trading_%FECHA%.log


REM ==========================================================
REM CABECERA
REM ==========================================================

echo.
echo ======================================
echo INICIANDO TRADING RADAR
echo Fecha: %date%
echo Hora: %time%
echo ======================================
echo.

echo. >> "%LOG%"
echo ====================================== >> "%LOG%"
echo INICIO TRADING RADAR >> "%LOG%"
echo Fecha: %date% >> "%LOG%"
echo Hora: %time% >> "%LOG%"
echo ====================================== >> "%LOG%"


REM ==========================================================
REM 1. TRADING RADAR
REM ==========================================================

echo. >> "%LOG%"
echo ====================================== >> "%LOG%"
echo EJECUTANDO MAIN >> "%LOG%"
echo ====================================== >> "%LOG%"

python main.py >> "%LOG%" 2>&1

set MAIN_EXIT_CODE=%ERRORLEVEL%


REM ==========================================================
REM 2. PAPER SIMULATOR
REM Solo si MAIN ha terminado correctamente
REM ==========================================================

if %MAIN_EXIT_CODE% EQU 0 (

    echo. >> "%LOG%"
    echo ====================================== >> "%LOG%"
    echo INICIANDO PAPER SIMULATOR >> "%LOG%"
    echo Fecha: %date% >> "%LOG%"
    echo Hora: %time% >> "%LOG%"
    echo ====================================== >> "%LOG%"

    python paper_simulator.py >> "%LOG%" 2>&1

    set PAPER_EXIT_CODE=%ERRORLEVEL%

) else (

    echo. >> "%LOG%"
    echo PAPER SIMULATOR OMITIDO POR ERROR EN MAIN >> "%LOG%"

    set PAPER_EXIT_CODE=0

)


REM ==========================================================
REM 3. PAPER PORTFOLIO LIVE
REM Independiente: benchmarks y valoraciones pueden continuar aunque falle una fase previa
REM ==========================================================

echo. >> "%LOG%"
echo ====================================== >> "%LOG%"
echo INICIANDO PAPER PORTFOLIOS >> "%LOG%"
echo Fecha: %date% >> "%LOG%"
echo Hora: %time% >> "%LOG%"
echo ====================================== >> "%LOG%"

python paper_portfolios_runner.py >> "%LOG%" 2>&1

set PORTFOLIO_EXIT_CODE=%ERRORLEVEL%


REM ==========================================================
REM 4. NEWS ANALYZER
REM News depende del radar, no del resultado de las carteras paper
REM ==========================================================

if %MAIN_EXIT_CODE% EQU 0 (

    echo. >> "%LOG%"
    echo ====================================== >> "%LOG%"
    echo INICIANDO NEWS ANALYZER >> "%LOG%"
    echo Fecha: %date% >> "%LOG%"
    echo Hora: %time% >> "%LOG%"
    echo ====================================== >> "%LOG%"

    python news_analyzer.py >> "%LOG%" 2>&1

    set NEWS_EXIT_CODE=%ERRORLEVEL%

) else (

    echo. >> "%LOG%"
    echo NEWS ANALYZER OMITIDO POR ERROR PREVIO >> "%LOG%"

    set NEWS_EXIT_CODE=0

)


REM ==========================================================
REM RESULTADO FINAL
REM ==========================================================

if %MAIN_EXIT_CODE% NEQ 0 (

    set EXIT_CODE=%MAIN_EXIT_CODE%

) else if %PAPER_EXIT_CODE% NEQ 0 (

    set EXIT_CODE=%PAPER_EXIT_CODE%

) else if %PORTFOLIO_EXIT_CODE% NEQ 0 (

    set EXIT_CODE=%PORTFOLIO_EXIT_CODE%

) else (

    set EXIT_CODE=%NEWS_EXIT_CODE%

)


REM ==========================================================
REM RESUMEN DE EJECUCION
REM ==========================================================

echo. >> "%LOG%"
echo ====================================== >> "%LOG%"
echo RESUMEN DE EJECUCION >> "%LOG%"
echo ====================================== >> "%LOG%"

echo MAIN:              %MAIN_EXIT_CODE% >> "%LOG%"
echo PAPER:             %PAPER_EXIT_CODE% >> "%LOG%"
echo PORTFOLIO LIVE:    %PORTFOLIO_EXIT_CODE% >> "%LOG%"
echo NEWS:              %NEWS_EXIT_CODE% >> "%LOG%"


if %EXIT_CODE% EQU 0 (

    echo RESULTADO: OK >> "%LOG%"
    echo FIN OK %date% %time% >> "%LOG%"

) else (

    echo RESULTADO: ERROR >> "%LOG%"
    echo ERROR %EXIT_CODE% - %date% %time% >> "%LOG%"

)


echo. >> "%LOG%"


REM ==========================================================
REM BORRAR LOGS DE MAS DE 90 DIAS
REM ==========================================================

forfiles /p "data" /m "trading_*.log" /d -90 /c "cmd /c del /q @path" >nul 2>&1


REM ==========================================================
REM SALIR
REM ==========================================================

exit /b %EXIT_CODE%
