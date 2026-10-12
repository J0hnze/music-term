@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows.ps1" -Mode start %*
set "music_term_exit=%errorlevel%"
if not "%music_term_exit%"=="0" pause
exit /b %music_term_exit%
