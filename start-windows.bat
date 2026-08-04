@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  start "" "http://localhost:8080"
  py -3 -m http.server 8080 --bind 127.0.0.1
  exit /b
)
where python >nul 2>nul
if %errorlevel%==0 (
  start "" "http://localhost:8080"
  python -m http.server 8080 --bind 127.0.0.1
  exit /b
)
if exist "C:\Users\I_jon\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" (
  start "" "http://localhost:8080"
  "C:\Users\I_jon\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m http.server 8080 --bind 127.0.0.1
  exit /b
)
echo Python hittades inte. Installera Python 3 eller anvand GitHub Pages-versionen.
pause
