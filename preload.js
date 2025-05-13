const { contextBridge, ipcRenderer } = require('electron');
const { dialog } = require('@electron/remote');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs').promises;

contextBridge.exposeInMainWorld('electronAPI', {
    // Fonctions principales
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
    onLogMessage: (callback) => ipcRenderer.on('log-message', (_, msg) => callback(msg)),
    onProgressUpdate: (callback) => ipcRenderer.on('progress-update', (_, data) => callback(data)),

    // Écriture dans le fichier de log
    writeLog: async (logFilePath, message) => {
        try {
            const logDir = path.dirname(logFilePath);
            await fs.mkdir(logDir, { recursive: true });
            await fs.appendFile(logFilePath, `${message}\n`);
        } catch (err) {
            console.error('Erreur écriture fichier log:', err);
            throw err;
        }
    },

    // Dossiers
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
            const logDir = path.join(__dirname, 'LOG');
            spawn('explorer.exe', [logDir], { detached: true });
        } catch (err) {
            console.error('Erreur ouverture dossier LOG:', err);
            throw err;
        }
    },

    // Exécution de script batch (gardé pour compatibilité future)
    runCommand: async (script, source, destination, message = '') => {
        if (!source || !destination) {
            throw new Error('Veuillez sélectionner les dossiers source et destination.');
        }
        if (message) alert(message);

        return new Promise((resolve, reject) => {
            const child = spawn('cmd', ['/c', `ressources\\${script}`, `"${source}"`, `"${destination}"`]);
            child.on('error', (error) => reject(error));
            child.on('close', (code) => {
                (code !== 0) ? reject(new Error(`Code de sortie ${code}`)) : resolve();
            });
        });
    },

    // Autres conversions simples (à convertir en JavaScript ultérieurement)
    convertToPbp: async (source, destination) =>
        await module.exports.runCommand('pbp_eboot.bat', source, destination, 'Attention, il se peut que certaines pistes audio soient perdues pendant la conversion'),

    mergeBinCue: async (source, destination) =>
        await module.exports.runCommand('merge_bin.bat', source, destination, 'Cette fonction rassemblera tous les .bin/.cue en un seul fichier'),

    extractChdToBin: async (source, destination) =>
        await module.exports.runCommand('chd_extract.bat', source, destination, 'Extraction de CHD vers bin/cue - résultats non garantis'),

    convertWiiToWbfs: async (source, destination) =>
        await module.exports.runCommand('wii_wbfs.bat', source, destination, 'Conversion WII ISO vers WBFS'),

    zipAllRoms: async (source, destination) =>
        await module.exports.runCommand('zip.bat', source, destination, 'Compression des jeux en ZIP individuels'),

    runUpdate: async () => {
        return new Promise((resolve, reject) => {
            const child = spawn('cmd', ['/c', 'update.bat']);
            child.on('error', reject);
            child.on('close', (code) => (code !== 0) ? reject(new Error(`Code de sortie ${code}`)) : resolve());
        });
    }
});

console.log('preload.js: electronAPI exposé');