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
    ? path.join(path.dirname(process.resourcesPath), 'ressources') // Remonte d'un dossier et va dans 'ressources'
    : path.join(__dirname, 'ressources');

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

async function extractWith7z(archivePath, destination, filesToExtract, sevenZipPath) {
    return new Promise((resolve, reject) => {
        // Fusionner -o et le chemin de destination en un seul argument
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
          const xisoPath = path.join(resourcesPath, 'xiso.exe');
		sendLog(`Chemin calculé de resourcesPath : ${resourcesPath}`);
const sevenZipPath = path.join(resourcesPath, '7za.exe');
sendLog(`Chemin attendu de 7za.exe : ${sevenZipPath}`);
if (!fs.existsSync(sevenZipPath)) {
    sendLog(`Erreur : 7za.exe non trouvé à ${sevenZipPath}`);
    throw new Error(`7za.exe non trouvé à ${sevenZipPath}`);
}
        sendLog(`Utilisation de 7za.exe à ${sevenZipPath}`);

        if (!fs.existsSync(xisoPath)) {
            sendLog(`Erreur : xiso.exe non trouvé à ${xisoPath}`);
            throw new Error(`xiso.exe non trouvé à ${xisoPath}`);
        }

        // Copier xiso.exe dans le dossier de destination
        const destXisoPath = path.join(destination, 'xiso.exe');
        await fsPromises.copyFile(xisoPath, destXisoPath);
        sendLog(`xiso.exe copié dans ${destination}`);

        // Test d'exécution de 7za.exe pour confirmer qu'il est exécutable
        try {
            await new Promise((resolve, reject) => {
                const testSpawn = spawn(sevenZipPath, ['--help']);
                testSpawn.on('close', code => {
                    if (code === 0) {
                        sendLog('Test de 7za.exe réussi : exécutable valide');
                        resolve();
                    } else {
                        reject(new Error('7za.exe n\'est pas exécutable'));
                    }
                });
                testSpawn.on('error', err => reject(err));
            });
        } catch (error) {
            sendLog(`Erreur lors du test de 7za.exe : ${error.message}`);
            throw error;
        }

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
            sendProgress((i / archives.length) * 10, `Analyse des archives`, i + 1, archives.length);
            const filesInside = await new Promise((resolve, reject) => {
                const filesList = [];
                seven.list(fullPath, { $bin: sevenZipPath })
                    .on('data', file => filesList.push(file.file))
                    .on('end', () => resolve(filesList))
                    .on('error', reject);
            });

            const isosInArchive = filesInside.filter(f => f.toLowerCase().endsWith('.iso'));
            if (isosInArchive.length > 0) {
                validArchives.push({ file, fullPath, isos: isosInArchive });
            } else {
                sendLog(`Archive ignorée (pas de .iso) : ${file}`);
                ignoredArchives++;
            }
        }

        sendLog(`Archives valides contenant des .iso : ${validArchives.length}`);
        sendProgress(10, `Extraction des archives`);

        for (let i = 0; i < validArchives.length; i++) {
            const { file, fullPath, isos } = validArchives[i];
            sendLog(`Extraction des fichiers .iso de ${file}...`);
            sendProgress(10 + (i / validArchives.length) * 20, `Extraction des archives`, i + 1, validArchives.length);
            await extractWith7z(fullPath, source, isos, sevenZipPath);
            sendLog(`Extraction terminée : ${file} -> ${source} (${isos.join(', ')})`);
        }

        sendLog(`Recherche des fichiers .iso après extraction...`);
        const allFilesAfterExtract = await fsPromises.readdir(source);
        const allIsos = allFilesAfterExtract.filter(f => path.extname(f).toLowerCase() === '.iso');

        sendLog(`Total des .iso trouvés : ${allIsos.length}`);
        sendProgress(30, `Patch des ISO`);

        for (let i = 0; i < allIsos.length; i++) {
            const iso = allIsos[i];
            const fullIsoPath = path.join(source, iso);
            const fileName = path.basename(iso, '.iso');
            sendLog(`Patch de ${fileName}...`);
            sendProgress(30 + (i / allIsos.length) * 50, `Patch des ISO`, i + 1, allIsos.length);

            let hasError = false;
            let errorMessage = '';

            await new Promise((resolve) => {
                const args = ['-r', fullIsoPath];
                sendLog(`Exécution de xiso.exe ${args.join(' ')}`);
                const xiso = spawn(destXisoPath, args, { cwd: destination });
                let stdoutOutput = '';
			xiso.stdout.on('data', data => {
				const lines = data.toString().split('\n').filter(Boolean);
				for (const line of lines) {
					stdoutOutput += line + '\n';
					if (line.includes('successfully rewritten')) {
						sendLog(`xiso.exe [${fileName}]: ${line}`);
					}
				}
			});
			xiso.stderr.on('data', data => {
				const lines = data.toString().split('\n').filter(Boolean);
				for (const line of lines) {
					sendLog(`xiso.exe [${fileName}] Erreur: ${line}`);
					hasError = true;
					errorMessage = line;
				}
			});
			xiso.on('close', code => {
				if (code === 0 && !hasError) {
					sendLog(`Patch terminé : ${fileName}`);
					const patchedIso = path.join(destination, fileName);
					if (fs.existsSync(patchedIso)) {
						const statsBefore = fs.statSync(fullIsoPath);
						const statsAfter = fs.statSync(patchedIso);
						if (statsAfter.size < statsBefore.size) {
							sendLog(`Optimisation détectée pour ${fileName}: ${statsBefore.size} -> ${statsAfter.size}`);
							optimizedGames++;
						}
					}
					resolve();
				} else {
					errorCount++;
					const errorMsg = hasError ? errorMessage : `Échec du patch de ${fileName}, code ${code}`;
					sendLog(errorMsg);
					resolve();
				}
			});
            });
        }

       sendLog('Nettoyage des fichiers extraits...');
		sendProgress(80, `Nettoyage`);
		// Supprimer les fichiers .iso originaux
		for (let i = 0; i < allIsos.length; i++) {
			const iso = allIsos[i];
			const fullIsoPath = path.join(source, iso);
			if (fs.existsSync(fullIsoPath)) {
				await fsPromises.unlink(fullIsoPath).catch(err => {
					sendLog(`Erreur lors de la suppression de ${fullIsoPath}: ${err.message}`);
				});
			}
		}
		// Supprimer tous les fichiers .old dans le dossier source
		const allFiles = await fsPromises.readdir(source);
		const oldFiles = allFiles.filter(file => path.extname(file).toLowerCase() === '.old');
		for (let i = 0; i < oldFiles.length; i++) {
			const oldFile = oldFiles[i];
			const fullOldPath = path.join(source, oldFile);
			if (fs.existsSync(fullOldPath)) {
				await fsPromises.unlink(fullOldPath).catch(err => {
					sendLog(`Erreur lors de la suppression de ${fullOldPath}: ${err.message}`);
				});
			}
		}
        // Supprimer xiso.exe du dossier de destination
        if (fs.existsSync(destXisoPath)) {
            await fsPromises.unlink(destXisoPath).catch(err => {
                sendLog(`Erreur lors de la suppression de ${destXisoPath}: ${err.message}`);
            });
            sendLog(`xiso.exe supprimé de ${destination}`);
        }

        const duration = (Date.now() - startTime) / 1000;
        sendLog(`Patch Xbox terminé en ${duration}s`);
        sendLog(`Jeux convertis : ${convertedGames}`);
        sendLog(`Jeux optimisés : ${optimizedGames}`);
        sendLog(`Archives ignorées : ${ignoredArchives}`);
        sendLog(`Erreurs : ${errorCount}`);

        return {
            summary: { convertedGames, optimizedGames, ignoredArchives, errorCount }
        };
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
    const destination = dest.endsWith('\\') ? dest + 'CHD' : dest + '\\CHD';
    let convertedGames = 0;
    let skippedGames = 0;
    let errorCount = 0;

    try {
        sendLog('Début de la conversion en CHD...');
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

        // Test d'exécution de 7za.exe pour confirmer qu'il est exécutable
        try {
            await new Promise((resolve, reject) => {
                const testSpawn = spawn(sevenZipPath, ['--help']);
                testSpawn.on('close', code => {
                    if (code === 0) {
                        sendLog('Test de 7za.exe réussi : exécutable valide');
                        resolve();
                    } else {
                        reject(new Error('7za.exe n\'est pas exécutable'));
                    }
                });
                testSpawn.on('error', err => reject(err));
            });
        } catch (error) {
            sendLog(`Erreur lors du test de 7za.exe : ${error.message}`);
            throw error;
        }

        const archiveExtensions = ['.7z', '.zip', '.gz', '.rar'];
        const sourceFiles = await fsPromises.readdir(source, { recursive: true });
        const archives = sourceFiles.filter(f => archiveExtensions.includes(path.extname(f).toLowerCase()));
        const sourceCues = sourceFiles.filter(f => ['.cue', '.gdi'].includes(path.extname(f).toLowerCase()));
        const sourceIsos = sourceFiles.filter(f => path.extname(f).toLowerCase() === '.iso');

        sendLog(`Archives détectées : ${archives.length}`);
        sendLog(`Fichiers .cue/.gdi détectés : ${sourceCues.length}`);
        sendLog(`Fichiers .iso détectés : ${sourceIsos.length}`);

        const validArchives = [];

        for (let i = 0; i < archives.length; i++) {
            const file = archives[i];
            const fullPath = path.join(source, file);
            sendLog(`Vérification de ${file}...`);
            sendProgress((i / archives.length) * 10, `Analyse des archives`, i + 1, archives.length);
            const filesInside = await new Promise((resolve, reject) => {
                const filesList = [];
                seven.list(fullPath, { $bin: sevenZipPath })
                    .on('data', file => filesList.push(file.file))
                    .on('end', () => resolve(filesList))
                    .on('error', reject);
            });

            const targetFiles = filesInside.filter(f => ['.cue', '.gdi', '.iso'].some(ext => f.toLowerCase().endsWith(ext)));
            if (targetFiles.length > 0) {
                validArchives.push({ file, fullPath, targets: targetFiles });
            } else {
                sendLog(`Archive ignorée (pas de .cue/.gdi/.iso) : ${file}`);
                skippedGames++;
            }
        }

        sendLog(`Archives valides contenant des .cue/.gdi/.iso : ${validArchives.length}`);
        sendProgress(10, `Extraction des archives`);

        for (let i = 0; i < validArchives.length; i++) {
            const { file, fullPath, targets } = validArchives[i];
            sendLog(`Extraction des fichiers .cue/.gdi/.iso de ${file}...`);
            sendProgress(10 + (i / validArchives.length) * 20, `Extraction des archives`, i + 1, validArchives.length);
            await extractWith7z(fullPath, source, targets, sevenZipPath);
            sendLog(`Extraction terminée : ${file} -> ${source} (${targets.join(', ')})`);
        }

        sendLog(`Recherche des fichiers .cue/.gdi/.iso après extraction...`);
        const allFilesAfterExtract = await fsPromises.readdir(source);
        const allCues = allFilesAfterExtract.filter(f => ['.cue', '.gdi'].includes(path.extname(f).toLowerCase()));
        const allIsos = allFilesAfterExtract.filter(f => path.extname(f).toLowerCase() === '.iso');

        sendLog(`Total des .cue/.gdi trouvés : ${allCues.length}`);
        sendLog(`Total des .iso trouvés : ${allIsos.length}`);
        sendProgress(30, `Conversion en CHD`);

        const chdmanPath = path.join(resourcesPath, 'chdman.exe');
        if (!fs.existsSync(chdmanPath)) {
            sendLog(`Erreur : chdman.exe non trouvé à ${chdmanPath}`);
            throw new Error(`chdman.exe non trouvé à ${chdmanPath}`);
        }
        sendLog(`Utilisation de chdman.exe à ${chdmanPath}`);

        const allInputs = [...allCues, ...allIsos];
        for (let i = 0; i < allInputs.length; i++) {
            const input = allInputs[i];
            const fullInputPath = path.join(source, input);
            const outputChdPath = path.join(destination, path.basename(input, path.extname(input)) + '.chd');
            sendLog(`Conversion de ${input}...`);
            sendProgress(30 + (i / allInputs.length) * 50, `Conversion en CHD`, i + 1, allInputs.length);

            await new Promise((resolve, reject) => {
                const chdman = spawn(chdmanPath, ['createcd', '-i', fullInputPath, '-o', outputChdPath]);
                let errorOutput = '';

                chdman.stdout.on('data', data => sendLog(`chdman stdout: ${data}`));
                chdman.stderr.on('data', data => {
                    errorOutput += data;
                    sendLog(`chdman stderr: ${data}`);
                });
                chdman.on('close', code => {
                    if (code === 0) {
                        sendLog(`Conversion terminée : ${input} -> ${outputChdPath}`);
                        convertedGames++;
                        resolve();
                    } else {
                        sendLog(`Erreur lors de la conversion de ${input}: code ${code}`);
                        errorCount++;
                        reject(new Error(errorOutput));
                    }
                });
            });
        }

        sendLog('Nettoyage des fichiers extraits...');
        sendProgress(80, `Nettoyage`);
        for (let i = 0; i < allInputs.length; i++) {
            const input = allInputs[i];
            const fullInputPath = path.join(source, input);
            if (fs.existsSync(fullInputPath)) {
                await fsPromises.unlink(fullInputPath);
                sendLog(`Fichier extrait supprimé : ${fullInputPath}`);
            }
        }

        const duration = (Date.now() - startTime) / 1000;
        sendLog(`Conversion CHD terminée en ${duration}s`);
        sendLog(`Jeux convertis : ${convertedGames}`);
        sendLog(`Jeux ignorés : ${skippedGames}`);
        sendLog(`Erreurs : ${errorCount}`);

        return {
            summary: { convertedGames, skippedGames, errorCount }
        };
    } catch (error) {
        sendLog(`Erreur lors de la conversion CHD: ${error.message}`);
        errorCount++;
        throw error;
    } finally {
        sendProgress(100, `Terminé`);
    }
});

