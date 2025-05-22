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
    chdman: path.join(resourcesPath, 'chdman.exe'),
    xiso: path.join(resourcesPath, 'xiso.exe'),
    dolphinTool: path.join(resourcesPath, 'DolphinTool.exe')
};

async function validateTools() {
    for (const [name, path] of Object.entries(tools)) {
        if (!fs.existsSync(path)) {
            sendLog(`Erreur : ${name} non trouvé à ${path}`);
            throw new Error(`${name} non trouvé à ${path}`);
        }
        sendLog(`Utilisation de ${name} à ${path}`);
    }
}

async function extractArchives(sourceDir, sevenZipPath, extensions = ['.7z', '.zip', '.gz', '.rar'], targetExtensions = ['.iso', '.cue', '.gdi']) {
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
            // Inclure les fichiers .bin associés aux .cue/.gdi
            const associatedFiles = [];
            for (const target of targetFiles) {
                associatedFiles.push(target);
                if (['.cue', '.gdi'].some(ext => target.toLowerCase().endsWith(ext))) {
                    const baseName = path.basename(target, path.extname(target));
                    const binFile = filesInside.find(f => f.toLowerCase() === `${baseName.toLowerCase()}.bin`);
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

async function runTool(toolPath, args, workingDir, fileName) {
    return new Promise((resolve, reject) => {
        sendLog(`Exécution de ${path.basename(toolPath)} ${args.join(' ')}`);
        const tool = spawn(toolPath, args, { cwd: workingDir });
        let stdoutOutput = '';
        let errorOutput = '';
        let lastLoggedPercentage = -1;
        let hasCriticalError = false; // Pour suivre les erreurs critiques

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

                // Gestion spéciale pour chdman.exe (progression)
                if (path.basename(toolPath).toLowerCase() === 'chdman.exe' && line.includes('Compressing')) {
                    const match = line.match(/Compressing, (\d+\.\d+)% complete/);
                    if (match) {
                        const percentage = parseFloat(match[1]);
                        if (line.includes('Compression complete') || Math.floor(percentage / 10) * 10 > lastLoggedPercentage) {
                            lastLoggedPercentage = Math.floor(percentage / 10) * 10;
                            sendLog(`${path.basename(toolPath)} [${fileName}]: ${line}`);
                        }
                    } else {
                        sendLog(`${path.basename(toolPath)} [${fileName}]: ${line}`);
                    }
                }
                // Gestion spéciale pour DolphinTool.exe (erreur critique)
                else if (path.basename(toolPath).toLowerCase() === 'dolphintool.exe' && line.includes('The input file is not a GC/Wii disc image')) {
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
                sendLog(`Traitement terminé : ${fileName}`);
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

function sendProgress(percent, message, current, total) {
    if (mainWindow) {
        console.log(`Envoi progression: ${percent}% - ${message} (${current}/${total})`);
        mainWindow.webContents.send('progress-update', { percent, message, current, total });
    }
}

async function extractWith7z(archivePath, destination, filesToExtract, sevenZipPath) {
    return new Promise((resolve, reject) => {
        const outputArg = `-o${destination}`;
        const args = ['x', archivePath, '-y', outputArg, ...filesToExtract];
        sendLog(`Exécution de 7za.exe ${args.join(' ')}`);
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

        await cleanupFiles(source, ['.iso', '.old']);
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
        sendLog('Début de la conversion en CHD...');
        sendLog(`Dossier source: ${source}`);
        sendLog(`Dossier destination: ${destination}`);
        await validateTools();

        const allInputs = await extractArchives(source, tools.sevenZip, ['.7z', '.zip', '.gz', '.rar'], ['.cue', '.gdi', '.iso']);
        sendLog(`Total des fichiers .cue/.gdi/.iso trouvés après extraction : ${allInputs.length}`);
        if (allInputs.length === 0) {
            sendLog('Aucun fichier .cue, .gdi ou .iso trouvé pour la conversion. Assurez-vous que le dossier source contient des fichiers compatibles.');
            return { summary: { convertedGames, skippedGames, errorCount } };
        }

        sendProgress(30, `Conversion en CHD`);
        for (let i = 0; i < allInputs.length; i++) {
            const input = allInputs[i].name;
            const fullInputPath = path.join(source, input);
            const outputChdPath = path.join(destination, path.basename(input, path.extname(input)) + '.chd');
            sendLog(`Début de la conversion de ${input}...`);
            sendProgress(30 + (i / allInputs.length) * 50, `Conversion en CHD`, i + 1, allInputs.length);
            await runTool(tools.chdman, ['createcd', '-i', fullInputPath, '-o', outputChdPath], destination, input);
            sendLog(`Conversion réussie : ${input} -> ${outputChdPath}`);
            convertedGames++;
        }

        await cleanupFiles(source, ['.cue', '.gdi', '.iso']);
        const duration = (Date.now() - startTime) / 1000;
        sendLog(`Conversion CHD terminée en ${duration}s`);
        sendLog(`Jeux convertis : ${convertedGames}`);
        sendLog(`Jeux ignorés : ${skippedGames}`);
        sendLog(`Erreurs : ${errorCount}`);

        return { summary: { convertedGames, skippedGames, errorCount } };
    } catch (error) {
        sendLog(`Erreur lors de la conversion CHD: ${error.message}`);
        errorCount++;
        throw error;
    } finally {
        sendProgress(100, `Terminé`);
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

        sendProgress(30, `Conversion en RVZ`);
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
                await runTool(tools.dolphinTool, [
                    'convert', '-f', 'rvz', '-c', 'zstd', '-l', '5', '-b', '131072',
                    '-i', fullIsoPath, '-o', outputRvzPath
                ], destination, iso);

                // Vérification post-conversion : fichier .rvz doit exister et avoir une taille > 0
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
                sendLog(`Échec de la conversion de ${iso}: ${error.message}`);
                if (fs.existsSync(outputRvzPath)) {
                    await fsPromises.unlink(outputRvzPath).catch(err => sendLog(`Erreur lors de la suppression de ${outputRvzPath}: ${err.message}`));
                    sendLog(`Fichier .rvz supprimé : ${outputRvzPath}`);
                }
            }
        }

        await cleanupFiles(source, ['.iso']);
        const duration = (Date.now() - startTime) / 1000;
        sendLog(`Conversion RVZ terminée en ${duration}s`);
        sendLog(`Jeux convertis : ${convertedGames}`);
        sendLog(`Jeux ignorés : ${skippedGames}`);
        sendLog(`Erreurs : ${errorCount}`);

        return { summary: { convertedGames, skippedGames, errorCount } };
    } catch (error) {
        sendLog(`Erreur lors de la conversion RVZ: ${error.message}`);
        errorCount++;
        throw error;
    } finally {
        sendProgress(100, `Terminé`);
    }
});