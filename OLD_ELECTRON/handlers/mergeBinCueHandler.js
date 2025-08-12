const path = require('path');
const fs = require('fs');
const fsPromises = require('fs').promises;
const { extractArchives, prepareDirectories, cleanupFiles } = require('../utils');
const { runTool, validateTools } = require('../tools');

module.exports = (ipcMain, tools, sendLog, sendProgress, askCleanupConfirmation, mainWindow) => {
    ipcMain.handle('merge-bin-cue', async (_, source, dest) => {
        const tempChdDir = await prepareDirectories(dest, 'Temp_CHD', (msg) => sendLog(mainWindow, msg));
        const finalDir = await prepareDirectories(dest, 'Merged_CUE', (msg) => sendLog(mainWindow, msg));
        let mergedGames = 0, skippedGames = 0, errorCount = 0;

        try {
            sendLog(mainWindow, 'Début de la fusion des fichiers BIN/CUE...');
            sendLog(mainWindow, `Dossier source: ${source}`);
            sendLog(mainWindow, `Dossier temporaire pour CHD: ${tempChdDir}`);
            sendLog(mainWindow, `Dossier destination final: ${finalDir}`);
            await validateTools(tools, (msg) => sendLog(mainWindow, msg));

            // Extraction des .cue et .bin
            const allCues = await extractArchives(
                source,
                tools.sevenZip,
                ['.7z', '.zip', '.gz', '.rar'],
                ['.cue', '.bin'],
                (msg) => sendLog(mainWindow, msg),
                (progress, msg, ...args) => sendProgress(mainWindow, progress, msg, ...args)
            );
            sendLog(mainWindow, `Total des fichiers .cue et .bin trouvés après extraction : ${allCues.length}`);
            if (allCues.length === 0) {
                sendLog(mainWindow, 'Aucun fichier .cue ou .bin trouvé pour la fusion. Assurez-vous que le dossier source contient des fichiers compatibles.');
                return { summary: { mergedGames, skippedGames, errorCount } };
            }

            // Filtrer les .cue multi-bin
            const multiBinCues = [];
            for (const cue of allCues.filter(f => path.extname(f.name).toLowerCase() === '.cue')) {
                const cueContent = await fsPromises.readFile(cue.fullPath, 'utf-8');
                const binFiles = cueContent.match(/FILE\s+"([^"]+\.bin)"/gi);
                if (binFiles && binFiles.length > 1) {
                    const cueDir = path.dirname(cue.fullPath);
                    const binNames = binFiles.map(match => match.match(/"([^"]+)"/)[1].toLowerCase());
                    const allBinsPresent = binNames.every(binName => allCues.some(f => path.basename(f.name).toLowerCase() === binName && path.dirname(f.fullPath) === cueDir));
                    if (allBinsPresent) {
                        multiBinCues.push(cue);
                        sendLog(mainWindow, `Fichier .cue avec plusieurs .bin détecté : ${cue.name} (tous les .bin trouvés)`);
                    } else {
                        sendLog(mainWindow, `Fichier .cue ignoré : ${cue.name} (certains .bin manquants)`);
                        skippedGames++;
                    }
                } else {
                    sendLog(mainWindow, `Fichier .cue avec un seul .bin, ignoré : ${cue.name}`);
                    skippedGames++;
                }
            }

            sendLog(mainWindow, `Total des fichiers .cue avec plusieurs .bin trouvés : ${multiBinCues.length}`);
            if (multiBinCues.length === 0) {
                sendLog(mainWindow, 'Aucun fichier .cue avec plusieurs .bin trouvé pour la fusion.');
                return { summary: { mergedGames, skippedGames, errorCount } };
            }

            try {
                await fsPromises.access(tempChdDir, fs.constants.W_OK);
                await fsPromises.access(finalDir, fs.constants.W_OK);
            } catch (error) {
                sendLog(mainWindow, `Erreur: Pas de permissions d'écriture dans ${tempChdDir} ou ${finalDir}. Exécutez en tant qu'administrateur ou choisissez un autre dossier.`);
                throw new Error('Permissions insuffisantes pour écrire dans le dossier de destination');
            }

            // Conversion en CHD
            sendProgress(mainWindow, 30, `Conversion en CHD pour fusion`, 0, multiBinCues.length, 0);
            for (let i = 0; i < multiBinCues.length; i++) {
                const cue = multiBinCues[i].name;
                const fullCuePath = multiBinCues[i].fullPath;
                const outputChdPath = path.join(tempChdDir, path.basename(cue, '.cue') + '.chd');
                sendLog(mainWindow, `Conversion de ${cue} en CHD...`);
                sendProgress(mainWindow, 30 + (i / multiBinCues.length) * 25, `Conversion en CHD pour fusion`, i + 1, multiBinCues.length, 0);

                if (fs.existsSync(outputChdPath)) {
                    sendLog(mainWindow, `Fichier CHD déjà existant, ignoré : ${cue} -> ${outputChdPath}`);
                    continue;
                }

                try {
                    const args = ['createcd', '-i', fullCuePath, '-o', outputChdPath];
                    await runTool(
                        tools.chdman,
                        args,
                        tempChdDir,
                        cue,
                        multiBinCues.length,
                        i,
                        'Conversion en CHD pour fusion',
                        (msg) => sendLog(mainWindow, msg),
                        (progress, msg, ...args) => sendProgress(mainWindow, progress, msg, ...args)
                    );

                    if (fs.existsSync(outputChdPath)) {
                        const stats = fs.statSync(outputChdPath);
                        if (stats.size > 0) {
                            sendLog(mainWindow, `Conversion réussie : ${cue} -> ${outputChdPath}`);
                        } else {
                            await fsPromises.unlink(outputChdPath).catch(err => sendLog(mainWindow, `Erreur lors de la suppression de ${outputChdPath}: ${err.message}`));
                            throw new Error('Fichier .chd généré mais vide ou invalide');
                        }
                    } else {
                        throw new Error('Fichier .chd non généré');
                    }
                } catch (error) {
                    errorCount++;
                    sendLog(mainWindow, `Échec de la conversion de ${cue} en CHD: ${error.message || error.stack || 'Aucune information disponible'}`);
                    if (fs.existsSync(outputChdPath)) {
                        await fsPromises.unlink(outputChdPath).catch(err => sendLog(mainWindow, `Erreur lors de la suppression de ${outputChdPath}: ${err.message}`));
                        sendLog(mainWindow, `Fichier .chd supprimé : ${outputChdPath}`);
                    }
                    continue;
                }
            }

            // Extraction des CHD en CUE/BIN fusionné
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

            sendLog(mainWindow, `Total des fichiers .chd à extraire pour fusion : ${allChds.length}`);
            sendProgress(mainWindow, 55, `Extraction CHD pour fusion`, 0, allChds.length, 0);
            for (let i = 0; i < allChds.length; i++) {
                const chd = allChds[i].name;
                const fullChdPath = allChds[i].fullPath;
                const outputCuePath = path.join(finalDir, path.basename(chd, path.extname(chd)) + '.cue');
                const outputBinPath = path.join(finalDir, path.basename(chd, path.extname(chd)) + '.bin');
                sendLog(mainWindow, `Extraction de ${chd} pour fusion...`);
                sendProgress(mainWindow, 55 + (i / allChds.length) * 25, `Extraction CHD pour fusion`, i + 1, allChds.length, 0);

                try {
                    const args = ['extractcd', '-i', fullChdPath, '-o', outputCuePath, '-ob', outputBinPath];
                    await runTool(
                        tools.chdman,
                        args,
                        finalDir,
                        chd,
                        allChds.length,
                        i,
                        'Extraction CHD pour fusion',
                        (msg) => sendLog(mainWindow, msg),
                        (progress, msg, ...args) => sendProgress(mainWindow, progress, msg, ...args)
                    );

                    if (fs.existsSync(outputCuePath) && fs.existsSync(outputBinPath)) {
                        const cueStats = fs.statSync(outputCuePath);
                        const binStats = fs.statSync(outputBinPath);
                        if (cueStats.size > 0 && binStats.size > 0) {
                            sendLog(mainWindow, `Fusion réussie : ${chd} -> ${outputCuePath} et ${outputBinPath}`);
                            mergedGames++;
                        } else {
                            await fsPromises.unlink(outputCuePath).catch(err => sendLog(mainWindow, `Erreur lors de la suppression de ${outputCuePath}: ${err.message}`));
                            await fsPromises.unlink(outputBinPath).catch(err => sendLog(mainWindow, `Erreur lors de la suppression de ${outputBinPath}: ${err.message}`));
                            throw new Error('Fichiers .cue ou .bin générés mais vides ou invalides');
                        }
                    } else {
                        throw new Error('Fichiers .cue ou .bin non générés');
                    }
                } catch (error) {
                    errorCount++;
                    sendLog(mainWindow, `Échec de l'extraction de ${chd} pour fusion: ${error.message || error.stack || 'Aucune information disponible'}`);
                    if (fs.existsSync(outputCuePath)) {
                        await fsPromises.unlink(outputCuePath).catch(err => sendLog(mainWindow, `Erreur lors de la suppression de ${outputCuePath}: ${err.message}`));
                        sendLog(mainWindow, `Fichier .cue supprimé : ${outputCuePath}`);
                    }
                    if (fs.existsSync(outputBinPath)) {
                        await fsPromises.unlink(outputBinPath).catch(err => sendLog(mainWindow, `Erreur lors de la suppression de ${outputBinPath}: ${err.message}`));
                        sendLog(mainWindow, `Fichier .bin supprimé : ${outputBinPath}`);
                    }
                    continue;
                }
            }

            sendLog(mainWindow, `Fusion BIN/CUE terminée`);
            sendLog(mainWindow, `Jeux fusionnés : ${mergedGames}`);
            sendLog(mainWindow, `Jeux ignorés : ${skippedGames}`);
            sendLog(mainWindow, `Erreurs : ${errorCount}`);

            sendLog(mainWindow, 'Demande de confirmation pour le nettoyage des fichiers source...');
            const shouldCleanup = await askCleanupConfirmation();

            if (shouldCleanup) {
                sendLog(mainWindow, 'Nettoyage des fichiers extraits et temporaires...');
                sendProgress(mainWindow, 80, `Nettoyage`);
                await cleanupFiles(source, ['.cue', '.bin'], (msg) => sendLog(mainWindow, msg), (progress, msg, ...args) => sendProgress(mainWindow, progress, msg, ...args));
                await cleanupFiles(tempChdDir, ['.chd'], (msg) => sendLog(mainWindow, msg), (progress, msg, ...args) => sendProgress(mainWindow, progress, msg, ...args));
                sendLog(mainWindow, 'Nettoyage terminé.');
            } else {
                sendLog(mainWindow, 'Nettoyage annulé par l’utilisateur.');
            }

            return { summary: { mergedGames, skippedGames, errorCount } };
        } catch (error) {
            sendLog(mainWindow, `Erreur lors de la fusion BIN/CUE: ${error.message || error.stack || 'Aucune information disponible'}`);
            errorCount++;
            throw error;
        } finally {
            sendProgress(mainWindow, 100, `Terminé`, 0, 0, 0);
        }
    });
};