param(
    [string]$ShortcutName = "Man Hinh Dien Thoai CoC.lnk",
    [string]$Serial = "",
    [string]$WindowTitle = "",
    [string]$Description = "Mo man hinh dien thoai Android (Tu dong ket noi lai)"
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$TargetBat = Join-Path $ScriptDir "Mo_Man_Hinh_CoC.bat"
$DesktopDir = [Environment]::GetFolderPath("Desktop")
if (-not $ShortcutName.EndsWith(".lnk")) {
    $ShortcutName = "$ShortcutName.lnk"
}
$ShortcutPath = Join-Path $DesktopDir $ShortcutName

$ScrcpyExe = $env:SCRCPY_PATH
if (-not $ScrcpyExe) {
    $cmd = Get-Command scrcpy -ErrorAction SilentlyContinue
    if ($cmd) { $ScrcpyExe = $cmd.Source }
}
if (-not $ScrcpyExe) {
    $fallback = Join-Path $env:LOCALAPPDATA "scrcpy\scrcpy.exe"
    if (Test-Path $fallback) { $ScrcpyExe = $fallback }
}

$ArgParts = @()
if ($Serial) {
    $ArgParts += "`"$Serial`""
    if ($WindowTitle) {
        $ArgParts += "`"$WindowTitle`""
    }
}

$Shell = New-Object -ComObject WScript.Shell
$Lnk = $Shell.CreateShortcut($ShortcutPath)
$Lnk.TargetPath = $TargetBat
$Lnk.Arguments = ($ArgParts -join " ")
$Lnk.WorkingDirectory = $ScriptDir
$Lnk.Description = $Description
if ($ScrcpyExe -and (Test-Path $ScrcpyExe)) {
    $Lnk.IconLocation = "$ScrcpyExe,0"
}
$Lnk.Save()

Write-Output "Da tao Icon Desktop thanh cong tai: $ShortcutPath"
