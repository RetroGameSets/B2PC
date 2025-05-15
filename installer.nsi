; Script NSIS personnalisé pour B2PC !define APP_NAME "B2PC" !define COMPANY_NAME "RetroGameSets.fr" !define APP_DESCRIPTION "Batch Games Converter - Convert and patch retro game ROMs"

; Page de bienvenue !define MUI_WELCOMEFINISHPAGE_BITMAP "${NSISDIR}\Contrib\Graphics\Wizard\win.bmp" !insertmacro MUI_PAGE_WELCOME

; Page de sélection du répertoire !insertmacro MUI_PAGE_DIRECTORY

; Page d'installation !insertmacro MUI_PAGE_INSTFILES

; Page de fin !define MUI_FINISHPAGE_RUN "$INSTDIR\B2PC.exe" !define MUI_FINISHPAGE_RUN_TEXT "Lancer B2PC" !insertmacro MUI_PAGE_FINISH

; Page de désinstallation !insertmacro MUI_UNPAGE_CONFIRM !insertmacro MUI_UNPAGE_INSTFILES

; Langue !insertmacro MUI_LANGUAGE "French"

; Nom de l'application Name "${APP_NAME}" OutFile "B2PC-Setup.exe"

; Dossier d'installation par défaut InstallDir "$PROGRAMFILES${APP_NAME}"

; Section d'installation Section SetOutPath "$INSTDIR" ; Les fichiers sont automatiquement inclus par Electron Forge SectionEnd