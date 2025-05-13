@echo off

SET "SourceDir=%1"
SET "DestDir=%2"

setlocal EnableDelayedExpansion

set sourceDir=!sourceDir:"=!
set destDir=!destDir:"=!

IF NOT EXIST "%DestDir%\LOG" MD "%DestDir%\LOG"
cd /D "%sourcedir%"

for %%f in (*) do (
  if not "%%~xf"==".zip" (
	TITLE Compression de %%~nf en cours...
	ECHO Compression de %%~nf en cours...
	echo.
	
	
	"%~dp0\7za.exe" a "%DestDir%\%%~nf.zip" "%%f" -mx9 >> "%destdir%\LOG\log_zip_compress.txt"
	echo %%~nf compressé.
	  )
)
	echo.
	echo.
)
echo.

echo ÉÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍ»
Echo º     Tous les jeux sont convertis , y'a plus qu'a jouer :D       º
echo ÈÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍ¼

pause>nul