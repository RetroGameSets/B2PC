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
    ? path.join(path.dirname(process.resourcesPath), 'ressources')
    : path.join(__dirname, 'ressources');

const tools = {
    sevenZip: path.join(resourcesPath, '7za.exe'),
    xiso: path.join(resourcesPath, 'xiso.exe'),
    chdman: path.join(resourcesPath, 'chdman.exe'), 
    dolphinTool: path.join(resourcesPath, 'dolphin-tool.exe')
};

async function validateTools() {
    for (const [name, path] of Object.entries(tools)) {
        if (!fs.existsSync(path)) {
            sendLog(`Erreur : ${name} non trouvé à ${path}`);
            throw new Error(`${name} non trouvé à ${path}`);
        }
        //sendLog(`Utilisation de ${name} à ${path}`);
    }
}

async function extractArchives(sourceDir, sevenZipPath, extensions = ['.7z', '.zip', '.gz', '.rar'], targetExtensions = ['.cue', '.bin', '.gdi', '.iso']) {
    const sourceFiles = [];
    const walkDir = async (dir) => {
        const files = await fsPromises.readdir(dir, { withFileTypes: true });
        for (const file of files) {
            const fullPath = path.join(dir, file.name);
            if (file.isDirectory()) {
                await walkDir(fullPath);
            } else {
                sourceFiles.push({ name: file.name, fullPath });
            }
        }
    };
    await walkDir(sourceDir);

    const archives = sourceFiles.filter(f => extensions.includes(path.extname(f.name).toLowerCase()));
    const validArchives = [];

    for (let i = 0; i < archives.length; i++) {
        const file = archives[i];
        const fullPath = file.fullPath;
        sendLog(`Vérification de ${file.name}...`);
        sendProgress((i / archives.length) * 10, `Analyse des archives`, i + 1, archives.length);
        const filesInside = await new Promise((resolve, reject) => {
            const filesList = [];
            seven.list(fullPath, { $bin: sevenZipPath })
                .on('data', file => filesList.push(file.file))
                .on('end', () => resolve(filesList))
                .on('error', reject);
        });

        const targetFiles = filesInside.filter(f => targetExtensions.some(ext => f.toLowerCase().endsWith(ext)));
        if (targetFiles.length > 0) {
            // Inclure les fichiers .bin associés aux .cue
            const associatedFiles = [];
            for (const target of targetFiles) {
                associatedFiles.push(target);
                if (target.toLowerCase().endsWith('.cue')) {
                    const baseName = path.basename(target, '.cue');
                    const binFile = filesInside.find(f => f.toLowerCase() === `${baseName}.bin` || f.toLowerCase() === `${baseName.toLowerCase()}.bin`);
                    if (binFile) associatedFiles.push(binFile);
                }
            }
            validArchives.push({ file: file.name, fullPath, targets: associatedFiles });
        } else {
            sendLog(`Archive ignorée (pas de fichiers cibles) : ${file.name}`);
        }
    }

    sendProgress(10, `Extraction des archives`);
    for (let i = 0; i < validArchives.length; i++) {
        const { file, fullPath, targets } = validArchives[i];
        sendLog(`Extraction de ${file}...`);
        sendProgress(10 + (i / validArchives.length) * 20, `Extraction des archives`, i + 1, validArchives.length);
        await extractWith7z(fullPath, sourceDir, targets, sevenZipPath);
        sendLog(`Extraction terminée : ${file}`);
    }

    // Rafraîchir la liste des fichiers après extraction
    sourceFiles.length = 0; // Vider la liste précédente
    await walkDir(sourceDir);
    return sourceFiles.filter(f => targetExtensions.includes(path.extname(f.name).toLowerCase()));
}

async function extractWith7z(archivePath, destination, filesToExtract, sevenZipPath) {
    return new Promise((resolve, reject) => {
        const outputArg = `-o${destination}`;
        const args = ['x', archivePath, '-y', outputArg, ...filesToExtract];
        //sendLog(`Exécution de 7za.exe ${args.join(' ')}`);
        const extraction = spawn(sevenZipPath, args, { cwd: destination });

        let errorOutput = '';
        extraction.stdout.on('data', data => sendLog(`7za stdout: ${data}`));
        extraction.stderr.on('data', data => {
            errorOutput += data;
            sendLog(`7za stderr: ${data}`);
        });
        extraction.on('close', code => {
            if (code === 0) {
                sendLog(`Extraction terminée : ${archivePath} -> ${destination}`);
                resolve();
            } else {
                sendLog(`Erreur lors de l'extraction de ${archivePath}: code ${code}`);
                reject(new Error(errorOutput));
            }
        });
        extraction.on('error', err => reject(err));
    });
}

async function prepareDirectories(dest, subFolder) {
    const destination = dest.endsWith('\\') ? dest + subFolder : dest + '\\' + subFolder;
    await fsPromises.mkdir(destination, { recursive: true });
    sendLog(`Dossier destination créé ou existant: ${destination}`);
    return destination;
}

