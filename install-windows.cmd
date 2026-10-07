@echo off
setlocal
pushd "%~dp0"
if not exist "pyproject.toml" (
  echo Extract the complete ZIP first, then run this file from the extracted folder.
  goto failed
)
py -3.12 -c "import sys; assert sys.version_info >= (3,11)" >nul 2>&1
if not errorlevel 1 (
  py -3.12 "installer\install_local.py"
  goto finished
)
py -3 -c "import sys; assert sys.version_info >= (3,11)" >nul 2>&1
if not errorlevel 1 (
  py -3 "installer\install_local.py"
  goto finished
)
python -c "import sys; assert sys.version_info >= (3,11)" >nul 2>&1
if not errorlevel 1 (
  python "installer\install_local.py"
  goto finished
)
echo Python 3.11+ was not found. Installing Python 3.12 for the current user...
winget install --id Python.Python.3.12 --exact --source winget --scope user --accept-package-agreements --accept-source-agreements
if errorlevel 1 goto python_failed
if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
  "%LocalAppData%\Programs\Python\Python312\python.exe" "installer\install_local.py"
  goto finished
)
echo Python was installed. Close this window and run install-windows.cmd again.
popd
pause
exit /b 0
:python_failed
echo Automatic Python installation was unavailable.
echo Install Python 3.12 from https://www.python.org/downloads/ and run this file again.
goto failed
:finished
if errorlevel 1 goto failed
echo Installation and Codex MCP registration completed. Restart Codex.
popd
pause
exit /b 0
:failed
echo Installation did not complete. Keep the error message shown above.
popd
pause
exit /b 1
