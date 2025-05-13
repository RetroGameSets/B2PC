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

CD /D "%~dp0"

IF NOT EXIST "%DestDir%\xiso.exe" COPY xiso.exe "%DestDir%\"
cls
cd /D "%DestDir%"

for /r "%sourceDir%" %%i in (*.iso) do ( 
TITLE Conversion de %%~ni
ECHO Conversion de %%~ni
echo.
		"%DestDir%\xiso.exe" -r "%sourceDir%\%%~ni.iso" >> "%destdir%\LOG\log_xbox_convert.txt"
		echo.
		echo %%~ni converti.
		echo.
		echo.
		)
echo *******************************************************
Echo *Tous les jeux sont convertis , y'a plus qu'a jouer :D*
echo *******************************************************

del /s /q "%DestDir%\xiso.exe" >NUL



pause>nul