async function cleanupFiles(sourceDir, extensionsToRemove) {
    sendLog('Nettoyage des fichiers extraits...');
    sendProgress(80, `Nettoyage`);
    const files = await fsPromises.readdir(sourceDir);
    for (const file of files) {
        if (extensionsToRemove.includes(path.extname(file).toLowerCase())) {
            const fullPath = path.join(sourceDir, file);
            await fsPromises.unlink(fullPath).catch(err => sendLog(`Erreur lors de la suppression de ${fullPath}: ${err.message}`));
        }
    }
}

async function runTool(toolPath, args, workingDir, fileName, totalFiles, fileIndex, operation) {
    return new Promise((resolve, reject) => {
       // sendLog(`Exécution de ${path.basename(toolPath)} ${args.join(' ')}`);
        const tool = spawn(toolPath, args, { cwd: workingDir });
        let stdoutOutput = '';
        let errorOutput = '';
        let hasCriticalError = false;

        const timeout = setTimeout(() => {
            tool.kill();
            reject(new Error(`Timeout: ${path.basename(toolPath)} n'a pas répondu après 5 minutes`));
        }, 300000); // 5 minutes

        tool.stdout.on('data', data => {
            const lines = data.toString().split('\n').filter(Boolean);
            for (const line of lines) {
                stdoutOutput += line + '\n';
                if (line.includes('successfully rewritten')) {
                    sendLog(`${path.basename(toolPath)} [${fileName}]: ${line}`);
                }
            }
        });

        tool.stderr.on('data', data => {
            const lines = data.toString().split('\n').filter(Boolean);
            for (const line of lines) {
                errorOutput += line + '\n';
                console.log(`[DEBUG] stderr: ${line}`); // Débogage temporaire

                // Gestion des messages de progression pour chdman.exe (createcd ou extractcd)
                if (path.basename(toolPath).toLowerCase() === 'chdman.exe') {
                    // Tester plusieurs motifs possibles
                    const percentageMatch = line.match(/(\w+,\s*(\d+\.\d+)%\s*complete)/i);
                    if (percentageMatch && percentageMatch[2]) {
                        const percentage = parseFloat(percentageMatch[2]);
                        if (totalFiles > 0 && fileIndex >= 0) {
                            const baseProgress = 30 + (fileIndex / totalFiles) * 50;
                            const fileProgress = (percentage / 100) * (50 / totalFiles);
                            sendProgress(baseProgress + fileProgress, operation, fileIndex + 1, totalFiles, percentage);
                            //console.log(`[DEBUG] Progression détectée: total=${baseProgress + fileProgress}%, fichier=${percentage}%`);
                        } else {
                            sendLog(`Erreur: Paramètres invalides - totalFiles: ${totalFiles}, fileIndex: ${fileIndex}`);
                        }
                    }
                    return; // Ne pas logger ces messages
                }

                // Gestion des messages de progression pour dolphin-tool.exe
                if (path.basename(toolPath).toLowerCase() === 'dolphin-tool.exe' && line.includes('Compressing,')) {
                    const percentageMatch = line.match(/Compressing,\s*(\d+\.\d+)%\s*complete/);
                    if (percentageMatch) {
                        const percentage = parseFloat(percentageMatch[1]);
                        if (totalFiles > 0 && fileIndex >= 0) {
                            const baseProgress = 30 + (fileIndex / totalFiles) * 50;
                            const fileProgress = (percentage / 100) * (50 / totalFiles);
                            sendProgress(baseProgress + fileProgress, operation, fileIndex + 1, totalFiles, percentage);
                        } else {
                            sendLog(`Erreur: Paramètres invalides - totalFiles: ${totalFiles}, fileIndex: ${fileIndex}`);
                        }
                    }
                    return; // Ne pas logger ces messages
                }

                // Gestion des erreurs critiques pour dolphin-tool.exe
                if (path.basename(toolPath).toLowerCase() === 'dolphin-tool.exe' && line.includes('The input file is not a GC/Wii disc image')) {
                    hasCriticalError = true;
                    sendLog(`${path.basename(toolPath)} [${fileName}] Erreur critique: ${line}`);
                }
                // Autres messages dans stderr
                else {
                    sendLog(`${path.basename(toolPath)} [${fileName}] Erreur: ${line}`);
                }
            }
        });

        tool.on('close', code => {
            clearTimeout(timeout);
            if (code === 0 && !hasCriticalError) {
                //sendLog(`Traitement terminé : ${fileName}`);
                resolve(stdoutOutput);
            } else {
                const errorMsg = hasCriticalError ? 'Fichier incompatible : non reconnu comme une image de disque GC/Wii' : (errorOutput || `Échec avec code ${code}`);
                sendLog(`Erreur lors du traitement de ${fileName}: ${errorMsg}`);
                reject(new Error(errorMsg));
            }
        });

        tool.on('error', err => {
            clearTimeout(timeout);
            reject(err);
        });
    });
}

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

function sendProgress(totalProgress, message, currentFile = 0, totalFiles = 0, currentFileProgress = 0) {
    const progressMessage = totalFiles > 0 ? `${message} (${currentFile}/${totalFiles})` : message;
    mainWindow.webContents.send('progress-update', {
        totalProgress: Math.round(totalProgress * 10) / 10,
        currentFileProgress: Math.round(currentFileProgress * 10) / 10,
        message: progressMessage
    });
}

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1280,
        height: 800,
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
    // mainWindow.webContents.openDevTools();

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

