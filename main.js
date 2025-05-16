const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const { autoUpdater } = require('electron-updater');
const path = require('path');
const fs = require('fs');
const fsPromises = require('fs').promises;
const { spawn } = require('child_process');
const seven = require('node-7z');
const { enable, initialize } = require('@electron/remote/main');

// Activer le logger pour electron-updater
autoUpdater.logger = require('electron-log');
autoUpdater.logger.transports.file.level = 'info';

initialize();
let mainWindow;

// Ajuster le chemin des ressources en fonction du contexte (packagé ou dev)
const isPackaged = app.isPackaged;
const resourcesPath = isPackaged
    ? path.join(process.resourcesPath, '..', 'ressources')
    : path.join(__dirname, 'ressources');

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1024,
        height: 720,
        resizable: true,
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false,
            sandbox: false
        }
    });

    enable(mainWindow.webContents);
    mainWindow.loadFile('index.html');
    mainWindow.setMenu(null);
   //mainWindow.webContents.openDevTools();
	
    // Vérification des chemins
    const imagesPath = path.join(__dirname, 'ressources', 'images');
    if (!fs.existsSync(resourcesPath)) {
        sendLog(`Erreur : Dossier ressources non trouvé à ${resourcesPath}`);
    } else {
        sendLog(`Dossier ressources trouvé à ${resourcesPath}`);
    }
    if (!fs.existsSync(imagesPath)) {
        sendLog(`Erreur : Dossier images non trouvé à ${imagesPath}`);
    } else {
        sendLog(`Dossier images trouvé à ${imagesPath}`);
    }
}

app.whenReady().then(() => {
    createWindow();

    // Configurer electron-updater
    if (process.env.NODE_ENV === 'development') {
        const devUpdatePath = path.join(__dirname, 'dev-app-update.yml');
        console.log('Mode développement : __dirname =', __dirname);
        console.log('Mode développement : tentative de chargement de', devUpdatePath);
        if (fs.existsSync(devUpdatePath)) {
            autoUpdater.updateConfigPath = devUpdatePath;
            autoUpdater.forceDevUpdateConfig = true;
            console.log('Mode développement : utilisation de dev-app-update.yml');
        } else {
            console.error('Mode développement : dev-app-update.yml non trouvé à', devUpdatePath);
        }
    } else {
        autoUpdater.setFeedURL({
            provider: 'github',
            owner: 'RetroGameSets',
            repo: 'B2PC',
            vPrefixedTagName: true
        });
        console.log('Mode production : configuration GitHub pour les mises à jour');
    }

    autoUpdater.checkForUpdates().catch(err => {
        console.error('Erreur lors de la vérification des mises à jour:', err);
    });

    autoUpdater.on('checking-for-update', () => {
        console.log('Vérification des mises à jour...');
    });

    autoUpdater.on('update-available', (info) => {
        console.log(`Mise à jour disponible : version ${info.version}`);
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
        console.log('Mise à jour téléchargée');
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
        console.error('Erreur de mise à jour:', err);
        dialog.showErrorBox('Erreur de mise à jour', `Impossible de vérifier les mises à jour : ${err.message}`);
    });

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
});

