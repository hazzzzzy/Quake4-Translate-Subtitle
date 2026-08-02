@echo off
rem =====================================================================
rem  Quake 4 Chinese Localization Launcher
rem  First use: edit GAME_DIR below to your Quake 4 install folder
rem  (the folder that contains the "q4base" subfolder)
rem  Details / help: see README.txt
rem
rem  RESOLUTION: edit W and H below. On first launch these are written
rem  to Quake4Config.cfg. After that, edit Quake4Config.cfg directly
rem  (in the savedata\q4base folder) to change resolution.
rem =====================================================================
set GAME_DIR=C:\Program Files (x86)\Steam\steamapps\common\Quake 4

rem Default resolution (16:9 recommended, fonts are calibrated for 16:9)
set W=1920
set H=1080

if not exist "%GAME_DIR%\q4base\pak001.pk4" (
  echo [ERROR] Not found: "%GAME_DIR%\q4base\pak001.pk4"
  echo Edit this file and set GAME_DIR to your Quake 4 install folder.
  pause
  exit /b 1
)
if not exist "%GAME_DIR%\q4base\pak021.pk4" (
  echo [ERROR] Your Quake 4 is not patched to 1.4.2 ^(pak021.pk4 missing^).
  echo Retail/CD version: install the official 1.4.2 patch first.
  echo Steam version already includes it.
  pause
  exit /b 1
)

rem Write default resolution to config ONLY if config doesn't exist yet
set CFG=%~dp0savedata\q4base\Quake4Config.cfg
if not exist "%CFG%" (
  if not exist "%~dp0savedata\q4base" mkdir "%~dp0savedata\q4base"
  echo seta r_fullscreen "1"> "%CFG%"
  echo seta r_mode "-1">> "%CFG%"
  echo seta r_customWidth "%W%">> "%CFG%"
  echo seta r_customHeight "%H%">> "%CFG%"
  echo [INFO] First launch: resolution set to %W%x%H%.
  echo [INFO] To change resolution later, edit Quake4Config.cfg in savedata\q4base\
)

"%~dp0engine\Quake4.exe" ^
 +set fs_basepath "%GAME_DIR%" ^
 +set fs_savepath "%~dp0savedata" ^
 +set sys_lang chinese +set harm_gui_wideCharLang 1 ^
 +set gui_smallFontLimit 0 ^
 +set image_forceDownSize 0 ^
 +set com_allowConsole 1 ^
 +set logFile 2 ^
 +set r_fullscreen 1 ^
 +set r_useShadowMapping 1 +set harm_r_softStencilShadow 0