ipcMain.handle('patch-xbox-iso', async (_, source, dest) => {
    const startTime = Date.now();
    const destination = await prepareDirectories(dest, 'xbox');
    let convertedGames = 0, optimizedGames = 0, ignoredArchives = 0, errorCount = 0;

    try {
        sendLog('Début du patch Xbox...');
        sendLog(`Dossier source: ${source}`);
        sendLog(`Dossier destination: ${destination}`);
        await validateTools();

        const allIsos = await extractArchives(source, tools.sevenZip, ['.7z', '.zip', '.gz', '.rar'], ['.iso']);
        sendProgress(30, `Patch des ISO`);

        for (let i = 0; i < allIsos.length; i++) {
            const iso = allIsos[i].name;
            const fullIsoPath = path.join(source, iso);
            const fileName = path.basename(iso, '.iso');
            sendProgress(30 + (i / allIsos.length) * 50, `Patch des ISO`, i + 1, allIsos.length);

            await fsPromises.copyFile(tools.xiso, path.join(destination, 'xiso.exe'));
            await runTool(path.join(destination, 'xiso.exe'), ['-r', fullIsoPath], destination, fileName);
            const patchedIso = path.join(destination, fileName + '_patched.iso');
            if (fs.existsSync(patchedIso)) {
                const statsBefore = fs.statSync(fullIsoPath);
                const statsAfter = fs.statSync(patchedIso);
                if (statsAfter.size < statsBefore.size) {
                    sendLog(`Optimisation détectée pour ${fileName}: ${statsBefore.size} -> ${statsAfter.size}`);
                    optimizedGames++;
                }
            }
            convertedGames++;
        }

        if (fs.existsSync(path.join(destination, 'xiso.exe'))) {
            await fsPromises.unlink(path.join(destination, 'xiso.exe')).catch(err => sendLog(`Erreur lors de la suppression de xiso.exe: ${err.message}`));
            sendLog(`xiso.exe supprimé de ${destination}`);
        }

        const duration = (Date.now() - startTime) / 1000;
        sendLog(`Patch Xbox terminé en ${duration}s`);
        sendLog(`Jeux convertis : ${convertedGames}`);
        sendLog(`Jeux optimisés : ${optimizedGames}`);
        sendLog(`Archives ignorées : ${ignoredArchives}`);
        sendLog(`Erreurs : ${errorCount}`);

        sendLog('Demande de confirmation pour le nettoyage des fichiers source...');
        const shouldCleanup = await new Promise((resolve) => {
            const cleanupChannel = 'confirm-cleanup';
            ipcMain.once(cleanupChannel, (_, shouldDelete) => {
                resolve(shouldDelete);
            });
            mainWindow.webContents.send('request-cleanup-confirmation', cleanupChannel);
        });

        if (shouldCleanup) {
            sendLog('Nettoyage des fichiers extraits...');
            sendProgress(80, `Nettoyage`);
            await cleanupFiles(source, ['.iso', '.old']);
            sendLog('Nettoyage terminé.');
        } else {
            sendLog('Nettoyage annulé par l’utilisateur.');
        }
        
        return { summary: { convertedGames, optimizedGames, ignoredArchives, errorCount } };
    } catch (error) {
        sendLog(`Erreur lors du patch Xbox: ${error.message}`);
        errorCount++;
        throw error;
    } finally {
        sendProgress(100, `Terminé`);
    }
});

