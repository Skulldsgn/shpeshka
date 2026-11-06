@echo off
chcp 65001 >nul
setlocal EnableExtensions

rem ================== Настройки: поправьте, если пути другие ==================
set "COMFY=D:\AI\ComfyUI_windows_portable"
set "DEST=D:\AI\shpeshka"
rem ============================================================================

set "PY=%COMFY%\python_embeded\python.exe"
set "NODE=%COMFY%\ComfyUI\custom_nodes\shpeshka"
set "ZIP=%TEMP%\shpeshka.zip"
set "UNZ=%TEMP%\shpeshka_unz"
set "SRC=%UNZ%\shpeshka-main"
set "URL=https://github.com/Skulldsgn/shpeshka/archive/refs/heads/main.zip"
set "LOG=%DEST%\setup_log.txt"
set "ERRS=0"

if not exist "%DEST%" mkdir "%DEST%"
> "%LOG%" echo Установка «Спешка» %DATE% %TIME%

call :say ""
call :say "=== Установка проекта «Спешка» ==="
call :say "ComfyUI: %COMFY%"
call :say "Проект:  %DEST%"
call :say ""

rem ---------- 1. Проверки ----------
call :say "[1/6] Проверяю пути..."
if not exist "%COMFY%\ComfyUI\main.py" goto :no_comfy
if not exist "%PY%" goto :no_python
"%PY%" -c "import numpy, PIL, torch" >nul 2>&1
if errorlevel 1 goto :no_libs
call :say "      ComfyUI и его Python на месте."

powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 8188 -State Listen -ErrorAction SilentlyContinue) { exit 1 }" >nul 2>&1
if errorlevel 1 call :say "      ComfyUI сейчас запущен — после установки его нужно будет перезапустить."

rem ---------- 2. Скачивание ----------
call :say "[2/6] Скачиваю проект с GitHub..."
if exist "%UNZ%" rmdir /s /q "%UNZ%"
del /q "%ZIP%" 2>nul
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol='Tls12'; Invoke-WebRequest -Uri '%URL%' -OutFile '%ZIP%'" >nul 2>&1
if not exist "%ZIP%" curl.exe -sL -o "%ZIP%" "%URL%" >nul 2>&1
if not exist "%ZIP%" goto :no_download
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Force '%ZIP%' '%UNZ%'" >nul 2>&1
if not exist "%SRC%\comfyui_node\__init__.py" goto :bad_zip
call :say "      Скачано."

rem ---------- 3. Уборка старого ----------
call :say "[3/6] Убираю всё, что ставили прошлые версии..."
for %%F in (comfy.bat detect_models.bat config.json ^
            prompts\scenes.json prompts\character.json ^
            scripts\comfy.py scripts\detect_models.py scripts\make_ui_workflows.py ^
            docs\character.md docs\pipeline.md) do (
  if exist "%DEST%\%%F" del /q "%DEST%\%%F" & >>"%LOG%" echo       удалён %%F
)
for %%D in (workflows post scripts\__pycache__ comfyui_node) do (
  if exist "%DEST%\%%D" rmdir /s /q "%DEST%\%%D" & >>"%LOG%" echo       удалена папка %%D
)
rem пустые папки от старого установщика; непустые не трогаем
for %%D in (refs selects final) do rmdir "%DEST%\%%D" 2>nul
rem старые готовые графы в библиотеке ComfyUI
if exist "%COMFY%\ComfyUI\user\default\workflows\shpeshka" rmdir /s /q "%COMFY%\ComfyUI\user\default\workflows\shpeshka"
rem старая нода целиком: поставим заново
if exist "%NODE%" rmdir /s /q "%NODE%"
rem таймлайн со старыми готовыми сценами заменяем, свой — оставляем
set "KEEP_TL=0"
if exist "%DEST%\prompts\timeline.json" (
  findstr /C:"\"s01\"" "%DEST%\prompts\timeline.json" >nul 2>&1 || set "KEEP_TL=1"
)
call :say "      Готово."

