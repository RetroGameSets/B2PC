const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs').promises;
const { spawn } = require('child_process');
const seven = require('node-7z');
const { enable, initialize } = require('@electron/remote/main');

initialize();
let mainWindow;

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1000,
        height: 700,
        resizable: false,
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false,
            sandbox: false
        }
    });

    enable(mainWindow.webContents);
    mainWindow.loadFile('index.html');
    mainWindow.webContents.openDevTools();
}

app.whenReady().then(() => {
    createWindow();
    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
});

function sendLog(msg) {
    if (mainWindow) {
        const timestamp = new Date().toLocaleTimeString('fr-FR', { hour12: false });
        mainWindow.webContents.send('log-message', `${timestamp} - ${msg}`);
    }
}

function sendProgress(percent, message, current, total) {
    if (mainWindow) {
        console.log(`Envoi progression: ${percent}% - ${message} (${current}/${total})`);
        mainWindow.webContents.send('progress-update', { percent, message, current, total });
    }
}

ipcMain.handle('patch-xbox-iso', async (_, source, dest) => {
    const startTime = Date.now();
    const destination = dest.endsWith('\\') ? dest + 'xbox' : dest + '\\xbox';
    let convertedGames = 0;
    let optimizedGames = 0;
    let ignoredArchives = 0;
    let skippedGames = 0;
    let errorCount = 0;

    try {
        sendLog('Début du patch Xbox...');
        sendLog(`Dossier source: ${source}`);
        sendLog(`Dossier destination: ${destination}`);

        const archiveExtensions = ['.7z', '.zip', '.gz', '.rar'];
        const sourceFiles = await fs.readdir(source, { recursive: true });
        const archives = sourceFiles.filter(f => archiveExtensions.includes(path.extname(f).toLowerCase()));
        const sourceIsos = sourceFiles.filter(f => path.extname(f).toLowerCase() === '.iso');

        sendLog(`Archives détectées : ${archives.length}`);
        sendLog(`ISOs détectés : ${sourceIsos.length}`);

        // Étape 1 : Vérification des archives
        const validArchives = [];
        const sevenZipPath = path.join(__dirname, 'ressources', '7za.exe');

        for (let i = 0; i < archives.length; i++) {
            const file = archives[i];
            const fullPath = path.join(source, file);
            sendLog(`Vérification de ${file}...`);
            let foundIso = false;
            await new Promise((resolve) => {
                const child = spawn(sevenZipPath, ['l', fullPath]);
                let output = '';
                child.stdout.on('data', data => output += data.toString('utf8'));
                child.on('close', () => {
                    sendLog(`Contenu de ${file} :\n${output}`);
                    const lines = output.split(/\r?\n/);
                    for (const line of lines) {
                        if (/\.iso$/i.test(line)) {
                            foundIso = true;
                            validArchives.push(file);
                            break;
                        }
                    }
                    if (!foundIso) {
                        ignoredArchives++;
                        sendLog(`Pas d'ISO dans ${file}, ignoré.`);
                    }
                    const percent = ((i + 1) / archives.length) * 100;
                    sendProgress(percent, `Vérification de ${file}`, i + 1, archives.length);
                    resolve();
                });
            });
        }

        sendLog(`Archives valides : ${validArchives.length}`);

        // Étape 2 : Extraction des archives valides
        const archivesToExtract = [];
        const skippedArchives = []; // Garder une trace des archives ignorées
        for (const file of validArchives) {
            const baseName = path.basename(file, path.extname(file));
            const isoPath = path.join(destination, `${baseName}.iso`);
            if (await fs.access(isoPath).then(() => true).catch(() => false)) {
                skippedGames++;
                sendLog(`${baseName}.iso existe déjà dans ${destination}, extraction ignorée.`);
                skippedArchives.push(baseName); // Ajouter le nom de base à la liste des ignorés
            } else {
                archivesToExtract.push(file);
            }
        }

        for (let i = 0; i < archivesToExtract.length; i++) {
            const file = archivesToExtract[i];
            const fullPath = path.join(source, file);
            sendLog(`Extraction de ${file}...`);

            // Envoyer la progression AVANT de commencer l'extraction
            const percent = ((i + 1) / archivesToExtract.length) * 100;
            sendProgress(percent, `Extraction de ${file}`, i + 1, archivesToExtract.length);

            await new Promise((resolve, reject) => {
                seven.extractFull(fullPath, destination, { $bin: sevenZipPath })
                    .on('end', () => {
                        sendLog(`${file} extrait.`);
                        resolve();
                    })
                    .on('error', err => {
                        sendLog(`Erreur extraction ${file}: ${err.message}`);
                        errorCount++;
                        reject();
                    });
            });
        }

        // Étape 3 : Conversion des ISOs
        const destFiles = await fs.readdir(destination, { recursive: true });
        const destIsos = destFiles.filter(f => path.extname(f).toLowerCase() === '.iso');
        const allIsos = [...sourceIsos.map(f => path.join(source, f)), ...destIsos.map(f => path.join(destination, f))];

        const isosToConvert = [];
        for (const iso of allIsos) {
            const fileName = path.basename(iso, '.iso');
            const isoPath = path.join(destination, `${fileName}.iso`);
            if (skippedArchives.includes(fileName)) {
                sendLog(`${fileName}.iso correspond à une archive ignorée, conversion ignorée.`);
            } else if (await fs.access(isoPath).then(() => true).catch(() => false) && iso !== isoPath) {
                skippedGames++;
                sendLog(`${fileName}.iso existe déjà dans ${destination}, conversion ignorée.`);
            } else {
                isosToConvert.push(iso);
            }
        }

        const xisoSource = path.join(__dirname, 'ressources', 'xiso.exe');
        const xisoDest = path.join(destination, 'xiso.exe');
        await fs.copyFile(xisoSource, xisoDest);

        for (let i = 0; i < isosToConvert.length; i++) {
            const iso = isosToConvert[i];
            const fileName = path.basename(iso, '.iso');
            sendLog(`Conversion de ${fileName}...`);

            // Envoyer la progression AVANT de commencer la conversion
            const percent = ((i + 1) / isosToConvert.length) * 100;
            sendProgress(percent, `Conversion de ${fileName}`, i + 1, isosToConvert.length);

            let hasError = false;
            let errorMessage = '';

            await new Promise((resolve) => {
                const child = spawn(xisoDest, ['-r', iso], { cwd: destination });
                child.stdout.on('data', data => {
                    const lines = data.toString().split('\n').filter(Boolean);
                    for (const line of lines) sendLog(`xiso.exe [${fileName}]: ${line}`);
                });
                child.stderr.on('data', data => {
                    const lines = data.toString().split('\n').filter(Boolean);
                    for (const line of lines) {
                        sendLog(`xiso.exe [${fileName}] Erreur: ${line}`);
                        if (line.includes('cannot rewrite')) {
                            hasError = true;
                            errorMessage = line;
                        }
                    }
                });
                child.on('close', code => {
                    if (code === 0 && !hasError) {
                        convertedGames++;
                        sendLog(`Conversion de ${fileName} OK`);
                        // Supprimer le fichier .iso.old après une conversion réussie
                        const isoOldPath = `${iso}.old`;
                        fs.unlink(isoOldPath).catch(err => {
                            sendLog(`Erreur lors de la suppression de ${isoOldPath}: ${err.message}`);
                        });
                    } else {
                        errorCount++;
                        const errorMsg = hasError ? errorMessage : `Échec conversion ${fileName}, code ${code}`;
                        sendLog(errorMsg);
                    }
                    resolve();
                });
            });
        }

        await fs.unlink(xisoDest).catch(() => {});

        const durationMs = Date.now() - startTime;
        sendLog('Résumé :');
        sendLog(`- Jeux convertis : ${convertedGames}`);
        sendLog(`- Jeux ignorés (déjà convertis) : ${skippedGames}`);
        sendLog(`- Archives ignorées (sans ISO) : ${ignoredArchives}`);
        sendLog(`- Erreurs : ${errorCount}`);
        sendLog(`- Temps total : ${(durationMs / 60000).toFixed(1)}m`);

        return {
            summary: { convertedGames, optimizedGames, ignoredArchives, skippedGames, errorCount, duration: durationMs }
        };

    } catch (error) {
        errorCount++;
        sendLog(`Erreur globale: ${error.message}`);
        throw error;
    }
});