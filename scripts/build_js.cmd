@echo off
rem Build jslib (TS -> pylightcharts/js/)
rem Usage: scripts\build_js.cmd  (run from anywhere in the repo)
setlocal
pushd "%~dp0..\jslib"
echo [build] %CD%
call npm run build
if errorlevel 1 goto failed
popd
echo [build] done -^> pylightcharts\js\
endlocal
exit /b 0
:failed
popd
echo [build] failed
endlocal
exit /b 1
