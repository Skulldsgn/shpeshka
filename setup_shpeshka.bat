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
set "NODE=%COMFY%\ComfyUI\custom_nodes\shpeshka"

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
rem ваши правки таймлайна и сгенерированная таблица не перезаписываются
set "KEEP="
if exist "%DEST%\prompts\timeline.json" set "KEEP=timeline.json timing.md"
if defined KEEP (
  robocopy "%UNZ%\shpeshka-main" "%DEST%" /E /XF %KEEP% /NFL /NDL /NJH /NJS /NP >nul
) else (
  robocopy "%UNZ%\shpeshka-main" "%DEST%" /E /NFL /NDL /NJH /NJS /NP >nul
)
if errorlevel 8 (
  echo [ОШИБКА] Не удалось скопировать файлы.
  pause
  exit /b 1
)

rem убираем то, что ставили прошлые версии и что больше не нужно
for %%F in (comfy.bat detect_models.bat config.json prompts\scenes.json prompts\character.json ^
            scripts\comfy.py scripts\detect_models.py scripts\make_ui_workflows.py ^
            docs\character.md docs\pipeline.md) do if exist "%DEST%\%%F" del /q "%DEST%\%%F"
for %%D in (workflows post) do if exist "%DEST%\%%D" rmdir /s /q "%DEST%\%%D"
if exist "%COMFY%\ComfyUI\user\default\workflows\shpeshka" rmdir /s /q "%COMFY%\ComfyUI\user\default\workflows\shpeshka"

echo [3/4] Ставлю ноду «Спешка: стиль» в ComfyUI...
robocopy "%DEST%\comfyui_node" "%NODE%" /MIR /NFL /NDL /NJH /NJS /NP >nul

echo [4/4] Создаю команды unify и timing...
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

del "%ZIP%" 2>nul
rmdir /s /q "%UNZ%" 2>nul

echo.
echo === Готово ===
echo Перезапустите ComfyUI (закройте консоль и запустите заново).
echo Нода: двойной клик по холсту, поиск «Спешка». Ставится между VAE Decode и Save Image.
echo.
pause
