@echo off

SET "SourceDir=%1"
SET "DestDir=%2"

setlocal EnableDelayedExpansion

set sourceDir=!sourceDir:"=!
set destDir=!destDir:"=!

IF NOT EXIST "%DestDir%\LOG" MD "%DestDir%\LOG"
cd /D "%sourcedir%"

for /r "%sourceDir%" %%i in (*.7z, *.zip, *.gz, *.rar) do ( 
	ECHO IL RESTE ENCORE A DES ARCHIVES DANS CE DOSSIER, UNE EXTRACTION EST NECESSAIRE AVANT DE CONTINUER
	ECHO.
	TITLE Extraction de %%~ni en cours...
	ECHO Extraction de %%~ni en cours...
	echo.
	"%~dp0\7za.exe" e "%%i" -aoa >> "%destdir%\LOG\log_zip_extract.txt"
	echo %%~ni extrait.
	echo.
	echo.
)
echo.



cd /D "%~dp0"

for /r "%sourceDir%" %%i in (*.cue, *.gdi, *.iso) do ( 
TITLE Conversion de %%~ni en CHD V5
echo ษออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออป
echo บConversion de %%~ni en CHD V5
echo ศออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออผ
echo.
IF NOT EXIST "%DestDir%\LOG" MD "%DestDir%\LOG"
		chdman createcd -i "%%i" -o "%DestDir%\%%~ni.chd" >> "%destdir%\LOG\log_chd_create.txt"
		echo.
		echo %%~ni converti en CHD V5.
		echo.
		)
echo ษอออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออป
Echo บ     Tous les jeux sont convertis , y'a plus qu'a jouer :D       บ
echo ศอออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออผ

pause>nul