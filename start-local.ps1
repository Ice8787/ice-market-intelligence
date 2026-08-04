$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = Get-Command py -ErrorAction SilentlyContinue
if ($python) {
    Start-Process 'http://localhost:8080'
    & $python.Source -3 -m http.server 8080 --bind 127.0.0.1
    exit
}
$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) {
    Start-Process 'http://localhost:8080'
    & $python.Source -m http.server 8080 --bind 127.0.0.1
    exit
}
$bundledPython = 'C:\Users\I_jon\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (Test-Path -LiteralPath $bundledPython) {
    Start-Process 'http://localhost:8080'
    & $bundledPython -m http.server 8080 --bind 127.0.0.1
    exit
}
throw 'Python 3 hittades inte. Starta projektet inifrån Codex eller installera Python 3.'
