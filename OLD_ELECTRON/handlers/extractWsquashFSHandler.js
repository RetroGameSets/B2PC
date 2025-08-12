const path = require('path');
const fs = require('fs');
const fsPromises = require('fs').promises;
const { prepareDirectories, cleanupFiles } = require('../utils');
const { spawn } = require('child_process');

module.exports = (ipcMain, tools, sendLog, sendProgress, askCleanupConfirmation, mainWindow) => {
    ipcMain.handle('extract-wsquashfs', async (_, source, dest) => {
        const startTime = Date.now();
        const destination = await prepareDirectories(dest, 'Extracted_SquashFS', (msg) => sendLog(mainWindow, msg));
        let extractedFiles = 0, skippedFiles = 0, errorCount = 0;

        // Fonction pour convertir un chemin Windows en chemin POSIX
        function toPosixPath(winPath) {
            return winPath;
        }

        try {
            sendLog(mainWindow, `Dossier source: ${source}`);
            sendLog(mainWindow, `Dossier destination: ${destination}`);

            // Chemin vers unsquashfs.exe
            const unsquashfsPath = tools.unsquashfs;
            if (!fs.existsSync(unsquashfsPath)) {
                sendLog(mainWindow, `Erreur : unsquashfs.exe non trouvé à ${unsquashfsPath}`);
                throw new Error('unsquashfs.exe non trouvé');
            }

            // Lister les fichiers .wsquashfs
            const wsquashfsFiles = [];
            const files = await fsPromises.readdir(source, { withFileTypes: true });
            for (const file of files) {
                if (file.isFile() && path.extname(file.name).toLowerCase() === '.wsquashfs') {
                    wsquashfsFiles.push(path.join(source, file.name));
                }
            }
            sendLog(mainWindow, `Total des fichiers .wsquashfs trouvés : ${wsquashfsFiles.length}`);

            if (wsquashfsFiles.length === 0) {
                sendLog(mainWindow, 'Aucun fichier .wsquashfs trouvé dans le dossier source.');
                return { summary: { extractedFiles, skippedFiles, errorCount } };
            }

            // Vérifier les permissions d'écriture
            try {
                await fsPromises.access(destination, fs.constants.W_OK);
            } catch (error) {
                sendLog(mainWindow, `Erreur: Pas de permissions d'écriture dans ${destination}. Exécutez en tant qu'administrateur ou choisissez un autre dossier.`);
                throw new Error('Permissions insuffisantes pour écrire dans le dossier de destination');
            }

            // Boucle d'extraction avec progression
            sendProgress(mainWindow, 30, `Extraction en SquashFS`, 0, wsquashfsFiles.length, 0);
            for (let i = 0; i < wsquashfsFiles.length; i++) {
                const wsquashfsFile = wsquashfsFiles[i];
                const fileName = path.basename(wsquashfsFile, '.wsquashfs');
                const outputDir = path.join(destination, fileName);

                sendLog(mainWindow, `Extraction de ${fileName}.wsquashfs...`);
                sendProgress(mainWindow, 30 + (i / wsquashfsFiles.length) * 50, `Extraction en SquashFS`, i + 1, wsquashfsFiles.length, 0);

                // Vérifier si le dossier de sortie existe déjà
                if (fs.existsSync(outputDir)) {
                    sendLog(mainWindow, `Dossier déjà extrait, ignoré : ${fileName}`);
                    skippedFiles++;
                    continue;
                }

                // Convertir les chemins en format POSIX
                const wsquashfsFilePosix = toPosixPath(wsquashfsFile);
                const outputDirPosix = toPosixPath(outputDir);

                // Arguments pour unsquashfs (nouvelle version)
                const args = [
                    '--unpack-path', '/',        // Extraire tout le contenu
                    '--unpack-root', outputDirPosix, // Dossier de destination
                    wsquashfsFilePosix           // Fichier .wsquashfs
                ];

                sendLog(mainWindow, `Exécution de unsquashfs avec les arguments: ${args.join(' ')}`);

                try {
                    await new Promise((resolve, reject) => {
                        const process = spawn(unsquashfsPath, args, { cwd: destination });
                        let errorOutput = '';

                        process.stdout.on('data', (data) => {
                            const output = data.toString().trim();
                            if (output) {
                                sendLog(mainWindow, `unsquashfs stdout: ${output}`);
                            }
                        });

                        process.stderr.on('data', (data) => {
                            const error = data.toString().trim();
                            if (error) {
                                errorOutput += error + '\n';
                                sendLog(mainWindow, `unsquashfs stderr: ${error}`);
                            }
                        });

                        process.on('close', (code) => {
                            if (code === 0) {
                                resolve();
                            } else {
                                let errorMessage = errorOutput || `Échec avec code ${code}: Détails non disponibles`;
                                if (code === 3221225781) {
                                    errorMessage = `Échec avec code ${code}: DLL manquante (STATUS_DLL_NOT_FOUND). Vérifiez les dépendances de unsquashfs.exe.`;
                                }
                                reject(new Error(errorMessage));
                            }
                        });

                        process.on('error', (err) => {
                            reject(new Error(`Erreur de démarrage de unsquashfs: ${err.message}`));
                        });
                    });

                    // Vérifier si l'extraction a créé un dossier valide
                    if (fs.existsSync(outputDir)) {
                        const extractedContents = await fsPromises.readdir(outputDir);
                        if (extractedContents.length > 0) {
                            sendLog(mainWindow, `Extraction réussie : ${fileName}.wsquashfs -> ${outputDir}`);
                            extractedFiles++;
                        } else {
                            await fsPromises.rm(outputDir, { recursive: true, force: true }).catch(err =>
                                sendLog(mainWindow, `Erreur lors de la suppression de ${outputDir}: ${err.message}`)
                            );
                            sendLog(mainWindow, `Dossier vide supprimé : ${outputDir}`);
                        }
                    } else {
                        throw new Error('Dossier de sortie non créé');
                    }
                } catch (error) {
                    errorCount++;
                    sendLog(mainWindow, `Échec de l'extraction de ${fileName}: ${error.message}`);
                    if (fs.existsSync(outputDir)) {
                        await fsPromises.rm(outputDir, { recursive: true, force: true }).catch(err =>
                            sendLog(mainWindow, `Erreur lors de la suppression de ${outputDir}: ${err.message}`)
                        );
                    }
                    continue;
                }
            }

            const duration = (Date.now() - startTime) / 1000;
            sendLog(mainWindow, `Extraction terminée en ${duration}s`);
            sendLog(mainWindow, `Fichiers extraits : ${extractedFiles}`);
            sendLog(mainWindow, `Fichiers ignorés : ${skippedFiles}`);
            sendLog(mainWindow, `Erreurs : ${errorCount}`);

            // Demande de confirmation pour le nettoyage
            sendLog(mainWindow, 'Demande de confirmation pour le nettoyage des fichiers source...');
            const shouldCleanup = await askCleanupConfirmation();

            if (shouldCleanup) {
                sendLog(mainWindow, 'Nettoyage des fichiers source...');
                sendProgress(mainWindow, 80, `Nettoyage`, 0, 0, 0);
                await cleanupFiles(source, ['.wsquashfs'], (msg) => sendLog(mainWindow, msg), (progress, msg, ...args) => sendProgress(mainWindow, progress, msg, ...args));
                sendLog(mainWindow, 'Nettoyage terminé.');
            } else {
                sendLog(mainWindow, 'Nettoyage annulé par l’utilisateur.');
            }

            return { summary: { extractedFiles, skippedFiles, errorCount } };
        } catch (error) {
            sendLog(mainWindow, `Erreur lors de l'extraction SquashFS: ${error.message}`);
            errorCount++;
            throw error;
        } finally {
            sendProgress(mainWindow, 100, `Terminé`, 0, 0, 0);
        }
    });
};