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

for /r "%sourceDir%" %%i in (*.chd) do ( 
TITLE Conversion de %%~ni
ECHO Conversion de %%~ni
echo.
IF NOT EXIST "%DestDir%\LOG" MD "%DestDir%\LOG"
IF NOT EXIST "%DestDir%\BIN" MD "%DestDir%\BIN"
		chdman extractcd -i "%sourceDir%\%%~ni.chd" -o "%DestDir%\BIN\%%~ni.cue" -ob "%DestDir%\BIN\%%~ni.bin" -f >> "%destdir%\LOG\log_chd_extract.txt"	
		echo.
		echo %%~ni extrait.
		echo.
		)
echo *******************************************************
Echo *Tous les jeux sont convertis , y'a plus qu'a jouer :D*
echo *******************************************************

pause>nul