rem ---------- 4. Копирование ----------
call :say "[4/6] Копирую файлы..."
if "%KEEP_TL%"=="1" (
  robocopy "%SRC%" "%DEST%" /E /XF timeline.json /NFL /NDL /NJH /NJS /NP >nul
) else (
  robocopy "%SRC%" "%DEST%" /E /NFL /NDL /NJH /NJS /NP >nul
)
if errorlevel 8 goto :no_copy
if "%KEEP_TL%"=="1" call :say "      Ваш prompts\timeline.json сохранён."
robocopy "%SRC%\comfyui_node" "%NODE%" /E /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 goto :no_copy
rem таблица таймингов под текущий таймлайн
"%PY%" "%DEST%\scripts\timing.py" >>"%LOG%" 2>&1

rem ---------- 5. Проверка ноды ----------
call :say "[5/6] Проверяю ноду на Python ComfyUI..."
"%PY%" -c "import sys; sys.path.insert(0, r'%NODE%'); import numpy as np, shpeshka_style as s; r = s.stylize(np.full((64, 64, 3), 0.5, np.float32)); assert r.shape == (64, 64, 3); print('ok')" >>"%LOG%" 2>&1
if errorlevel 1 set "ERRS=1"
if "%ERRS%"=="1" call :say "      [!] Нода не прошла проверку. Подробности в setup_log.txt."
if "%ERRS%"=="0" call :say "      Нода «Спешка: стиль» работает."

rem ---------- 6. Команды ----------
call :say "[6/6] Создаю команды unify и timing..."
> "%DEST%\unify.bat" (
  echo @echo off
  echo chcp 65001 ^>nul
  echo "%PY%" "%DEST%\scripts\unify.py" %%*
)
> "%DEST%\timing.bat" (
  echo @echo off
  echo chcp 65001 ^>nul
  echo "%PY%" "%DEST%\scripts\timing.py" %%*
)
where ffmpeg >nul 2>&1 || call :say "      ffmpeg не найден в PATH: аниматик (timing --animatic) не соберётся, остальное работает."

del /q "%ZIP%" 2>nul
rmdir /s /q "%UNZ%" 2>nul

call :say ""
if "%ERRS%"=="0" call :say "=== Готово ==="
if not "%ERRS%"=="0" call :say "=== Готово, но с ошибками: см. setup_log.txt ==="
call :say "1. Перезапустите ComfyUI: закройте консоль и запустите run_nvidia_gpu.bat заново."
call :say "2. Двойной клик по холсту, поиск «Спешка», нода ставится между VAE Decode и Save Image."
call :say "Лог: %LOG%"
echo.
pause
exit /b 0

rem ---------- ошибки ----------
:no_comfy
call :say "[ОШИБКА] Не найден ComfyUI в %COMFY%. Поправьте путь COMFY в начале файла."
goto :fail
:no_python
call :say "[ОШИБКА] Не найден встроенный Python: %PY%"
goto :fail
:no_libs
call :say "[ОШИБКА] В Python ComfyUI нет numpy, pillow или torch. ComfyUI установлен полностью?"
goto :fail
:no_download
call :say "[ОШИБКА] Не удалось скачать проект. Проверьте интернет."
goto :fail
:bad_zip
call :say "[ОШИБКА] Скачанный архив повреждён или пустой. Запустите установщик ещё раз."
goto :fail
:no_copy
call :say "[ОШИБКА] Не удалось скопировать файлы. Закройте программы, которые держат папку проекта, и повторите."
goto :fail
:fail
call :say "Лог: %LOG%"
echo.
pause
exit /b 1

rem ---------- вывод в консоль и в лог ----------
:say
if "%~1"=="" goto :say_empty
echo %~1
>>"%LOG%" echo %~1
exit /b 0
:say_empty
echo.
>>"%LOG%" echo.
exit /b 0
