@echo off
rem Start the inkdict GUI on Windows: double-click this file.
rem It needs uv (https://docs.astral.sh/uv/), which installs Python 3.13 and the requirements by itself, and git.
cd /d "%~dp0"

where uv >nul 2>nul
if errorlevel 1 goto no_uv
where git >nul 2>nul
if errorlevel 1 goto no_git

set UV_PYTHON_PREFERENCE=only-managed
uv run --no-project --python 3.13 --with-requirements requirements.txt python -m wikidict.gui %*
if errorlevel 1 pause
exit /b

:no_uv
echo uv is needed. Install it with:
echo     powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
echo then run this file again.
pause
exit /b 1

:no_git
echo git is needed (to install a dependency): https://git-scm.com/download/win
echo Install it, then run this file again.
pause
exit /b 1
