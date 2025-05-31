const path = require('path');
const fs = require('fs');
const fsPromises = require('fs').promises;
const { prepareDirectories, cleanupFiles } = require('../utils');
const { runTool, validateTools } = require('../tools');

module.exports = (ipcMain, tools, sendLog, sendProgress, askCleanupConfirmation, mainWindow) => {
    ipcMain.handle('extract-chd', async (_, source, dest) => {
        const destination = await prepareDirectories(dest, 'Extracted_CHD', (msg) => sendLog(mainWindow, msg));
        let extractedGames = 0, skippedGames = 0, errorCount = 0;

        try {
            sendLog(mainWindow, `Dossier source: ${source}`);
            sendLog(mainWindow, `Dossier destination: ${destination}`);

            // Recherche des fichiers .chd
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

            sendLog(mainWindow, `Total des fichiers .chd trouvés : ${allChds.length}`);
            if (allChds.length === 0) {
                sendLog(mainWindow, 'Aucun fichier .chd trouvé pour l\'extraction. Assurez-vous que le dossier source contient des fichiers compatibles.');
                return { summary: { extractedGames, skippedGames, errorCount } };
            }

            try {
                await fsPromises.access(destination, fs.constants.W_OK);
            } catch (error) {
                sendLog(mainWindow, `Erreur: Pas de permissions d'écriture dans ${destination}. Exécutez en tant qu'administrateur ou choisissez un autre dossier.`);
                throw new Error('Permissions insuffisantes pour écrire dans le dossier de destination');
            }

            sendProgress(mainWindow, 30, `Extraction des fichiers CHD`, 0, allChds.length, 0);
            for (let i = 0; i < allChds.length; i++) {
                const chd = allChds[i].name;
                const fullChdPath = path.join(source, chd);
                const outputCuePath = path.join(destination, path.basename(chd, path.extname(chd)) + '.cue');
                const outputBinPath = path.join(destination, path.basename(chd, path.extname(chd)) + '.bin');
                sendLog(mainWindow, `Extraction de ${chd}...`);
                sendProgress(mainWindow, 30 + (i / allChds.length) * 50, `Extraction des fichiers CHD`, i + 1, allChds.length, 0);

                try {
                    const args = ['extractcd', '-i', fullChdPath, '-o', outputCuePath, '-ob', outputBinPath];
                    await runTool(
                        tools.chdman,
                        args,
                        destination,
                        chd,
                        allChds.length,
                        i,
                        'Extraction des fichiers CHD',
                        (msg) => sendLog(mainWindow, msg),
                        (progress, msg, ...args) => sendProgress(mainWindow, progress, msg, ...args)
                    );

                    if (fs.existsSync(outputCuePath) && fs.existsSync(outputBinPath)) {
                        const cueStats = fs.statSync(outputCuePath);
                        const binStats = fs.statSync(outputBinPath);
                        if (cueStats.size > 0 && binStats.size > 0) {
                            sendLog(mainWindow, `Extraction réussie : ${chd} -> ${outputCuePath} et ${outputBinPath}`);
                            extractedGames++;
                        } else {
                            await fsPromises.unlink(outputBinPath).catch(err => sendLog(mainWindow, `Erreur lors de la suppression de ${outputBinPath}: ${err.message}`));
                            sendLog(mainWindow, `Fichier .bin supprimé : ${outputBinPath}`);
                        }
                    }
                } catch (error) {
                    errorCount++;
                    sendLog(mainWindow, `Échec de l'extraction de ${chd}: ${error.message || error.stack || 'Aucune information disponible'}`);
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

            sendLog(mainWindow, `Extraction CHD terminée`);
            sendLog(mainWindow, `Jeux extraits : ${extractedGames}`);
            sendLog(mainWindow, `Jeux ignorés : ${skippedGames}`);
            sendLog(mainWindow, `Erreurs : ${errorCount}`);
            sendLog(mainWindow, 'Demande de confirmation pour le nettoyage des fichiers source...');
            const shouldCleanup = await askCleanupConfirmation();

            if (shouldCleanup) {
                sendLog(mainWindow, 'Nettoyage des fichiers extraits...');
                sendProgress(mainWindow, 80, `Nettoyage`);
                await cleanupFiles(source, ['.chd'], (msg) => sendLog(mainWindow, msg), (progress, msg, ...args) => sendProgress(mainWindow, progress, msg, ...args));
                sendLog(mainWindow, 'Nettoyage terminé.');
            } else {
                sendLog(mainWindow, 'Nettoyage annulé par l’utilisateur.');
            }
            return { summary: { extractedGames, skippedGames, errorCount } };
        } catch (error) {
            sendLog(mainWindow, `Erreur lors de l'extraction CHD: ${error.message || error.stack || 'Aucune information disponible'}`);
            errorCount++;
            throw error;
        } finally {
            sendProgress(mainWindow, 100, `Terminé`, 0, 0, 0);
        }
    });
};