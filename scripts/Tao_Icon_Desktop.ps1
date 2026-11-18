$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$TargetBat = Join-Path $ScriptDir "Mo_Man_Hinh_CoC.bat"
$DesktopDir = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $DesktopDir "Man Hinh Dien Thoai CoC.lnk"

$ScrcpyExe = $env:SCRCPY_PATH
if (-not $ScrcpyExe) {
    $cmd = Get-Command scrcpy -ErrorAction SilentlyContinue
    if ($cmd) { $ScrcpyExe = $cmd.Source }
}
if (-not $ScrcpyExe) {
    $fallback = Join-Path $env:LOCALAPPDATA "scrcpy\scrcpy.exe"
    if (Test-Path $fallback) { $ScrcpyExe = $fallback }
}

$Shell = New-Object -ComObject WScript.Shell
$Lnk = $Shell.CreateShortcut($ShortcutPath)
$Lnk.TargetPath = $TargetBat
$Lnk.WorkingDirectory = $ScriptDir
$Lnk.Description = "Mo man hinh dien thoai Android (Clash of Clans Auto - Tu dong ket noi lai)"
if ($ScrcpyExe -and (Test-Path $ScrcpyExe)) {
    $Lnk.IconLocation = "$ScrcpyExe,0"
}
$Lnk.Save()

Write-Output "Da tao Icon Desktop thanh cong tai: $ShortcutPath"
