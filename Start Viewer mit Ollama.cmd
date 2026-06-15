@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "REPO=%~dp0"
set "VIEWER=%REPO%viewer.html"
set "VIEWER_URL=http://127.0.0.1:8765/viewer.html"

title Graz Viewer
cd /d "%REPO%"

echo.
echo Graz Viewer
echo ===========
echo Ordner: %REPO%
echo.

call :BuildViewerIfMissing
if errorlevel 1 goto fail

call :EnsureDigraBackground

call :EnsureViewerServer
if errorlevel 1 goto fail

call :OpenViewer
if errorlevel 1 goto fail

echo.
echo Viewer wurde geoeffnet.
ping -n 4 127.0.0.1 >nul
exit /b 0

:BuildViewerIfMissing
echo Baue lokale HTML neu...
if exist "out\agenda_items_digra_sync_plus_city_protocols_and_archive_questions_clean.jsonl" (
    set "RECORDS=out\agenda_items_digra_sync_plus_city_protocols_and_archive_questions_clean.jsonl"
    set "SUMMARY=out\summary_digra_sync_plus_city_protocols_and_archive_questions_clean.json"
) else if exist "out\agenda_items_digra_sync_plus_city_protocols_and_archive_questions.jsonl" (
    set "RECORDS=out\agenda_items_digra_sync_plus_city_protocols_and_archive_questions.jsonl"
    set "SUMMARY=out\summary_digra_sync_plus_city_protocols_and_archive_questions.json"
) else if exist "out\agenda_items_digra_sync_plus_city_protocols.jsonl" (
    set "RECORDS=out\agenda_items_digra_sync_plus_city_protocols.jsonl"
    set "SUMMARY=out\summary_digra_sync_plus_city_protocols.json"
) else if exist "out\agenda_items_digra_sync.jsonl" (
    set "RECORDS=out\agenda_items_digra_sync.jsonl"
    set "SUMMARY=out\summary_digra_sync.json"
) else if exist "out\agenda_items_digra_ai_plus_latest.jsonl" (
    set "RECORDS=out\agenda_items_digra_ai_plus_latest.jsonl"
    set "SUMMARY=out\summary_digra_plus_latest.json"
) else (
    set "RECORDS=out\agenda_items_digra_ai.jsonl"
    set "SUMMARY=out\summary_digra.json"
)
if not exist "!RECORDS!" (
    echo FEHLER: !RECORDS! fehlt.
    exit /b 1
)
if not exist "!SUMMARY!" (
    echo FEHLER: !SUMMARY! fehlt.
    exit /b 1
)

python -m graz_protocols.viewer --records "!RECORDS!" --summary "!SUMMARY!" --topics out\topic_candidates.json --output viewer.html --parking-cache out\parkgaragen_graz.csv --roadworks-cache out\baustellen_graz.html
exit /b %ERRORLEVEL%

:EnsureDigraBackground
where python >nul 2>nul
if errorlevel 1 exit /b 0
if not exist "out" mkdir "out"
if exist "out\digra_background.lock" (
    for /f "usebackq delims=" %%P in ("out\digra_background.lock") do set "DIGRA_BG_PID=%%P"
    if defined DIGRA_BG_PID (
        tasklist /FI "PID eq !DIGRA_BG_PID!" 2>nul | findstr /R "\<!DIGRA_BG_PID!\>" >nul
        if not errorlevel 1 (
            echo DIGRA-Hintergrunddienst laeuft bereits.
            exit /b 0
        )
    )
)
echo Starte DIGRA-Hintergrunddienst...
start "Graz DIGRA Hintergrunddienst" /min cmd /c "cd /d ""%REPO%"" && python -m graz_protocols.background_update --interval-minutes 30 --limit 30"
exit /b 0

:EnsureViewerServer
curl -fsS "http://127.0.0.1:8765/viewer.html" >nul 2>nul
if not errorlevel 1 (
    echo Lokaler Viewer-Server laeuft bereits.
    exit /b 0
)

where python >nul 2>nul
if errorlevel 1 (
    echo FEHLER: Python wurde nicht gefunden. Der Viewer-Server kann nicht gestartet werden.
    exit /b 1
)

echo Starte lokalen Viewer-Server auf http://127.0.0.1:8765 ...
start "Graz Viewer Server" /min cmd /c "cd /d ""%REPO%"" && python -m http.server 8765 --bind 127.0.0.1"

set /a server_tries=0
:WaitForViewerServer
ping -n 2 127.0.0.1 >nul
curl -fsS "http://127.0.0.1:8765/viewer.html" >nul 2>nul
if not errorlevel 1 (
    echo Lokaler Viewer-Server laeuft.
    exit /b 0
)
set /a server_tries+=1
if !server_tries! lss 10 goto WaitForViewerServer

echo FEHLER: Lokaler Viewer-Server antwortet nicht.
exit /b 1

:OpenViewer
if not exist "%VIEWER%" (
    echo FEHLER: viewer.html wurde nicht gefunden.
    exit /b 1
)
echo Oeffne viewer.html ...
start "" "%VIEWER_URL%?v=%RANDOM%%RANDOM%"
exit /b 0

:fail
echo.
echo Es ist ein Fehler aufgetreten. Fenster bleibt offen.
echo.
pause
exit /b 1