ipcMain.handle('convert-iso-to-rvz', async (_, source, dest) => {
    const startTime = Date.now();
    const destination = dest.endsWith('\\') ? dest + 'RVZ' : dest + '\\RVZ';
    let convertedGames = 0;
    let skippedGames = 0;
    let errorCount = 0;

    try {
        sendLog('Début de la conversion en RVZ...');
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

        // Test d'exécution de 7za.exe pour confirmer qu'il est exécutable
        try {
            await new Promise((resolve, reject) => {
                const testSpawn = spawn(sevenZipPath, ['--help']);
                testSpawn.on('close', code => {
                    if (code === 0) {
                        sendLog('Test de 7za.exe réussi : exécutable valide');
                        resolve();
                    } else {
                        reject(new Error('7za.exe n\'est pas exécutable'));
                    }
                });
                testSpawn.on('error', err => reject(err));
            });
        } catch (error) {
            sendLog(`Erreur lors du test de 7za.exe : ${error.message}`);
            throw error;
        }

        const archiveExtensions = ['.7z', '.zip', '.gz', '.rar'];
        const sourceFiles = await fsPromises.readdir(source, { recursive: true });
        const archives = sourceFiles.filter(f => archiveExtensions.includes(path.extname(f).toLowerCase()));
        const sourceIsos = sourceFiles.filter(f => path.extname(f).toLowerCase() === '.iso');

        sendLog(`Archives détectées : ${archives.length}`);
        sendLog(`Fichiers .iso détectés : ${sourceIsos.length}`);

        const validArchives = [];

        for (let i = 0; i < archives.length; i++) {
            const file = archives[i];
            const fullPath = path.join(source, file);
            sendLog(`Vérification de ${file}...`);
            sendProgress((i / archives.length) * 10, `Analyse des archives`, i + 1, archives.length);
            const filesInside = await new Promise((resolve, reject) => {
                const filesList = [];
                seven.list(fullPath, { $bin: sevenZipPath })
                    .on('data', file => filesList.push(file.file))
                    .on('end', () => resolve(filesList))
                    .on('error', reject);
            });

            const isosInArchive = filesInside.filter(f => f.toLowerCase().endsWith('.iso'));
            if (isosInArchive.length > 0) {
                validArchives.push({ file, fullPath, isos: isosInArchive });
            } else {
                sendLog(`Archive ignorée (pas de .iso) : ${file}`);
                skippedGames++;
            }
        }

        sendLog(`Archives valides contenant des .iso : ${validArchives.length}`);
        sendProgress(10, `Extraction des archives`);

        for (let i = 0; i < validArchives.length; i++) {
            const { file, fullPath, isos } = validArchives[i];
            sendLog(`Extraction des fichiers .iso de ${file}...`);
            sendProgress(10 + (i / validArchives.length) * 20, `Extraction des archives`, i + 1, validArchives.length);
            await extractWith7z(fullPath, source, isos, sevenZipPath);
            sendLog(`Extraction terminée : ${file} -> ${source} (${isos.join(', ')})`);
        }

        sendLog(`Recherche des fichiers .iso après extraction...`);
        const allFilesAfterExtract = await fsPromises.readdir(source);
        const allIsos = allFilesAfterExtract.filter(f => path.extname(f).toLowerCase() === '.iso');

        sendLog(`Total des .iso trouvés : ${allIsos.length}`);
        sendProgress(30, `Conversion en RVZ`);

        const dolphinToolPath = path.join(resourcesPath, 'DolphinTool.exe');
        if (!fs.existsSync(dolphinToolPath)) {
            sendLog(`Erreur : DolphinTool.exe non trouvé à ${dolphinToolPath}`);
            throw new Error(`DolphinTool.exe non trouvé à ${dolphinToolPath}`);
        }
        sendLog(`Utilisation de DolphinTool.exe à ${dolphinToolPath}`);

        for (let i = 0; i < allIsos.length; i++) {
            const iso = allIsos[i];
            const fullIsoPath = path.join(source, iso);
            const outputRvzPath = path.join(destination, path.basename(iso, '.iso') + '.rvz');

            // Vérifier si le fichier .rvz existe déjà
            if (fs.existsSync(outputRvzPath)) {
                sendLog(`Jeu déjà converti, ignoré : ${iso} -> ${outputRvzPath}`);
                skippedGames++;
                sendProgress(30 + (i / allIsos.length) * 50, `Conversion en RVZ`, i + 1, allIsos.length);
                continue;
            }

            sendLog(`Conversion de ${iso}...`);
            sendProgress(30 + (i / allIsos.length) * 50, `Conversion en RVZ`, i + 1, allIsos.length);

            await new Promise((resolve, reject) => {
                const dolphinTool = spawn(dolphinToolPath, [
                    'convert',
                    '-f', 'rvz',
                    '-c', 'zstd',
                    '-l', '5',
                    '-b', '131072',
                    '-i', fullIsoPath,
                    '-o', outputRvzPath
                ]);
                let errorOutput = '';

                dolphinTool.stdout.on('data', data => sendLog(`DolphinTool stdout: ${data}`));
                dolphinTool.stderr.on('data', data => {
                    errorOutput += data;
                    sendLog(`DolphinTool stderr: ${data}`);
                });
                dolphinTool.on('close', code => {
                    if (code === 0) {
                        sendLog(`Conversion terminée : ${iso} -> ${outputRvzPath}`);
                        convertedGames++;
                        resolve();
                    } else {
                        sendLog(`Erreur lors de la conversion de ${iso}: code ${code}`);
                        errorCount++;
                        reject(new Error(errorOutput));
                    }
                });
            });
        }

        sendLog('Nettoyage des fichiers extraits...');
        sendProgress(80, `Nettoyage`);
        for (let i = 0; i < allIsos.length; i++) {
            const iso = allIsos[i];
            const fullIsoPath = path.join(source, iso);
            if (fs.existsSync(fullIsoPath)) {
                await fsPromises.unlink(fullIsoPath);
                sendLog(`Fichier ISO supprimé : ${fullIsoPath}`);
            }
        }

        const duration = (Date.now() - startTime) / 1000;
        sendLog(`Conversion RVZ terminée en ${duration}s`);
        sendLog(`Jeux convertis : ${convertedGames}`);
        sendLog(`Jeux ignorés : ${skippedGames}`);
        sendLog(`Erreurs : ${errorCount}`);

        return {
            summary: { convertedGames, skippedGames, errorCount }
        };
    } catch (error) {
        sendLog(`Erreur lors de la conversion RVZ: ${error.message}`);
        errorCount++;
        throw error;
    } finally {
        sendProgress(100, `Terminé`);
    }
});