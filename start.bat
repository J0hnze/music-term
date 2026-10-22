@echo off
set "music_term_args=%*"
if defined music_term_args set "music_term_args=%music_term_args:--debug=-Debug%"
if defined music_term_args set "music_term_args=%music_term_args:--deugb=-Debug%"
if defined music_term_args set "music_term_args=%music_term_args:--test-artwork=-TestArtwork%"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows.ps1" -Mode start %music_term_args%
set "music_term_exit=%errorlevel%"
if not "%music_term_exit%"=="0" pause
exit /b %music_term_exit%
