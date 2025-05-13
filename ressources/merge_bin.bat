@echo OFF

SET "SourceDir=%1"
SET "DestDir=%2"

setlocal EnableDelayedExpansion

set sourceDir=!sourceDir:"=!
set destDir=!destDir:"=!




for /r "%sourceDir%" %%i in (*.cue) do ( 
TITLE Conversion de %%~ni - 0%%
ECHO Conversion de %%~ni - 0%%
IF NOT EXIST "%DestDir%\CHD_TEMP" MD "%DestDir%\CHD_TEMP"
IF NOT EXIST "%DestDir%\LOG" MD "%DestDir%\LOG" 
        TITLE Conversion de %%~ni - 25%%
        ECHO Conversion de %%~ni - 25%%
		ressources\chdman createcd -i "%sourceDir%\%%~ni.cue" -o "%DestDir%\CHD_TEMP\%%~ni.chd" -c none -f >> "%destdir%\LOG\log_chd_create.txt"
		TITLE Conversion de %%~ni - 50%%
		ECHO Conversion de %%~ni - 50%%
		ressources\chdman extractcd -i "%destDir%\CHD_TEMP\%%~ni.chd" -o "%DestDir%\%%~ni.cue" -ob "%DestDir%\%%~ni.bin" -f >> "%destdir%\LOG\log_chd_extract.txt"	
			del "%DestDir%\CHD_TEMP\%%~ni.chd" 
			rmdir /Q /S "%DestDir%\CHD_TEMP">nul
			TITLE Conversion de %%~ni - 100%%
			ECHO Conversion de %%~ni - 100%%			
			echo.
			echo %%~ni converti en un seul bin.
			echo.
		)

echo *******************************************************
Echo *Tous les jeux sont convertis , y'a plus qu'a jouer :D*
echo *******************************************************
pause>nul