function sendLog(msg) {
    if (mainWindow && msg) {
        const timestamp = new Date().toLocaleTimeString('fr-FR', { hour12: false });
        const logMessage = `${timestamp} - ${msg}`;
        console.log('Envoi log:', logMessage); // Débogage
        mainWindow.webContents.send('log-message', logMessage);
    } else {
        console.error('Erreur sendLog: mainWindow ou msg non défini');
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
		
        await fsPromises.mkdir(destination, { recursive: true });
        sendLog(`Dossier destination créé ou existant: ${destination}`);
		const sevenZipPath = path.join(resourcesPath, '7za.exe');
		
        if (!fs.existsSync(sevenZipPath)) {
            sendLog(`Erreur : 7za.exe non trouvé à ${sevenZipPath}`);
            throw new Error(`7za.exe non trouvé à ${sevenZipPath}`);
        }
        sendLog(`Utilisation de 7za.exe à ${sevenZipPath}`);
        const archiveExtensions = ['.7z', '.zip', '.gz', '.rar'];
        const sourceFiles = await fsPromises.readdir(source, { recursive: true });
        const archives = sourceFiles.filter(f => archiveExtensions.includes(path.extname(f).toLowerCase()));
        const sourceIsos = sourceFiles.filter(f => path.extname(f).toLowerCase() === '.iso');

        sendLog(`Archives détectées : ${archives.length}`);
        sendLog(`ISOs détectés : ${sourceIsos.length}`);

        const validArchives = [];

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

        const archivesToExtract = [];
        const skippedArchives = [];
        for (const file of validArchives) {
            const baseName = path.basename(file, path.extname(file));
            const isoPath = path.join(destination, `${baseName}.iso`);
            if (await fsPromises.access(isoPath).then(() => true).catch(() => false)) {
                skippedGames++;
                sendLog(`${baseName}.iso existe déjà dans ${destination}, extraction ignorée.`);
                skippedArchives.push(baseName);
            } else {
                archivesToExtract.push(file);
            }
        }

        for (let i = 0; i < archivesToExtract.length; i++) {
            const file = archivesToExtract[i];
            const fullPath = path.join(source, file);
            sendLog(`Extraction de ${file}...`);

            const percent = ((i + 1) / archivesToExtract.length) * 100;
            sendProgress(percent, `Extraction de ${file}`, i + 1, archivesToExtract.length);

            await new Promise((resolve, reject) => {
                seven.extractFull(fullPath, source, { $bin: sevenZipPath })
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

        const sourceFilesAfterExtract = await fsPromises.readdir(source, { recursive: true });
        const allIsos = sourceFilesAfterExtract.filter(f => path.extname(f).toLowerCase() === '.iso').map(f => path.join(source, f));

        const isosToConvert = [];
        for (const iso of allIsos) {
            const fileName = path.basename(iso, '.iso');
            const isoPath = path.join(destination, `${fileName}.iso`);
            if (skippedArchives.includes(fileName)) {
                sendLog(`${fileName}.iso correspond à une archive ignorée, conversion ignorée.`);
            } else if (await fsPromises.access(isoPath).then(() => true).catch(() => false)) {
                skippedGames++;
                sendLog(`${fileName}.iso existe déjà dans ${destination}, conversion ignorée.`);
            } else {
                isosToConvert.push(iso);
            }
        }

        const xisoSource = path.join(resourcesPath, 'xiso.exe');
        const xisoDest = path.join(destination, 'xiso.exe');
        await fsPromises.copyFile(xisoSource, xisoDest);

        for (let i = 0; i < isosToConvert.length; i++) {
            const iso = isosToConvert[i];
            const fileName = path.basename(iso, '.iso');
            sendLog(`Conversion de ${fileName}...`);

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
                        const isoOldPath = `${iso}.old`;
                        fsPromises.unlink(isoOldPath).catch(err => {
                            sendLog(`Erreur lors de la suppression de ${isoOldPath}: ${err.message}`);
                        });
                        fsPromises.unlink(iso).catch(err => {
                            sendLog(`Erreur lors de la suppression de ${iso}: ${err.message}`);
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

        await fsPromises.unlink(xisoDest).catch(() => {});

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

ipcMain.handle('convert-to-chdv5', async (_, source, dest) => {
    const startTime = Date.now();
    const destination = dest.endsWith('\\') ? dest + 'CHD' : dest + '\\CHD';
    let convertedGames = 0;
    let skippedGames = 0;
    let ignoredArchives = 0;
    let errorCount = 0;

    try {
        sendLog('Début de la conversion en CHDv5...');
        sendLog(`Dossier source: ${source}`);
        sendLog(`Dossier destination: ${destination}`);
		const sevenZipPath = path.join(resourcesPath, '7za.exe');
        if (!fs.existsSync(sevenZipPath)) {
            sendLog(`Erreur : 7za.exe non trouvé à ${sevenZipPath}`);
            throw new Error(`7za.exe non trouvé à ${sevenZipPath}`);
        }
        sendLog(`Utilisation de 7za.exe à ${sevenZipPath}`);
        await fsPromises.mkdir(destination, { recursive: true });
        sendLog(`Dossier destination créé ou existant: ${destination}`);

        const archiveExtensions = ['.7z', '.zip', '.gz', '.rar'];
        const inputExtensions = ['.iso', '.cue', '.gdi'];
        const sourceFiles = await fsPromises.readdir(source, { recursive: true });
        const archives = sourceFiles.filter(f => archiveExtensions.includes(path.extname(f).toLowerCase()));
        const sourceInputs = sourceFiles.filter(f => inputExtensions.includes(path.extname(f).toLowerCase()));

        sendLog(`Archives détectées : ${archives.length}`);
        sendLog(`Fichiers d'entrée détectés : ${sourceInputs.length}`);

        const validArchives = [];

        for (let i = 0; i < archives.length; i++) {
            const file = archives[i];
            const fullPath = path.join(source, file);
            sendLog(`Vérification de ${file}...`);
            let foundValidFile = false;
            await new Promise((resolve) => {
                const child = spawn(sevenZipPath, ['l', fullPath]);
                let output = '';
                child.stdout.on('data', data => output += data.toString('utf8'));
                child.on('close', () => {
                    sendLog(`Contenu de ${file} :\n${output}`);
                    const lines = output.split(/\r?\n/);
                    for (const line of lines) {
                        if (/\.(iso|cue|gdi|bin)$/i.test(line)) {
                            foundValidFile = true;
                            validArchives.push(file);
                            break;
                        }
                    }
                    if (!foundValidFile) {
                        ignoredArchives++;
                        sendLog(`Pas de fichier .iso/.cue/.gdi/.bin dans ${file}, ignoré.`);
                    }
                    const percent = ((i + 1) / archives.length) * 100;
                    sendProgress(percent, `Vérification de ${file}`, i + 1, archives.length);
                    resolve();
                });
            });
        }

        sendLog(`Archives valides : ${validArchives.length}`);

        const archivesToExtract = [];
        const skippedArchives = [];
        for (const file of validArchives) {
            const baseName = path.basename(file, path.extname(file));
            const outputPath = path.join(destination, `${baseName}.chd`);
            if (await fsPromises.access(outputPath).then(() => true).catch(() => false)) {
                skippedGames++;
                sendLog(`${baseName}.chd existe déjà dans ${destination}, extraction ignorée.`);
                skippedArchives.push(baseName);
            } else {
                archivesToExtract.push(file);
            }
        }

        for (let i = 0; i < archivesToExtract.length; i++) {
            const file = archivesToExtract[i];
            const fullPath = path.join(source, file);
            sendLog(`Extraction de ${file}...`);

            const percent = ((i + 1) / archivesToExtract.length) * 100;
            sendProgress(percent, `Extraction de ${file}`, i + 1, archivesToExtract.length);

            await new Promise((resolve, reject) => {
                seven.extractFull(fullPath, source, { $bin: sevenZipPath })
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

        const sourceFilesAfterExtract = await fsPromises.readdir(source, { recursive: true });
        const allInputs = sourceFilesAfterExtract.filter(f => inputExtensions.includes(path.extname(f).toLowerCase())).map(f => path.join(source, f));

        const inputsToConvert = [];
        for (const input of allInputs) {
            const fileName = path.basename(input, path.extname(input));
            const outputPath = path.join(destination, `${fileName}.chd`);
            if (skippedArchives.includes(fileName)) {
                sendLog(`${fileName}.chd correspond à une archive ignorée, conversion ignorée.`);
            } else if (await fsPromises.access(outputPath).then(() => true).catch(() => false)) {
                skippedGames++;
                sendLog(`${fileName}.chd existe déjà dans ${destination}, conversion ignorée.`);
            } else {
                inputsToConvert.push(input);
            }
        }

        const chdmanPath = path.join(__dirname, 'ressources', 'chdman.exe');

        for (let i = 0; i < inputsToConvert.length; i++) {
            const file = inputsToConvert[i];
            const inputPath = file;
            const baseName = path.basename(file, path.extname(file));
            const outputPath = path.join(destination, `${baseName}.chd`);

            sendLog(`Conversion de ${baseName}...`);
            const percent = ((i + 1) / inputsToConvert.length) * 100;
            sendProgress(percent, `Conversion de ${baseName}`, i + 1, inputsToConvert.length);

            let lastLine = '';
            await new Promise((resolve, reject) => {
                const child = spawn(chdmanPath, ['createcd', '-i', inputPath, '-o', outputPath]);
                child.stdout.on('data', data => {
                    const lines = data.toString().split('\n').filter(Boolean);
                    for (const line of lines) {
                        if (line.includes('Compression complete')) {
                            lastLine = line;
                        }
                    }
                });
                child.stderr.on('data', data => {
                    const lines = data.toString().split('\n').filter(Boolean);
                    for (const line of lines) {
                        if (line.toLowerCase().includes('error') || line.toLowerCase().includes('failed')) {
                            sendLog(`chdman [${baseName}] Erreur: ${line}`);
                        }
                    }
                });
                child.on('close', code => {
                    if (code === 0) {
                        convertedGames++;
                        if (lastLine) {
                            sendLog(`chdman [${baseName}]: ${lastLine}`);
                        }
                        sendLog(`Conversion de ${baseName} OK`);
                        const inputExt = path.extname(inputPath).toLowerCase();
                        if (inputExt === '.cue' || inputExt === '.gdi') {
                            const cueContent = fsPromises.readFileSync(inputPath, 'utf8');
                            const binFiles = cueContent.match(/FILE\s+"([^"]+\.bin)"/gi) || [];
                            for (const bin of binFiles) {
                                const binPath = path.join(path.dirname(inputPath), bin.match(/"([^"]+\.bin)"/)[1]);
                                fsPromises.unlink(binPath).catch(err => {
                                    sendLog(`Erreur lors de la suppression de ${binPath}: ${err.message}`);
                                });
                            }
                            fsPromises.unlink(inputPath).catch(err => {
                                sendLog(`Erreur lors de la suppression de ${inputPath}: ${err.message}`);
                            });
                        } else if (inputExt === '.iso') {
                            fsPromises.unlink(inputPath).catch(err => {
                                sendLog(`Erreur lors de la suppression de ${inputPath}: ${err.message}`);
                            });
                        }
                        resolve();
                    } else {
                        errorCount++;
                        sendLog(`Échec conversion ${baseName}, code ${code}`);
                        reject(new Error(`Échec conversion ${baseName}, code ${code}`));
                    }
                });
            });
        }

        const durationMs = Date.now() - startTime;
        sendLog('Résumé :');
        sendLog(`- Jeux convertis : ${convertedGames}`);
        sendLog(`- Jeux ignorés (déjà convertis) : ${skippedGames}`);
        sendLog(`- Archives ignorées (sans fichier valide) : ${ignoredArchives}`);
        sendLog(`- Erreurs : ${errorCount}`);
        sendLog(`- Temps total : ${(durationMs / 60000).toFixed(1)}m`);

        return {
            summary: { convertedGames, skippedGames, ignoredArchives, errorCount, duration: durationMs }
        };

    } catch (error) {
        errorCount++;
        sendLog(`Erreur globale: ${error.message}`);
        throw error;
    }
});