ipcMain.handle('convert-to-chdv5', async (_, source, dest) => {
    const startTime = Date.now();
    const destination = await prepareDirectories(dest, 'CHD');
    let convertedGames = 0, skippedGames = 0, errorCount = 0;

    try {
        // sendLog('Début de la conversion en CHD...');
        sendLog(`Dossier source: ${source}`);
        sendLog(`Dossier destination: ${destination}`);
        await validateTools();

        const allInputs = await extractArchives(source, tools.sevenZip, ['.7z', '.zip', '.gz', '.rar'], ['.cue', '.gdi', '.iso']);
        sendLog(`Total des fichiers .cue/.gdi/.iso trouvés après extraction : ${allInputs.length}`);
        if (allInputs.length === 0) {
            sendLog('Aucun fichier .cue, .gdi ou .iso trouvé pour la conversion. Assurez-vous que le dossier source contient des fichiers compatibles.');
            return { summary: { convertedGames, skippedGames, errorCount } };
        }

        sendProgress(30, `Conversion en CHD`, 0, allInputs.length, 0);
        for (let i = 0; i < allInputs.length; i++) {
            const input = allInputs[i].name;
            const fullInputPath = path.join(source, input);
            const outputChdPath = path.join(destination, path.basename(input, path.extname(input)) + '.chd');
            sendLog(`Conversion de ${input}...`);
            sendProgress(30 + (i / allInputs.length) * 50, `Conversion en CHD`, i + 1, allInputs.length, 0);

            if (fs.existsSync(outputChdPath)) {
                sendLog(`Fichier déjà converti, ignoré : ${input} -> ${outputChdPath}`);
                skippedGames++;
                continue;
            }

            try {
                await fsPromises.access(destination, fs.constants.W_OK);
            } catch (error) {
                sendLog(`Erreur: Pas de permissions d'écriture dans ${destination}. Exécutez en tant qu'administrateur ou choisissez un autre dossier.`);
                throw new Error('Permissions insuffisantes pour écrire dans le dossier de destination');
            }

            try {
                const args = ['createcd', '-i', fullInputPath, '-o', outputChdPath];
                await runTool(tools.chdman, args, destination, input, allInputs.length, i, 'Conversion en CHD');

                if (fs.existsSync(outputChdPath)) {
                    const stats = fs.statSync(outputChdPath);
                    if (stats.size > 0) {
                        sendLog(`Conversion réussie : ${input} -> ${outputChdPath}`);
                        convertedGames++;
                    } else {
                        await fsPromises.unlink(outputChdPath).catch(err => sendLog(`Erreur lors de la suppression de ${outputChdPath}: ${err.message}`));
                        throw new Error('Fichier .chd généré mais vide ou invalide');
                    }
                } else {
                    throw new Error('Fichier .chd non généré');
                }
            } catch (error) {
                errorCount++;
                sendLog(`Échec de la conversion de ${input}: ${error.message || error.stack || 'Aucune information disponible'}`);
                if (fs.existsSync(outputChdPath)) {
                    await fsPromises.unlink(outputChdPath).catch(err => sendLog(`Erreur lors de la suppression de ${outputChdPath}: ${err.message}`));
                    sendLog(`Fichier .chd supprimé : ${outputChdPath}`);
                }
            }
        }
        const duration = (Date.now() - startTime) / 1000;
        sendLog(`Conversion CHD terminée en ${duration}s`);
        sendLog(`Jeux convertis : ${convertedGames}`);
        sendLog(`Jeux ignorés : ${skippedGames}`);
        sendLog(`Erreurs : ${errorCount}`);
        sendLog('Demande de confirmation pour le nettoyage des fichiers source...');
        
        const shouldCleanup = await new Promise((resolve) => {
            const cleanupChannel = 'confirm-cleanup';
            ipcMain.once(cleanupChannel, (_, shouldDelete) => {
                resolve(shouldDelete);
            });
            mainWindow.webContents.send('request-cleanup-confirmation', cleanupChannel);
        });

        if (shouldCleanup) {
            sendLog('Nettoyage des fichiers extraits...');
            sendProgress(80, `Nettoyage`);
            await cleanupFiles(source, ['.iso', '.cue', '.bin', '.gdi']);
            sendLog('Nettoyage terminé.');
        } else {
            sendLog('Nettoyage annulé par l’utilisateur.');
        }
        return { summary: { convertedGames, skippedGames, errorCount } };
    } catch (error) {
        sendLog(`Erreur lors de la conversion CHD: ${error.message || error.stack || 'Aucune information disponible'}`);
        errorCount++;
        throw error;
    } finally {
        sendProgress(100, `Terminé`, 0, 0, 0);
    }
});

