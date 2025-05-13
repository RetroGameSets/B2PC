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


for /r "%sourceDir%" %%i in (*.cue) do ( 
TITLE Conversion de %%~ni - 0%%
ECHO Conversion de %%~ni - 0%%
IF NOT EXIST "%DestDir%\CHD_TEMP" MD "%DestDir%\CHD_TEMP"
IF NOT EXIST "%DestDir%\BIN_TEMP" MD "%DestDir%\BIN_TEMP"
IF NOT EXIST "%DestDir%\LOG" MD "%DestDir%\LOG" 
        TITLE Conversion de %%~ni - 25%%
        ECHO Conversion de %%~ni - 25%%
		chdman createcd -i "%sourceDir%\%%~ni.cue" -o "%DestDir%\CHD_TEMP\%%~ni.chd" -c none -f >> "%destdir%\LOG\log_chd_create.txt"
		TITLE Conversion de %%~ni - 50%%
		ECHO Conversion de %%~ni - 50%%
		chdman extractcd -i "%destDir%\CHD_TEMP\%%~ni.chd" -o "%DestDir%\BIN_TEMP\%%~ni.cue" -ob "%DestDir%\BIN_TEMP\%%~ni.bin" -f >> "%destdir%\LOG\log_chd_extract.txt"	
			del "%DestDir%\CHD_TEMP\%%~ni.chd" 
		TITLE Conversion de %%~ni - 75%%
		ECHO Conversion de %%~ni - 75%%
		bintopbp "%DestDir%\BIN_TEMP" "%DestDir%" >> "%destdir%\LOG\log_pbp.txt"
			del "%DestDir%\BIN_TEMP\%%~ni.cue"
			del "%DestDir%\BIN_TEMP\%%~ni.bin"
			rmdir /Q /S "%DestDir%\BIN_TEMP">nul
			rmdir /Q /S "%DestDir%\CHD_TEMP">nul
			TITLE Conversion de %%~ni - 100%%
			ECHO Conversion de %%~ni - 100%%			
			echo.
			echo %%~ni converti en pbp.
			echo.
		)

echo *******************************************************
Echo *Tous les jeux sont convertis , y'a plus qu'a jouer :D*
echo *******************************************************
pause>nul