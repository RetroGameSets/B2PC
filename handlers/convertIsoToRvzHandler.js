const path = require('path');
const fs = require('fs');
const fsPromises = require('fs').promises;
const { extractArchives, prepareDirectories, cleanupFiles } = require('../utils');
const { runTool, validateTools, checkIsoCompatibility } = require('../tools');

module.exports = (ipcMain, tools, sendLog, sendProgress, askCleanupConfirmation, mainWindow) => {
    ipcMain.handle('convert-iso-to-rvz', async (_, source, dest) => {
        const destination = await prepareDirectories(dest, 'RVZ', (msg) => sendLog(mainWindow, msg));
        let convertedGames = 0, skippedGames = 0, errorCount = 0;

        try {
            sendLog(mainWindow, 'Début de la conversion en RVZ...');
            sendLog(mainWindow, `Dossier source: ${source}`);
            sendLog(mainWindow, `Dossier destination: ${destination}`);
            await validateTools(tools, (msg) => sendLog(mainWindow, msg));

            const allIsos = await extractArchives(
                source,
                tools.sevenZip,
                ['.7z', '.zip', '.gz', '.rar'],
                ['.iso'],
                (msg) => sendLog(mainWindow, msg),
                (progress, msg, ...args) => sendProgress(mainWindow, progress, msg, ...args)
            );
            sendLog(mainWindow, `Total des fichiers .iso trouvés après extraction : ${allIsos.length}`);
            if (allIsos.length === 0) {
                sendLog(mainWindow, 'Aucun fichier .iso trouvé pour la conversion. Assurez-vous que le dossier source contient des fichiers compatibles.');
                return { summary: { convertedGames, skippedGames, errorCount } };
            }

            try {
                await fsPromises.access(destination, fs.constants.W_OK);
            } catch (error) {
                sendLog(mainWindow, `Erreur: Pas de permissions d'écriture dans ${destination}. Exécutez en tant qu'administrateur ou choisissez un autre dossier.`);
                throw new Error('Permissions insuffisantes pour écrire dans le dossier de destination');
            }

            sendProgress(mainWindow, 30, `Conversion en RVZ`, 0, allIsos.length);
            for (let i = 0; i < allIsos.length; i++) {
                const iso = allIsos[i].name;
                const fullIsoPath = path.join(source, iso);
                const outputRvzPath = path.join(destination, path.basename(iso, '.iso') + '.rvz');

                if (fs.existsSync(outputRvzPath)) {
                    sendLog(mainWindow, `Jeu déjà converti, ignoré : ${iso} -> ${outputRvzPath}`);
                    skippedGames++;
                    sendProgress(mainWindow, 30 + (i / allIsos.length) * 50, `Conversion en RVZ`, i + 1, allIsos.length);
                    continue;
                }

                // Vérification de la compatibilité
                const isCompatible = await checkIsoCompatibility(fullIsoPath, tools.dolphinTool, (msg) => sendLog(mainWindow, msg));
                if (!isCompatible) {
                    errorCount++;
                    sendLog(mainWindow, `Conversion ignorée pour ${iso} : incompatible avec RVZ`);
                    sendProgress(mainWindow, 30 + (i / allIsos.length) * 50, `Conversion en RVZ`, i + 1, allIsos.length);
                    continue;
                }

                sendProgress(mainWindow, 30 + (i / allIsos.length) * 50, `Conversion en RVZ`, i + 1, allIsos.length);
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
                    await runTool(
                        tools.dolphinTool,
                        args,
                        destination,
                        iso,
                        allIsos.length,
                        i,
                        'Conversion en RVZ',
                        (msg) => sendLog(mainWindow, msg),
                        (progress, msg, ...args) => sendProgress(mainWindow, progress, msg, ...args)
                    );

                    if (fs.existsSync(outputRvzPath)) {
                        const stats = fs.statSync(outputRvzPath);
                        if (stats.size > 0) {
                            sendLog(mainWindow, `Conversion réussie : ${iso} -> ${outputRvzPath}`);
                            convertedGames++;
                        } else {
                            await fsPromises.unlink(outputRvzPath).catch(err => sendLog(mainWindow, `Erreur lors de la suppression de ${outputRvzPath}: ${err.message}`));
                            throw new Error('Fichier .rvz généré mais vide ou invalide');
                        }
                    } else {
                        throw new Error('Fichier .rvz non généré');
                    }
                } catch (error) {
                    errorCount++;
                    sendLog(mainWindow, `Échec de la conversion de ${iso}: ${error.message || error.stack || 'Aucune information disponible'}`);
                    if (fs.existsSync(outputRvzPath)) {
                        await fsPromises.unlink(outputRvzPath).catch(err => sendLog(mainWindow, `Erreur lors de la suppression de ${outputRvzPath}: ${err.message}`));
                        sendLog(mainWindow, `Fichier .rvz supprimé : ${outputRvzPath}`);
                    }
                }
            }

            sendLog(mainWindow, `Conversion RVZ terminée`);
            sendLog(mainWindow, `Jeux convertis : ${convertedGames}`);
            sendLog(mainWindow, `Jeux ignorés : ${skippedGames}`);
            sendLog(mainWindow, `Erreurs : ${errorCount}`);

            sendLog(mainWindow, 'Demande de confirmation pour le nettoyage des fichiers source...');
            const shouldCleanup = await askCleanupConfirmation();

            if (shouldCleanup) {
                sendLog(mainWindow, 'Nettoyage des fichiers extraits...');
                sendProgress(mainWindow, 80, `Nettoyage`);
                await cleanupFiles(source, ['.iso'], (msg) => sendLog(mainWindow, msg), (progress, msg, ...args) => sendProgress(mainWindow, progress, msg, ...args));
                sendLog(mainWindow, 'Nettoyage terminé.');
            } else {
                sendLog(mainWindow, 'Nettoyage annulé par l’utilisateur.');
            }

            return { summary: { convertedGames, skippedGames, errorCount } };
        } catch (error) {
            sendLog(mainWindow, `Erreur lors de la conversion RVZ: ${error.message || error.stack || 'Aucune information disponible'}`);
            errorCount++;
            throw error;
        } finally {
            sendProgress(mainWindow, 100, `Terminé`);
        }
    });
};