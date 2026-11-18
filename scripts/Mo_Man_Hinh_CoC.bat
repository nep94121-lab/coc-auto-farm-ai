@echo off
setlocal enabledelayedexpansion
title Hien Thi Man Hinh Dien Thoai (CoC Auto - Tu Dong Ket Noi Lai)

set "ADB_EXE=%ADB_PATH%"
if "%ADB_EXE%"=="" (
    for /f "delims=" %%i in ('where adb 2^>nul') do if "!ADB_EXE!"=="" set "ADB_EXE=%%i"
)
if "%ADB_EXE%"=="" if exist "%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe" (
    set "ADB_EXE=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
)
if "%ADB_EXE%"=="" (
    echo [LOI] Khong tim thay adb.exe! Hay cai Android Platform Tools hoac dat bien ADB_PATH.
    pause
    exit /b 1
)

set "SCRCPY_EXE=%SCRCPY_PATH%"
if "%SCRCPY_EXE%"=="" (
    for /f "delims=" %%i in ('where scrcpy 2^>nul') do if "!SCRCPY_EXE!"=="" set "SCRCPY_EXE=%%i"
)
if "%SCRCPY_EXE%"=="" if exist "%LOCALAPPDATA%\scrcpy\scrcpy.exe" (
    set "SCRCPY_EXE=%LOCALAPPDATA%\scrcpy\scrcpy.exe"
)
if "%SCRCPY_EXE%"=="" (
    echo [LOI] Khong tim thay scrcpy.exe! Tai scrcpy tai https://github.com/Genymobile/scrcpy/releases va giai nen vao %LOCALAPPDATA%\scrcpy
    pause
    exit /b 1
)

set "SERIAL_ARG="
if not "%ANDROID_SERIAL%"=="" set "SERIAL_ARG=-s %ANDROID_SERIAL%"

:RECONNECT_LOOP
cls
echo ====================================================================
echo   KET NOI MAN HINH DIEN THOAI CHO CLASH OF CLANS - AUTO RECONNECT
echo   - ADB   : %ADB_EXE%
echo   - SCRCPY: %SCRCPY_EXE%
echo ====================================================================

"%ADB_EXE%" start-server >nul 2>&1
"%ADB_EXE%" %SERIAL_ARG% get-state >nul 2>&1
if errorlevel 1 (
    echo [!] Dang thu ket noi lai ADB...
    "%ADB_EXE%" %SERIAL_ARG% reconnect >nul 2>&1
    "%ADB_EXE%" wait-for-device
)

"%ADB_EXE%" %SERIAL_ARG% shell "svc power stayon true; settings put system screen_off_timeout 2147483647; dumpsys deviceidle whitelist +com.supercell.clashofclans >/dev/null 2>&1; input keyevent KEYCODE_WAKEUP; wm dismiss-keyguard" >nul 2>&1

echo [OK] Dang mo cua so man hinh dien thoai - Bam X de dong han
"%SCRCPY_EXE%" %SERIAL_ARG% --window-title="Samsung Galaxy S9 (CoC Auto)" --no-audio --stay-awake --max-fps=60
set "EXIT_CODE=%ERRORLEVEL%"

if "%EXIT_CODE%"=="0" (
    echo [INFO] Da dong man hinh theo yeu cau nguoi dung.
    exit /b 0
)

echo [CANH BAO] Mat ket noi scrcpy, ma loi=%EXIT_CODE%. Tu dong ket noi lai sau 2 giay...
timeout /t 2 /nobreak >nul
goto RECONNECT_LOOP
