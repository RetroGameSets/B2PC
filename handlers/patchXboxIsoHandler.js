const path = require('path');
const fs = require('fs');
const fsPromises = require('fs').promises;
const { extractArchives, prepareDirectories, cleanupFiles } = require('../utils');
const { runTool, validateTools } = require('../tools');

module.exports = (ipcMain, tools, sendLog, sendProgress, askCleanupConfirmation, mainWindow) => {
    ipcMain.handle('patch-xbox-iso', async (_, source, dest) => {
        const destination = await prepareDirectories(dest, 'xbox', (msg) => sendLog(mainWindow, msg));
        let convertedGames = 0, optimizedGames = 0, ignoredArchives = 0, errorCount = 0;

        try {
            sendLog(mainWindow, 'Début du patch Xbox...');
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
            sendProgress(mainWindow, 30, `Patch des ISO`);

            for (let i = 0; i < allIsos.length; i++) {
                const iso = allIsos[i].name;
                const fullIsoPath = path.join(source, iso);
                const fileName = path.basename(iso, '.iso');
                const destIsoPath = path.join(destination, iso);
                const destIsoOldPath = destIsoPath + '.old';

                // Copie l'ISO dans le dossier destination AVANT patch
                await fsPromises.copyFile(fullIsoPath, destIsoPath);

                // Supprime le .iso.old s'il existe dans le dossier destination
                if (fs.existsSync(destIsoOldPath)) {
                    await fsPromises.unlink(destIsoOldPath);
                    sendLog(mainWindow, `Ancien backup supprimé : ${destIsoOldPath}`);
                }

                sendProgress(mainWindow, 30 + (i / allIsos.length) * 50, `Patch des ISO`, i + 1, allIsos.length);

                await fsPromises.copyFile(tools.xiso, path.join(destination, 'xiso.exe'));
                await runTool(
                    path.join(destination, 'xiso.exe'),
                    ['-r', destIsoPath],
                    destination,
                    fileName,
                    allIsos.length,
                    i,
                    'Patch des ISO',
                    (msg) => sendLog(mainWindow, msg),
                    (progress, msg, ...args) => sendProgress(mainWindow, progress, msg, ...args)
                );
                const patchedIso = path.join(destination, fileName + '_patched.iso');
                if (fs.existsSync(patchedIso)) {
                    const statsBefore = fs.statSync(destIsoPath);
                    const statsAfter = fs.statSync(patchedIso);
                    if (statsAfter.size < statsBefore.size) {
                        sendLog(mainWindow, `Optimisation détectée pour ${fileName}: ${statsBefore.size} -> ${statsAfter.size}`);
                        optimizedGames++;
                    }
                }
                convertedGames++;
            }

            if (fs.existsSync(path.join(destination, 'xiso.exe'))) {
                await fsPromises.unlink(path.join(destination, 'xiso.exe')).catch(err => sendLog(mainWindow, `Erreur lors de la suppression de xiso.exe: ${err.message}`));
                sendLog(mainWindow, `xiso.exe supprimé de ${destination}`);
            }
            const filesInDest = await fsPromises.readdir(destination);
            for (const file of filesInDest) {
                if (file.endsWith('.iso.old')) {
                    const oldPath = path.join(destination, file);
                    await fsPromises.unlink(oldPath).catch(err => sendLog(mainWindow, `Erreur lors de la suppression de ${oldPath}: ${err.message}`));
                    sendLog(mainWindow, `Fichier .iso.old supprimé : ${oldPath}`);
                }
            }

            sendLog(mainWindow, `Patch Xbox terminé`);
            sendLog(mainWindow, `Jeux convertis : ${convertedGames}`);
            sendLog(mainWindow, `Jeux optimisés : ${optimizedGames}`);
            sendLog(mainWindow, `Archives ignorées : ${ignoredArchives}`);
            sendLog(mainWindow, `Erreurs : ${errorCount}`);

            sendLog(mainWindow, 'Demande de confirmation pour le nettoyage des fichiers source...');
            const shouldCleanup = await askCleanupConfirmation();

            if (shouldCleanup) {
                sendLog(mainWindow, 'Nettoyage des fichiers extraits...');
                sendProgress(mainWindow, 80, `Nettoyage`);
                await cleanupFiles(source, ['.iso', '.old'], (msg) => sendLog(mainWindow, msg), (progress, msg, ...args) => sendProgress(mainWindow, progress, msg, ...args));
                sendLog(mainWindow, 'Nettoyage terminé.');
            } else {
                sendLog(mainWindow, 'Nettoyage annulé par l’utilisateur.');
            }

            return { summary: { convertedGames, optimizedGames, ignoredArchives, errorCount } };
        } catch (error) {
            sendLog(mainWindow, `Erreur lors du patch Xbox: ${error.message}`);
            errorCount++;
            throw error;
        } finally {
            sendProgress(mainWindow, 100, `Terminé`);
        }
    });
};