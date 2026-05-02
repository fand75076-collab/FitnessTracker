$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot
$vbRoot = Split-Path -Parent (Split-Path -Parent $projectRoot)

$androidRoot = "D:\Android"
$jdkHome = Join-Path $androidRoot "jdk-17"
$sdkHome = Join-Path $androidRoot "sdk"
$gradleHome = Join-Path $androidRoot "gradle-8.10.2"
$gradleUserHome = Join-Path $androidRoot ".gradle"

$env:JAVA_HOME = $jdkHome
$env:ANDROID_HOME = $sdkHome
$env:ANDROID_SDK_ROOT = $sdkHome
$env:GRADLE_USER_HOME = $gradleUserHome
$env:Path = @(
    (Join-Path $jdkHome "bin"),
    (Join-Path $gradleHome "bin"),
    (Join-Path $sdkHome "cmdline-tools\latest\bin"),
    (Join-Path $sdkHome "platform-tools"),
    $env:Path
) -join ";"

$missing = @()
if (-not (Test-Path $jdkHome)) { $missing += "JDK at $jdkHome" }
if (-not (Test-Path $sdkHome)) { $missing += "Android SDK at $sdkHome" }
if (-not (Test-Path $gradleHome)) { $missing += "Gradle at $gradleHome" }

$javaExe = Join-Path $jdkHome "bin\java.exe"
if (-not (Test-Path $javaExe)) { $missing += "JDK java.exe at $javaExe" }

$gradleCmd = $null
if (Test-Path ".\gradlew.bat") {
    $gradleCmd = ".\gradlew.bat"
} elseif (Get-Command gradle -ErrorAction SilentlyContinue) {
    $gradleCmd = "gradle"
} elseif (Test-Path (Join-Path $gradleHome "bin\gradle.bat")) {
    $gradleCmd = Join-Path $gradleHome "bin\gradle.bat"
} else {
    $missing += "Gradle (gradle or gradlew.bat)"
}

if (-not (Test-Path (Join-Path $sdkHome "platforms\android-35\android.jar"))) {
    $missing += "Android SDK platform 35"
}

if ($missing.Count -gt 0) {
    Write-Host "Cannot build APK. Missing:" -ForegroundColor Yellow
    foreach ($item in $missing) {
        Write-Host " - $item" -ForegroundColor Yellow
    }
    Write-Host ""
    Write-Host "Install the missing components under D:\Android and re-run this script."
    exit 2
}

$dbSource = Join-Path $vbRoot "data\workout.db"
$dbDest = Join-Path $projectRoot "app\src\main\assets\workout.db"
$syncScript = Join-Path $vbRoot "sync_exercise_config.py"
$python = Join-Path $vbRoot ".venv\Scripts\python.exe"
if ((Test-Path $python) -and (Test-Path $syncScript)) {
    & $python $syncScript
}

if (Test-Path $dbSource) {
    if (Test-Path $python) {
        & $python -c "import sqlite3, sys; conn = sqlite3.connect(sys.argv[1]); conn.execute('PRAGMA wal_checkpoint(FULL)'); conn.close()" $dbSource
    }
    Copy-Item $dbSource $dbDest -Force
    Write-Host "Copied workout.db to assets" -ForegroundColor Green
}

Write-Host "Building APK..." -ForegroundColor Cyan
& $gradleCmd ":app:assembleDebug"

$apk = Join-Path $projectRoot "app\build\outputs\apk\debug\app-debug.apk"
if (Test-Path $apk) {
    Write-Host "APK built: $apk" -ForegroundColor Green
} else {
    throw "Gradle finished but APK was not found at $apk"
}
