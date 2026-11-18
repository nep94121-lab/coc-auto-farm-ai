$ErrorActionPreference = "Continue"

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host "  KIEM TRA & CAI DAT MOI TRƯỜNG WIN 10 CHO COC AUTO FARM AI" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir

# 1. Kiem tra Python & thu vien
Write-Host "`n[1/6] Kiem tra Python..." -ForegroundColor Yellow
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "[THIEU] Chua co Python! Hay cai Python 3.10+ (tick 'Add Python to PATH') hoac chay: winget install Python.Python.3.12" -ForegroundColor Red
} else {
    python --version
    Write-Host "Dang cai thu vien Python tu requirements.txt..."
    pip install -r (Join-Path $RepoRoot "requirements.txt")
}

# 2. Kiem tra ADB (Android Platform Tools)
Write-Host "`n[2/6] Kiem tra ADB..." -ForegroundColor Yellow
$adb = (Get-Command adb -ErrorAction SilentlyContinue).Source
if (-not $adb -and (Test-Path "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe")) {
    $adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
}
if (-not $adb) {
    Write-Host "[THIEU] Khong tim thay adb.exe! Hay chay: winget install Google.PlatformTools" -ForegroundColor Red
    Write-Host "        Hoac giai nen platform-tools vao: $env:LOCALAPPDATA\Android\Sdk\platform-tools\" -ForegroundColor Gray
} else {
    Write-Host "[OK] ADB: $adb" -ForegroundColor Green
    & $adb devices
}

# 3. Kiem tra scrcpy
Write-Host "`n[3/6] Kiem tra scrcpy (hien man hinh dien thoai)..." -ForegroundColor Yellow
$scrcpy = (Get-Command scrcpy -ErrorAction SilentlyContinue).Source
if (-not $scrcpy -and (Test-Path "$env:LOCALAPPDATA\scrcpy\scrcpy.exe")) {
    $scrcpy = "$env:LOCALAPPDATA\scrcpy\scrcpy.exe"
}
if (-not $scrcpy) {
    Write-Host "[THIEU] Khong tim thay scrcpy.exe! Hay chay: winget install Genymobile.scrcpy" -ForegroundColor Red
    Write-Host "        Hoac tai tai https://github.com/Genymobile/scrcpy/releases va giai nen vao $env:LOCALAPPDATA\scrcpy\" -ForegroundColor Gray
} else {
    Write-Host "[OK] scrcpy: $scrcpy" -ForegroundColor Green
}

# 4. Chong Win 10 ngat cong USB & ngu may khi cam sac (tranh out scrcpy/ADB)
Write-Host "`n[4/6] Cau hinh Win 10 khong tat nguon USB khi cam dien thoai..." -ForegroundColor Yellow
try {
    # Disable USB selective suspend (AC & DC)
    powercfg /SETACVALUEINDEX SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0 | Out-Null
    powercfg /SETDCVALUEINDEX SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0 | Out-Null
    powercfg /CHANGE standby-timeout-ac 0 | Out-Null
    powercfg /SETACTIVE SCHEME_CURRENT | Out-Null
    Write-Host "[OK] Da tat USB Selective Suspend va Sleep AC tren Win 10." -ForegroundColor Green
} catch {
    Write-Host "[WARN] Khong the chinh powercfg tu dong: $_" -ForegroundColor DarkYellow
}

# 5. Tao Icon ngoai Desktop
Write-Host "`n[5/6] Tao Icon Desktop (Man Hinh Dien Thoai CoC)..." -ForegroundColor Yellow
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ScriptDir "Tao_Icon_Desktop.ps1")

# 6. Chay bo test offline
Write-Host "`n[6/6] Chay pytest kiem thu he thong..." -ForegroundColor Yellow
Push-Location $RepoRoot
python -m pytest tests/test_offline_suite.py -v --timeout=30
Pop-Location

Write-Host "`nHoan tat kiem tra! Neu thiet bi moi khac Galaxy S9 (2220x1080), hay doc muc 'Thiet Bi Moi' trong AGENTS.md." -ForegroundColor Cyan
