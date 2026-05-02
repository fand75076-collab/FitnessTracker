$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Python virtual environment not found: $python"
}

& $python -m pip install -r (Join-Path $root "requirements.txt") pyinstaller

$dbSource = Join-Path $root "data\workout.db"
if (Test-Path $dbSource) {
    & $python -c "import sqlite3, sys; conn = sqlite3.connect(sys.argv[1]); conn.execute('PRAGMA wal_checkpoint(FULL)'); conn.close()" $dbSource
}

Push-Location $root
try {
    & $python -m PyInstaller `
        --noconfirm `
        --clean `
        --windowed `
        --name FitnessTracker `
        --add-data "app.py;." `
        --add-data "fitness_tracker/config;fitness_tracker/config" `
        --add-data "fitness_tracker/static;fitness_tracker/static" `
        --collect-all streamlit `
        --collect-all altair `
        --collect-all webview `
        --collect-all pythonnet `
        --collect-all clr_loader `
        --exclude-module pytest `
        --exclude-module pyarrow.tests `
        --exclude-module pandas.tests `
        --exclude-module numpy.tests `
        --collect-submodules fitness_tracker `
        launcher.py

    $dataDest = Join-Path $root "dist\FitnessTracker\data"
    New-Item -ItemType Directory -Force -Path $dataDest | Out-Null
    if (Test-Path $dbSource) {
        Copy-Item $dbSource (Join-Path $dataDest "workout.db") -Force
    }
}
finally {
    Pop-Location
}
