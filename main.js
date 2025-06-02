const { app, BrowserWindow, ipcMain, dialog, screen } = require('electron');
const { autoUpdater } = require('electron-updater');
const path = require('path');
const fs = require('fs');
const fsPromises = require('fs').promises;
const { enable, initialize } = require('@electron/remote/main');
const patchXboxIsoHandler = require('./handlers/patchXboxIsoHandler');
const convertToChdv5Handler = require('./handlers/convertToChdv5Handler');
const convertIsoToRvzHandler = require('./handlers/convertIsoToRvzHandler');
const mergeBinCueHandler = require('./handlers/mergeBinCueHandler');
const extractChdHandler = require('./handlers/extractChdHandler');
const compressWsquashFSHandler = require('./handlers/compressWsquashFSHandler');
const extractWsquashFSHandler = require('./handlers/extractWsquashFSHandler');

// Modules utilitaires
const { extractArchives, extractWith7z, prepareDirectories, cleanupFiles } = require('./utils');
const { runTool, validateTools, checkIsoCompatibility } = require('./tools');
const { sendLog, sendProgress } = require('./logger');

// Logger pour electron-updater
autoUpdater.logger = require('electron-log');
autoUpdater.logger.transports.file.level = 'info';

initialize();
let mainWindow;

// Détection du contexte (packagé ou dev)
const isPackaged = app.isPackaged;
const resourcesPath = isPackaged
    ? path.join(path.dirname(process.resourcesPath), 'ressources')
    : path.join(__dirname, 'ressources');

const tools = {
    sevenZip: path.join(resourcesPath, '7za.exe'),
    xiso: path.join(resourcesPath, 'xiso.exe'),
    chdman: path.join(resourcesPath, 'chdman.exe'),
    dolphinTool: path.join(resourcesPath, 'dolphin-tool.exe'),
    gensquashfs: path.join(resourcesPath, 'gensquashfs.exe'),
    unsquashfs: path.join(resourcesPath, 'unsquashfs.exe')
};

// Demande de confirmation de nettoyage
async function askCleanupConfirmation() {
    return new Promise((resolve) => {
        const cleanupChannel = 'confirm-cleanup';
        ipcMain.once(cleanupChannel, (_, shouldDelete) => {
            resolve(shouldDelete);
        });
        if (mainWindow) {
            mainWindow.webContents.send('request-cleanup-confirmation', cleanupChannel);
        } else {
            resolve(false);
        }
    });
}

// Création de la fenêtre principale
function createWindow() {
    const { width: screenWidth, height: screenHeight } = screen.getPrimaryDisplay().workAreaSize;

    let options = {
        minWidth: 800,
        minHeight: 600,
        resizable: true,
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false,
            sandbox: false
        }
    };

    if (screenWidth <= 1920 && screenHeight <= 1080) {
        //pour petites résolutions
        options.width = 1280;
        options.height = 800;
        options.x = Math.floor((screenWidth - 1280) / 2);
        options.y = Math.floor((screenHeight - 800) / 2);
    } else {
        // Fenêtre 1920x1080 centrée pour grandes résolutions
        options.width = 1920;
        options.height = 1080;
        options.x = Math.floor((screenWidth - 1920) / 2);
        options.y = Math.floor((screenHeight - 1080) / 2);
    }

    mainWindow = new BrowserWindow(options);
    enable(mainWindow.webContents);
    mainWindow.loadFile('index.html');
    mainWindow.setMenu(null);
    //mainWindow.webContents.openDevTools();

    const imagesPath = path.join(__dirname, 'ressources', 'images');
    if (!fs.existsSync(resourcesPath)) {
        sendLog(mainWindow, `Erreur : Dossier ressources non trouvé à ${resourcesPath}`);
    } else {
        sendLog(mainWindow, `Dossier ressources trouvé à ${resourcesPath}`);
    }
    if (!fs.existsSync(imagesPath)) {
        sendLog(mainWindow, `Erreur : Dossier images non trouvé à ${imagesPath}`);
    } else {
        sendLog(mainWindow, `Dossier images trouvé à ${imagesPath}`);
    }
}

// Gestion du cycle de vie de l'application
app.whenReady().then(() => {
    createWindow();

    if (process.env.NODE_ENV === 'development') {
        const devUpdatePath = path.join(__dirname, 'dev-app-update.yml');
        if (fs.existsSync(devUpdatePath)) {
            autoUpdater.updateConfigPath = devUpdatePath;
            autoUpdater.forceDevUpdateConfig = true;
        }
    } else {
        autoUpdater.setFeedURL({
            provider: 'github',
            owner: 'RetroGameSets',
            repo: 'B2PC',
            vPrefixedTagName: true
        });
    }

    autoUpdater.checkForUpdates().catch(err => {
        console.error('Erreur lors de la vérification des mises à jour:', err);
    });

    autoUpdater.on('checking-for-update', () => {
        console.log('Vérification des mises à jour...');
    });

    autoUpdater.on('update-available', (info) => {
        dialog.showMessageBox(mainWindow, {
            type: 'info',
            title: 'Mise à jour disponible',
            message: `Une nouvelle version (${info.version}) est disponible. Voulez-vous la télécharger ?`,
            buttons: ['Oui', 'Non']
        }).then(result => {
            if (result.response === 0) autoUpdater.downloadUpdate();
        });
    });

    autoUpdater.on('update-downloaded', () => {
        dialog.showMessageBox(mainWindow, {
            type: 'info',
            title: 'Mise à jour prête',
            message: 'La mise à jour a été téléchargée. L’application va redémarrer pour l’installer.',
            buttons: ['Installer', 'Plus tard']
        }).then(result => {
            if (result.response === 0) autoUpdater.quitAndInstall();
        });
    });

    autoUpdater.on('error', (err) => {
        dialog.showErrorBox('Erreur de mise à jour', `Impossible de vérifier les mises à jour : ${err.message}`);
    });

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });


    //handlers 
    patchXboxIsoHandler(ipcMain, tools, sendLog, sendProgress, askCleanupConfirmation, mainWindow);
    convertToChdv5Handler(ipcMain, tools, sendLog, sendProgress, askCleanupConfirmation, mainWindow);
    extractChdHandler(ipcMain, tools, sendLog, sendProgress, askCleanupConfirmation, mainWindow);
    convertIsoToRvzHandler(ipcMain, tools, sendLog, sendProgress, askCleanupConfirmation, mainWindow);
    mergeBinCueHandler(ipcMain, tools, sendLog, sendProgress, askCleanupConfirmation, mainWindow);
    compressWsquashFSHandler(ipcMain, tools, sendLog, sendProgress, askCleanupConfirmation, mainWindow);
    extractWsquashFSHandler(ipcMain, tools, sendLog, sendProgress, askCleanupConfirmation, mainWindow);

});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
});