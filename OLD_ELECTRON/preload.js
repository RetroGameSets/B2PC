const { contextBridge, ipcRenderer } = require('electron');
const { dialog } = require('@electron/remote');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs').promises;

const logDir = `${process.env.APPDATA}\\B2PC\\LOG`;

const appPath = path.resolve(__dirname, 'package.json');
let appVersion;
try {
    const packageJson = require(appPath);
    appVersion = packageJson.version;
} catch (err) {
    console.error('Erreur lors du chargement de package.json:', err);
    appVersion = 'Version inconnue';
}

// Fonction utilitaire
async function validateDirsAndInvoke(channel, source, dest, ...args) {
    const exists = async p => await fs.access(p).then(() => true).catch(() => false);
    if (!await exists(source)) throw new Error(`Dossier source n'existe pas : ${source}`);
    if (!await exists(dest)) throw new Error(`Dossier destination n'existe pas : ${dest}`);
    return ipcRenderer.invoke(channel, source, dest, ...args);
}

contextBridge.exposeInMainWorld('electronAPI', {
    patchXboxIso: (source, dest) => validateDirsAndInvoke('patch-xbox-iso', source, dest),
    convertToChdv5: (source, dest) => validateDirsAndInvoke('convert-to-chdv5', source, dest),
    extractChd: (source, dest) => validateDirsAndInvoke('extract-chd', source, dest),
    convertIsoToRvz: (source, dest) => validateDirsAndInvoke('convert-iso-to-rvz', source, dest),
    mergeBinCue: (source, dest) => validateDirsAndInvoke('merge-bin-cue', source, dest),
    compressWsquashFS: (source, dest, compressionLevel) => validateDirsAndInvoke('compress-wsquashfs', source, dest, compressionLevel),
    extractWsquashFS: (source, dest) => validateDirsAndInvoke('extract-wsquashfs', source, dest),

    onLogMessage: (callback) => ipcRenderer.on('log-message', (_, msg) => callback(msg)),
    onProgressUpdate: (callback) => ipcRenderer.on('progress-update', (_, data) => callback(data)),

    writeLog: async (logFilePath, message) => {
        try {
            const logDir = path.dirname(logFilePath);
            await fs.mkdir(logDir, { recursive: true });
            await fs.appendFile(logFilePath, `${message}\n`, { flag: 'a+' });
        } catch (err) {
            console.error('Erreur écriture fichier log:', err);
            throw err;
        }
    },

    selectSourceFolder: async () => {
        try {
            const result = await dialog.showOpenDialog({ properties: ['openDirectory'] });
            return (!result.canceled && result.filePaths.length > 0) ? result.filePaths[0] : null;
        } catch (error) {
            console.error('Erreur sélection dossier source:', error);
            throw error;
        }
    },

    selectDestinationFolder: async () => {
        try {
            const result = await dialog.showOpenDialog({ properties: ['openDirectory'] });
            return (!result.canceled && result.filePaths.length > 0) ? result.filePaths[0] : null;
        } catch (error) {
            console.error('Erreur sélection dossier destination:', error);
            throw error;
        }
    },

    openLogFolder: async () => {
        try {
            await fs.access(logDir).catch(() => fs.mkdir(logDir, { recursive: true }));
            spawn('explorer.exe', [logDir], { detached: true, shell: true });
        } catch (err) {
            console.error('Erreur ouverture dossier LOG:', err);
            throw err;
        }
    },

    getLogDir: () => logDir,
    getAppVersion: () => appVersion
});

// Confirmation de suppression
ipcRenderer.on('request-cleanup-confirmation', (event, cleanupChannel) => {
    dialog.showMessageBox({
        type: 'question',
        buttons: ['Oui', 'Non'],
        defaultId: 1,
        title: 'Confirmation de suppression',
        message: 'Voulez-vous supprimer les fichiers source après la conversion ?',
        detail: 'Les fichiers dans le dossier source seront supprimés si vous choisissez "Oui".'
    }).then((response) => {
        const shouldDelete = response.response === 0;
        ipcRenderer.send(cleanupChannel, shouldDelete);
    });
});

console.log('preload.js: electronAPI exposé');
