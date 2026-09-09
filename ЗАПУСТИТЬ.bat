@echo off
setlocal
chcp 65001 >nul
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\launcher.ps1" %*
set "AUTONAVY_EXIT=%ERRORLEVEL%"
if not "%AUTONAVY_EXIT%"=="0" if not "%AUTONAVY_NO_PAUSE%"=="1" pause
exit /b %AUTONAVY_EXIT%
