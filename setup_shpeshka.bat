@echo off
chcp 65001 >nul
setlocal

rem ===== Настройки: поправьте, если пути другие =====
set "COMFY=D:\AI\ComfyUI_windows_portable"
set "DEST=D:\AI\shpeshka"
rem ===================================================

set "PY=%COMFY%\python_embeded\python.exe"
set "ZIP=%TEMP%\shpeshka.zip"
set "UNZ=%TEMP%\shpeshka_unz"

echo.
echo === Установка проекта «Спешка» ===
echo ComfyUI: %COMFY%
echo Проект:  %DEST%
echo.

if not exist "%PY%" (
  echo [ОШИБКА] Не найден Python ComfyUI: %PY%
  echo Проверьте путь COMFY в начале этого файла.
  pause
  exit /b 1
)

echo [1/4] Скачиваю проект с GitHub...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ProgressPreference='SilentlyContinue';" ^
  "Invoke-WebRequest -Uri 'https://github.com/Skulldsgn/shpeshka/archive/refs/heads/main.zip' -OutFile '%ZIP%';" ^
  "if (Test-Path '%UNZ%') { Remove-Item -Recurse -Force '%UNZ%' };" ^
  "Expand-Archive -Force '%ZIP%' '%UNZ%'"
if errorlevel 1 (
  echo [ОШИБКА] Не удалось скачать. Проверьте интернет.
  pause
  exit /b 1
)

echo [2/4] Копирую файлы в %DEST%...
if exist "%DEST%\config.json" (
  rem обновление: свой config.json не трогаем
  robocopy "%UNZ%\shpeshka-main" "%DEST%" /E /XF config.json /NFL /NDL /NJH /NJS /NP >nul
) else (
  robocopy "%UNZ%\shpeshka-main" "%DEST%" /E /NFL /NDL /NJH /NJS /NP >nul
)
if errorlevel 8 (
  echo [ОШИБКА] Не удалось скопировать файлы.
  pause
  exit /b 1
)
mkdir "%DEST%\refs" 2>nul
mkdir "%DEST%\selects" 2>nul
mkdir "%DEST%\final" 2>nul

echo [3/4] Ищу модели в ComfyUI и записываю config.json...
"%PY%" "%DEST%\scripts\detect_models.py" "%COMFY%"

echo [4/4] Создаю ярлыки команд...
(
  echo @echo off
  echo chcp 65001 ^>nul
  echo "%PY%" "%DEST%\scripts\comfy.py" %%*
) > "%DEST%\comfy.bat"
(
  echo @echo off
  echo chcp 65001 ^>nul
  echo "%PY%" "%DEST%\scripts\unify.py" %%*
) > "%DEST%\unify.bat"
(
  echo @echo off
  echo chcp 65001 ^>nul
  echo "%PY%" "%DEST%\scripts\timing.py" %%*
) > "%DEST%\timing.bat"
(
  echo @echo off
  echo chcp 65001 ^>nul
  echo "%PY%" "%DEST%\scripts\detect_models.py" "%COMFY%"
  echo pause
) > "%DEST%\detect_models.bat"

del "%ZIP%" 2>nul
rmdir /s /q "%UNZ%" 2>nul

echo.
echo === Готово ===
echo Дальше: запустите ComfyUI (run_nvidia_gpu.bat), потом в открывшемся окне:
echo     comfy character single --variants 8
echo Результаты будут в %DEST%\output
echo.
start "Спешка" cmd /k "cd /d "%DEST%""
pause