ipcMain.handle('extract-chd', async (_, source, dest) => {
    const startTime = Date.now();
    const destination = await prepareDirectories(dest, 'Extracted_CHD');
    let extractedGames = 0, skippedGames = 0, errorCount = 0;

    try {
        //sendLog('Début de l\'extraction des fichiers CHD...');
        sendLog(`Dossier source: ${source}`);
        sendLog(`Dossier destination: ${destination}`);

        const allChds = [];
        const walkDir = async (dir) => {
            const files = await fsPromises.readdir(dir, { withFileTypes: true });
            for (const file of files) {
                const fullPath = path.join(dir, file.name);
                if (file.isDirectory()) {
                    await walkDir(fullPath);
                } else if (path.extname(file.name).toLowerCase() === '.chd') {
                    allChds.push({ name: file.name, fullPath });
                }
            }
        };
        await walkDir(source);

        sendLog(`Total des fichiers .chd trouvés : ${allChds.length}`);
        if (allChds.length === 0) {
            sendLog('Aucun fichier .chd trouvé pour l\'extraction. Assurez-vous que le dossier source contient des fichiers compatibles.');
            return { summary: { extractedGames, skippedGames, errorCount } };
        }

        try {
            await fsPromises.access(destination, fs.constants.W_OK);
        } catch (error) {
            sendLog(`Erreur: Pas de permissions d'écriture dans ${destination}. Exécutez en tant qu'administrateur ou choisissez un autre dossier.`);
            throw new Error('Permissions insuffisantes pour écrire dans le dossier de destination');
        }

        sendProgress(30, `Extraction des fichiers CHD`, 0, allChds.length, 0);
        for (let i = 0; i < allChds.length; i++) {
            const chd = allChds[i].name;
            const fullChdPath = path.join(source, chd);
            const outputCuePath = path.join(destination, path.basename(chd, path.extname(chd)) + '.cue');
            const outputBinPath = path.join(destination, path.basename(chd, path.extname(chd)) + '.bin');
            sendLog(`Extraction de ${chd}...`);
            sendProgress(30 + (i / allChds.length) * 50, `Extraction des fichiers CHD`, i + 1, allChds.length, 0);

            if (fs.existsSync(outputCuePath) || fs.existsSync(outputBinPath)) {
                sendLog(`Fichiers déjà extraits, ignoré : ${chd} -> ${outputCuePath}`);
                skippedGames++;
                continue;
            }

            try {
                const args = ['extractcd', '-i', fullChdPath, '-o', outputCuePath, '-ob', outputBinPath];
                await runTool(tools.chdman, args, destination, chd, allChds.length, i, 'Extraction des fichiers CHD');

                if (fs.existsSync(outputCuePath) && fs.existsSync(outputBinPath)) {
                    const cueStats = fs.statSync(outputCuePath);
                    const binStats = fs.statSync(outputBinPath);
                    if (cueStats.size > 0 && binStats.size > 0) {
                        sendLog(`Extraction réussie : ${chd} -> ${outputCuePath} et ${outputBinPath}`);
                        extractedGames++;
                    } else {
                        await fsPromises.unlink(outputCuePath).catch(err => sendLog(`Erreur lors de la suppression de ${outputCuePath}: ${err.message}`));
                        await fsPromises.unlink(outputBinPath).catch(err => sendLog(`Erreur lors de la suppression de ${outputBinPath}: ${err.message}`));
                        throw new Error('Fichiers .cue ou .bin générés mais vides ou invalides');
                    }
                } else {
                    throw new Error('Fichiers .cue ou .bin non générés');
                }
            } catch (error) {
                errorCount++;
                sendLog(`Échec de l'extraction de ${chd}: ${error.message || error.stack || 'Aucune information disponible'}`);
                if (fs.existsSync(outputCuePath)) {
                    await fsPromises.unlink(outputCuePath).catch(err => sendLog(`Erreur lors de la suppression de ${outputCuePath}: ${err.message}`));
                    sendLog(`Fichier .cue supprimé : ${outputCuePath}`);
                }
                if (fs.existsSync(outputBinPath)) {
                    await fsPromises.unlink(outputBinPath).catch(err => sendLog(`Erreur lors de la suppression de ${outputBinPath}: ${err.message}`));
                    sendLog(`Fichier .bin supprimé : ${outputBinPath}`);
                }
            }
        }

        const duration = (Date.now() - startTime) / 1000;
        sendLog(`Extraction CHD terminée en ${duration}s`);
        sendLog(`Jeux extraits : ${extractedGames}`);
        sendLog(`Jeux ignorés : ${skippedGames}`);
        sendLog(`Erreurs : ${errorCount}`);
        sendLog('Demande de confirmation pour le nettoyage des fichiers source...');
        const shouldCleanup = await new Promise((resolve) => {
            const cleanupChannel = 'confirm-cleanup';
            ipcMain.once(cleanupChannel, (_, shouldDelete) => {
                resolve(shouldDelete);
            });
            mainWindow.webContents.send('request-cleanup-confirmation', cleanupChannel);
        });

        if (shouldCleanup) {
            sendLog('Nettoyage des fichiers extraits...');
            sendProgress(80, `Nettoyage`);
            await cleanupFiles(source, ['.chd']);
            sendLog('Nettoyage terminé.');
        } else {
            sendLog('Nettoyage annulé par l’utilisateur.');
        }
        return { summary: { extractedGames, skippedGames, errorCount } };
    } catch (error) {
        sendLog(`Erreur lors de l'extraction CHD: ${error.message || error.stack || 'Aucune information disponible'}`);
        errorCount++;
        throw error;
    } finally {
        sendProgress(100, `Terminé`, 0, 0, 0);
    }
});

async function checkIsoCompatibility(isoPath, dolphinToolPath) {
    return new Promise((resolve, reject) => {
        sendLog(`Vérification de la compatibilité de ${path.basename(isoPath)} avec DolphinTool...`);
        const headerProcess = spawn(dolphinToolPath, ['header', '-i', isoPath]);
        let output = '';

        headerProcess.stdout.on('data', data => {
            output += data.toString();
        });

        headerProcess.stderr.on('data', data => {
            sendLog(`DolphinTool header [${path.basename(isoPath)}] Erreur: ${data}`);
        });

        headerProcess.on('close', code => {
            if (code === 0 && output.trim().length > 0) {
                sendLog(`ISO compatible : ${path.basename(isoPath)}`);
                resolve(true);
            } else {
                sendLog(`ISO incompatible : ${path.basename(isoPath)} (pas une image GameCube/Wii)`);
                resolve(false);
            }
        });

        headerProcess.on('error', err => reject(err));
    });
}

