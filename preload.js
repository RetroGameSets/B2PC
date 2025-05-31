const { contextBridge, ipcRenderer } = require('electron');
const { dialog } = require('@electron/remote');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs').promises;

const logDir = `${process.env.APPDATA}\\B2PC\\LOG`; // Défini dans preload.js

// Charger package.json avec un chemin absolu basé sur __dirname
const appPath = path.resolve(__dirname, 'package.json');
let appVersion;
try {
    const packageJson = require(appPath);
    appVersion = packageJson.version;
} catch (err) {
    console.error('Erreur lors du chargement de package.json:', err);
    appVersion = 'Version inconnue'; // Valeur par défaut en cas d'erreur
}

contextBridge.exposeInMainWorld('electronAPI', {
    patchXboxIso: async (source, dest) => {
        if (!await fs.access(source).then(() => true).catch(() => false)) {
            throw new Error(`Dossier source n'existe pas : ${source}`);
        }
        if (!await fs.access(dest).then(() => true).catch(() => false)) {
            throw new Error(`Dossier destination n'existe pas : ${dest}`);
        }
        return ipcRenderer.invoke('patch-xbox-iso', source, dest);
    },
    convertToChdv5: async (source, dest) => {
        if (!await fs.access(source).then(() => true).catch(() => false)) {
            throw new Error(`Dossier source n'existe pas : ${source}`);
        }
        if (!await fs.access(dest).then(() => true).catch(() => false)) {
            throw new Error(`Dossier destination n'existe pas : ${dest}`);
        }
        return ipcRenderer.invoke('convert-to-chdv5', source, dest);
    },
    extractChd: async (source, dest) => {
        if (!await fs.access(source).then(() => true).catch(() => false)) {
            throw new Error(`Dossier source n'existe pas : ${source}`);
        }
        if (!await fs.access(dest).then(() => true).catch(() => false)) {
            throw new Error(`Dossier destination n'existe pas : ${dest}`);
        }
        return ipcRenderer.invoke('extract-chd', source, dest);
    },
    convertIsoToRvz: async (source, dest) => {
        if (!await fs.access(source).then(() => true).catch(() => false)) {
            throw new Error(`Dossier source n'existe pas : ${source}`);
        }
        if (!await fs.access(dest).then(() => true).catch(() => false)) {
            throw new Error(`Dossier destination n'existe pas : ${dest}`);
        }
        return ipcRenderer.invoke('convert-iso-to-rvz', source, dest);
    },
    mergeBinCue: async (source, dest) => {
        if (!await fs.access(source).then(() => true).catch(() => false)) {
            throw new Error(`Dossier source n'existe pas : ${source}`);
        }
        if (!await fs.access(dest).then(() => true).catch(() => false)) {
            throw new Error(`Dossier destination n'existe pas : ${dest}`);
        }
        return ipcRenderer.invoke('merge-bin-cue', source, dest);
    },
    compressWsquashFS: async (source, dest, compressionLevel) => {
        if (!await fs.access(source).then(() => true).catch(() => false)) {
            throw new Error(`Dossier source n'existe pas : ${source}`);
        }
        if (!await fs.access(dest).then(() => true).catch(() => false)) {
            throw new Error(`Dossier destination n'existe pas : ${dest}`);
        }
        return ipcRenderer.invoke('compress-wsquashfs', source, dest, compressionLevel);
    },
    extractWsquashFS: async (source, dest) => {
        if (!await fs.access(source).then(() => true).catch(() => false)) {
            throw new Error(`Dossier source n'existe pas : ${source}`);
        }
        if (!await fs.access(dest).then(() => true).catch(() => false)) {
            throw new Error(`Dossier destination n'existe pas : ${dest}`);
        }
        return ipcRenderer.invoke('extract-wsquashfs', source, dest);
    },

    onLogMessage: (callback) => ipcRenderer.on('log-message', (_, msg) => callback(msg)),
    onProgressUpdate: (callback) => ipcRenderer.on('progress-update', (_, data) => callback(data)),

    writeLog: async (logFilePath, message) => {
        try {
            const logDir = path.dirname(logFilePath);
            await fs.mkdir(logDir, { recursive: true }); // Créer le dossier s'il n'existe pas
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

    runCommand: async (script, source, destination, message = '') => {
        if (!source || !destination) {
            throw new Error('Veuillez sélectionner les dossiers source et destination.');
        }
        if (message) alert(message);

        return new Promise((resolve, reject) => {
            const child = spawn('cmd', ['/c', `ressources\\${script}`, `"${source}"`, `"${destination}"`]);
            child.on('error', (error) => reject(error));
            child.on('close', (code) => (code !== 0) ? reject(new Error(`Code de sortie ${code}`)) : resolve());
        });
    },

    getLogDir: () => logDir, // Exposer logDir

    getAppVersion: () => appVersion // Exposer la version de l'application
});

// Gérer la confirmation de nettoyage dans preload.js
ipcRenderer.on('request-cleanup-confirmation', (event, cleanupChannel) => {
    dialog.showMessageBox({
        type: 'question',
        buttons: ['Oui', 'Non'],
        defaultId: 1, // "Non" par défaut
        title: 'Confirmation de suppression',
        message: 'Voulez-vous supprimer les fichiers source après la conversion ?',
        detail: 'Les fichiers .iso, .cue, .bin, .gdi, .chd dans le dossier source seront supprimés si vous choisissez "Oui".'
    }).then((response) => {
        const shouldDelete = response.response === 0;
        ipcRenderer.send(cleanupChannel, shouldDelete);
    });
});
console.log('preload.js: electronAPI exposé');