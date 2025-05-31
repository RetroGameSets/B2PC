const path = require('path');
const fs = require('fs');
const fsPromises = require('fs').promises;
const { prepareDirectories, cleanupFiles } = require('../utils');
const { spawn } = require('child_process');

module.exports = (ipcMain, tools, sendLog, sendProgress, askCleanupConfirmation, mainWindow) => {
    ipcMain.handle('compress-wsquashfs', async (_, source, dest, compressionLevel) => {
        const startTime = Date.now();
        const destination = await prepareDirectories(dest, 'Compressed_SquashFS', (msg) => sendLog(mainWindow, msg));
        let compressedFolders = 0, skippedFolders = 0, errorCount = 0;

        try {
            sendLog(mainWindow, `Dossier source: ${source}`);
            sendLog(mainWindow, `Dossier destination: ${destination}`);

            const gensquashfsPath = tools.gensquashfs;
            if (!fs.existsSync(gensquashfsPath)) {
                sendLog(mainWindow, `Erreur : gensquashfs.exe non trouvé à ${gensquashfsPath}`);
                throw new Error('gensquashfs.exe non trouvé');
            }

            const folders = [];
            const files = await fsPromises.readdir(source, { withFileTypes: true });
            for (const file of files) {
                if (file.isDirectory()) {
                    folders.push(path.join(source, file.name));
                }
            }
            sendLog(mainWindow, `Total des dossiers trouvés : ${folders.length}`);

            if (folders.length === 0) {
                sendLog(mainWindow, 'Aucun dossier trouvé dans le dossier source.');
                return { summary: { compressedFolders, skippedFolders, errorCount } };
            }

            try {
                await fsPromises.access(destination, fs.constants.W_OK);
            } catch (error) {
                sendLog(mainWindow, `Erreur: Pas de permissions d'écriture dans ${destination}.`);
                throw new Error('Permissions insuffisantes');
            }

            sendProgress(mainWindow, 30, `Compression en SquashFS`, 0, folders.length, 0);
            for (let i = 0; i < folders.length; i++) {
                const folder = folders[i];
                const folderName = path.basename(folder);
                const outputSquashfsPath = path.join(destination, `${folderName}.squashfs`);
                const outputWsquashfsPath = path.join(destination, `${folderName}.wsquashfs`);

                sendLog(mainWindow, `Compression de ${folderName}...`);
                sendProgress(mainWindow, 30 + (i / folders.length) * 50, `Compression en SquashFS`, i + 1, folders.length, 0);

                if (fs.existsSync(outputWsquashfsPath)) {
                    sendLog(mainWindow, `Dossier déjà compressé, ignoré : ${folderName}`);
                    skippedFolders++;
                    continue;
                }

                let compressor;
                switch (compressionLevel) {
                    case 'fast':
                        compressor = 'lz4';
                        break;
                    case 'medium':
                        compressor = 'zstd';
                        break;
                    case 'maximum':
                        compressor = 'xz';
                        break;
                    default:
                        throw new Error('Niveau de compression invalide');
                }

                const args = [
                    '--pack-dir', folder, outputSquashfsPath,
                    '--compressor', compressor,
                    '--block-size', '1048576',
                    '--num-jobs', '8'
                ];

                try {
                    await new Promise((resolve, reject) => {
                        const process = spawn(gensquashfsPath, args, { cwd: destination });
                        let errorOutput = '';

                        process.stdout.on('data', (data) => {
                            sendLog(mainWindow, `gensquashfs stdout: ${data.toString()}`);
                        });

                        process.stderr.on('data', (data) => {
                            errorOutput += data.toString();
                            sendLog(mainWindow, `gensquashfs stderr: ${data.toString()}`);
                        });

                        process.on('close', (code) => {
                            if (code === 0) resolve();
                            else reject(new Error(errorOutput || 'Erreur inconnue'));
                        });
                    });

                    if (fs.existsSync(outputSquashfsPath)) {
                        fs.renameSync(outputSquashfsPath, outputWsquashfsPath);
                        sendLog(mainWindow, `Compression réussie : ${folderName}.wsquashfs`);
                        compressedFolders++;
                    } else {
                        throw new Error('Fichier .squashfs non généré');
                    }
                } catch (error) {
                    errorCount++;
                    sendLog(mainWindow, `Échec de la compression de ${folderName}: ${error.message}`);
                    if (fs.existsSync(outputSquashfsPath)) fs.unlinkSync(outputSquashfsPath);
                }
            }

            const duration = (Date.now() - startTime) / 1000;
            sendLog(mainWindow, `Compression terminée en ${duration}s`);
            sendLog(mainWindow, `Dossiers compressés : ${compressedFolders}`);
            sendLog(mainWindow, `Dossiers ignorés : ${skippedFolders}`);
            sendLog(mainWindow, `Erreurs : ${errorCount}`);

            sendLog(mainWindow, 'Demande de confirmation pour le nettoyage...');
            const shouldCleanup = await askCleanupConfirmation();

            if (shouldCleanup) {
                sendLog(mainWindow, 'Nettoyage des dossiers source...');
                sendProgress(mainWindow, 80, `Nettoyage`, 0, 0, 0);
                for (const folder of folders) {
                    await fsPromises.rm(folder, { recursive: true, force: true }).catch(err =>
                        sendLog(mainWindow, `Erreur lors de la suppression de ${folder}: ${err.message}`)
                    );
                }
                sendLog(mainWindow, 'Nettoyage terminé.');
            } else {
                sendLog(mainWindow, 'Nettoyage annulé.');
            }

            return { summary: { compressedFolders, skippedFolders, errorCount } };
        } catch (error) {
            sendLog(mainWindow, `Erreur lors de la compression: ${error.message}`);
            errorCount++;
            throw error;
        } finally {
            sendProgress(mainWindow, 100, `Terminé`, 0, 0, 0);
        }
    });
};