ipcMain.handle('convert-iso-to-rvz', async (_, source, dest) => {
    const startTime = Date.now();
    const destination = await prepareDirectories(dest, 'RVZ');
    let convertedGames = 0, skippedGames = 0, errorCount = 0;

    try {
        sendLog('Début de la conversion en RVZ...');
        sendLog(`Dossier source: ${source}`);
        sendLog(`Dossier destination: ${destination}`);
        await validateTools();

        const allIsos = await extractArchives(source, tools.sevenZip, ['.7z', '.zip', '.gz', '.rar'], ['.iso']);
        sendLog(`Total des fichiers .iso trouvés après extraction : ${allIsos.length}`);
        if (allIsos.length === 0) {
            sendLog('Aucun fichier .iso trouvé pour la conversion. Assurez-vous que le dossier source contient des fichiers compatibles.');
            return { summary: { convertedGames, skippedGames, errorCount } };
        }

        // Vérifier les permissions d'écriture
        try {
            await fsPromises.access(destination, fs.constants.W_OK);
        } catch (error) {
            sendLog(`Erreur: Pas de permissions d'écriture dans ${destination}. Exécutez en tant qu'administrateur ou choisissez un autre dossier.`);
            throw new Error('Permissions insuffisantes pour écrire dans le dossier de destination');
        }

        sendProgress(30, `Conversion en RVZ`, 0, allIsos.length);
        for (let i = 0; i < allIsos.length; i++) {
            const iso = allIsos[i].name;
            const fullIsoPath = path.join(source, iso);
            const outputRvzPath = path.join(destination, path.basename(iso, '.iso') + '.rvz');

            if (fs.existsSync(outputRvzPath)) {
                sendLog(`Jeu déjà converti, ignoré : ${iso} -> ${outputRvzPath}`);
                skippedGames++;
                sendProgress(30 + (i / allIsos.length) * 50, `Conversion en RVZ`, i + 1, allIsos.length);
                continue;
            }

            // Vérification de la compatibilité
            const isCompatible = await checkIsoCompatibility(fullIsoPath, tools.dolphinTool);
            if (!isCompatible) {
                errorCount++;
                sendLog(`Conversion ignorée pour ${iso} : incompatible avec RVZ`);
                sendProgress(30 + (i / allIsos.length) * 50, `Conversion en RVZ`, i + 1, allIsos.length);
                continue;
            }

            sendProgress(30 + (i / allIsos.length) * 50, `Conversion en RVZ`, i + 1, allIsos.length);
            try {
                const args = [
                    'convert',
                    '-i', fullIsoPath,
                    '-o', outputRvzPath,
                    '-f', 'rvz',
                    '-b', '131072',
                    '-c', 'zstd',
                    '-l', '5'
                ];
                await runTool(tools.dolphinTool, args, destination, iso, allIsos.length, i, 'Conversion en RVZ');

                if (fs.existsSync(outputRvzPath)) {
                    const stats = fs.statSync(outputRvzPath);
                    if (stats.size > 0) {
                        sendLog(`Conversion réussie : ${iso} -> ${outputRvzPath}`);
                        convertedGames++;
                    } else {
                        await fsPromises.unlink(outputRvzPath).catch(err => sendLog(`Erreur lors de la suppression de ${outputRvzPath}: ${err.message}`));
                        throw new Error('Fichier .rvz généré mais vide ou invalide');
                    }
                } else {
                    throw new Error('Fichier .rvz non généré');
                }
            } catch (error) {
                errorCount++;
                sendLog(`Échec de la conversion de ${iso}: ${error.message || error.stack || 'Aucune information disponible'}`);
                if (fs.existsSync(outputRvzPath)) {
                    await fsPromises.unlink(outputRvzPath).catch(err => sendLog(`Erreur lors de la suppression de ${outputRvzPath}: ${err.message}`));
                    sendLog(`Fichier .rvz supprimé : ${outputRvzPath}`);
                }
            }
        }

        const duration = (Date.now() - startTime) / 1000;
        sendLog(`Conversion RVZ terminée en ${duration}s`);
        sendLog(`Jeux convertis : ${convertedGames}`);
        sendLog(`Jeux ignorés : ${skippedGames}`);
        sendLog(`Erreurs : ${errorCount}`);

        sendLog('Demande de confirmation pour le nettoyage des fichiers source...');
        const shouldCleanup = await new Promise((resolve) => {
            const cleanupChannel = 'confirm-cleanup';
            ipcMain.once(cleanupChannel, (_, shouldDelete) => {
                resolve(shouldDelete);
            });
            mainWindow.webContents.send('request-cleanup-confirmation', cleanupChannel);
        });

        if (shouldCleanup) {
            sendLog('Nettoyage des fichiers extraits...');
            sendProgress(80, `Nettoyage`);
            await cleanupFiles(source, ['.iso']);
            sendLog('Nettoyage terminé.');
        } else {
            sendLog('Nettoyage annulé par l’utilisateur.');
        }

        return { summary: { convertedGames, skippedGames, errorCount } };
    } catch (error) {
        sendLog(`Erreur lors de la conversion RVZ: ${error.message || error.stack || 'Aucune information disponible'}`);
        errorCount++;
        throw error;
    } finally {
        sendProgress(100, `Terminé`);
    }
});

ipcMain.handle('merge-bin-cue', async (_, source, dest) => {
    const startTime = Date.now();
    const tempChdDir = await prepareDirectories(dest, 'Temp_CHD'); // Dossier temporaire pour les fichiers CHD
    const finalDir = await prepareDirectories(dest, 'Merged_CUE'); // Dossier final pour les fichiers fusionnés
    let mergedGames = 0, skippedGames = 0, errorCount = 0;

    try {
        sendLog('Début de la fusion des fichiers BIN/CUE...');
        sendLog(`Dossier source: ${source}`);
        sendLog(`Dossier temporaire pour CHD: ${tempChdDir}`);
        sendLog(`Dossier destination final: ${finalDir}`);
        await validateTools();

        // Étape 1 : Extraire les archives pour accéder aux fichiers .cue et .bin
        const allCues = await extractArchives(source, tools.sevenZip, ['.7z', '.zip', '.gz', '.rar'], ['.cue', '.bin']);
        sendLog(`Total des fichiers .cue et .bin trouvés après extraction : ${allCues.length}`);
        if (allCues.length === 0) {
            sendLog('Aucun fichier .cue ou .bin trouvé pour la fusion. Assurez-vous que le dossier source contient des fichiers compatibles.');
            return { summary: { mergedGames, skippedGames, errorCount } };
        }

        // Filtrer les fichiers .cue avec plusieurs .bin associés
        const multiBinCues = [];
        for (const cue of allCues.filter(f => path.extname(f.name).toLowerCase() === '.cue')) {
            const cueContent = await fsPromises.readFile(cue.fullPath, 'utf-8');
            const binFiles = cueContent.match(/FILE\s+"([^"]+\.bin)"/gi);
            if (binFiles && binFiles.length > 1) { // Vérifie s'il y a plusieurs .bin
                const cueDir = path.dirname(cue.fullPath);
                const binNames = binFiles.map(match => match.match(/"([^"]+)"/)[1].toLowerCase());
                const allBinsPresent = binNames.every(binName => allCues.some(f => path.basename(f.name).toLowerCase() === binName && path.dirname(f.fullPath) === cueDir));
                if (allBinsPresent) {
                    multiBinCues.push(cue);
                    sendLog(`Fichier .cue avec plusieurs .bin détecté : ${cue.name} (tous les .bin trouvés)`);
                } else {
                    sendLog(`Fichier .cue ignoré : ${cue.name} (certains .bin manquants)`);
                    skippedGames++;
                }
            } else {
                sendLog(`Fichier .cue avec un seul .bin, ignoré : ${cue.name}`);
                skippedGames++;
            }
        }

        sendLog(`Total des fichiers .cue avec plusieurs .bin trouvés : ${multiBinCues.length}`);
        if (multiBinCues.length === 0) {
            sendLog('Aucun fichier .cue avec plusieurs .bin trouvé pour la fusion.');
            return { summary: { mergedGames, skippedGames, errorCount } };
        }

        // Vérifier les permissions d'écriture
        try {
            await fsPromises.access(tempChdDir, fs.constants.W_OK);
            await fsPromises.access(finalDir, fs.constants.W_OK);
        } catch (error) {
            sendLog(`Erreur: Pas de permissions d'écriture dans ${tempChdDir} ou ${finalDir}. Exécutez en tant qu'administrateur ou choisissez un autre dossier.`);
            throw new Error('Permissions insuffisantes pour écrire dans le dossier de destination');
        }

        // Étape 2 : Convertir chaque .cue avec plusieurs .bin en .chd
        sendProgress(30, `Conversion en CHD pour fusion`, 0, multiBinCues.length, 0);
        for (let i = 0; i < multiBinCues.length; i++) {
            const cue = multiBinCues[i].name;
            const fullCuePath = path.join(source, cue);
            const outputChdPath = path.join(tempChdDir, path.basename(cue, '.cue') + '.chd');
            sendLog(`Conversion de ${cue} en CHD...`);
            sendProgress(30 + (i / multiBinCues.length) * 25, `Conversion en CHD pour fusion`, i + 1, multiBinCues.length, 0);

            if (fs.existsSync(outputChdPath)) {
                sendLog(`Fichier CHD déjà existant, ignoré : ${cue} -> ${outputChdPath}`);
                continue;
            }

            try {
                const args = ['createcd', '-i', fullCuePath, '-o', outputChdPath];
                await runTool(tools.chdman, args, tempChdDir, cue, multiBinCues.length, i, 'Conversion en CHD pour fusion');

                if (fs.existsSync(outputChdPath)) {
                    const stats = fs.statSync(outputChdPath);
                    if (stats.size > 0) {
                        sendLog(`Conversion réussie : ${cue} -> ${outputChdPath}`);
                    } else {
                        await fsPromises.unlink(outputChdPath).catch(err => sendLog(`Erreur lors de la suppression de ${outputChdPath}: ${err.message}`));
                        throw new Error('Fichier .chd généré mais vide ou invalide');
                    }
                } else {
                    throw new Error('Fichier .chd non généré');
                }
            } catch (error) {
                errorCount++;
                sendLog(`Échec de la conversion de ${cue} en CHD: ${error.message || error.stack || 'Aucune information disponible'}`);
                if (fs.existsSync(outputChdPath)) {
                    await fsPromises.unlink(outputChdPath).catch(err => sendLog(`Erreur lors de la suppression de ${outputChdPath}: ${err.message}`));
                    sendLog(`Fichier .chd supprimé : ${outputChdPath}`);
                }
                continue; // Continue avec le prochain fichier
            }
        }

        // Étape 3 : Extraire les fichiers .chd en .cue avec un seul .bin
        const allChds = [];
        const walkChdDir = async (dir) => {
            const files = await fsPromises.readdir(dir, { withFileTypes: true });
            for (const file of files) {
                const fullPath = path.join(dir, file.name);
                if (file.isDirectory()) {
                    await walkChdDir(fullPath);
                } else if (path.extname(file.name).toLowerCase() === '.chd') {
                    allChds.push({ name: file.name, fullPath });
                }
            }
        };
        await walkChdDir(tempChdDir);

        sendLog(`Total des fichiers .chd à extraire pour fusion : ${allChds.length}`);
        sendProgress(55, `Extraction CHD pour fusion`, 0, allChds.length, 0);
        for (let i = 0; i < allChds.length; i++) {
            const chd = allChds[i].name;
            const fullChdPath = path.join(tempChdDir, chd);
            const outputCuePath = path.join(finalDir, path.basename(chd, path.extname(chd)) + '.cue');
            const outputBinPath = path.join(finalDir, path.basename(chd, path.extname(chd)) + '.bin');
            sendLog(`Extraction de ${chd} pour fusion...`);
            sendProgress(55 + (i / allChds.length) * 25, `Extraction CHD pour fusion`, i + 1, allChds.length, 0);

            if (fs.existsSync(outputCuePath) || fs.existsSync(outputBinPath)) {
                sendLog(`Fichiers déjà extraits, ignoré : ${chd} -> ${outputCuePath}`);
                skippedGames++;
                continue;
            }

            try {
                const args = ['extractcd', '-i', fullChdPath, '-o', outputCuePath, '-ob', outputBinPath];
                await runTool(tools.chdman, args, finalDir, chd, allChds.length, i, 'Extraction CHD pour fusion');

                if (fs.existsSync(outputCuePath) && fs.existsSync(outputBinPath)) {
                    const cueStats = fs.statSync(outputCuePath);
                    const binStats = fs.statSync(outputBinPath);
                    if (cueStats.size > 0 && binStats.size > 0) {
                        sendLog(`Fusion réussie : ${chd} -> ${outputCuePath} et ${outputBinPath}`);
                        mergedGames++;
                    } else {
                        await fsPromises.unlink(outputCuePath).catch(err => sendLog(`Erreur lors de la suppression de ${outputCuePath}: ${err.message}`));
                        await fsPromises.unlink(outputBinPath).catch(err => sendLog(`Erreur lors de la suppression de ${outputBinPath}: ${err.message}`));
                        throw new Error('Fichiers .cue ou .bin générés mais vides ou invalides');
                    }
                } else {
                    throw new Error('Fichiers .cue ou .bin non générés');
                }
            } catch (error) {
                errorCount++;
                sendLog(`Échec de l'extraction de ${chd} pour fusion: ${error.message || error.stack || 'Aucune information disponible'}`);
                if (fs.existsSync(outputCuePath)) {
                    await fsPromises.unlink(outputCuePath).catch(err => sendLog(`Erreur lors de la suppression de ${outputCuePath}: ${err.message}`));
                    sendLog(`Fichier .cue supprimé : ${outputCuePath}`);
                }
                if (fs.existsSync(outputBinPath)) {
                    await fsPromises.unlink(outputBinPath).catch(err => sendLog(`Erreur lors de la suppression de ${outputBinPath}: ${err.message}`));
                    sendLog(`Fichier .bin supprimé : ${outputBinPath}`);
                }
                continue; // Continue avec le prochain fichier
            }
        }

        const duration = (Date.now() - startTime) / 1000;
        sendLog(`Fusion BIN/CUE terminée en ${duration}s`);
        sendLog(`Jeux fusionnés : ${mergedGames}`);
        sendLog(`Jeux ignorés : ${skippedGames}`);
        sendLog(`Erreurs : ${errorCount}`);

        sendLog('Demande de confirmation pour le nettoyage des fichiers source...');
        const shouldCleanup = await new Promise((resolve) => {
            const cleanupChannel = 'confirm-cleanup';
            ipcMain.once(cleanupChannel, (_, shouldDelete) => {
                resolve(shouldDelete);
            });
            mainWindow.webContents.send('request-cleanup-confirmation', cleanupChannel);
        });

        if (shouldCleanup) {
            sendLog('Nettoyage des fichiers extraits et temporaires...');
            sendProgress(80, `Nettoyage`);
            await cleanupFiles(source, ['.cue', '.bin']); // Nettoie les fichiers .cue et .bin sources
            await cleanupFiles(tempChdDir, ['.chd']); // Nettoie les fichiers CHD temporaires
            sendLog('Nettoyage terminé.');
        } else {
            sendLog('Nettoyage annulé par l’utilisateur.');
        }

        return { summary: { mergedGames, skippedGames, errorCount } };
    } catch (error) {
        sendLog(`Erreur lors de la fusion BIN/CUE: ${error.message || error.stack || 'Aucune information disponible'}`);
        errorCount++;
        throw error;
    } finally {
        sendProgress(100, `Terminé`, 0, 0, 0);
    }
});