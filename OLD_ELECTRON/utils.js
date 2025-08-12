const path = require('path');
const fs = require('fs');
const fsPromises = require('fs').promises;
const seven = require('node-7z');

async function extractArchives(sourceDir, sevenZipPath, extensions = ['.7z', '.zip', '.gz', '.rar'], targetExtensions = ['.cue', '.bin', '.gdi', '.iso'], sendLog, sendProgress) {
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
        if (sendLog) sendLog(`Vérification de ${file.name}...`);
        if (sendProgress) sendProgress((i / archives.length) * 10, `Analyse des archives`, i + 1, archives.length);
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
            if (sendLog) sendLog(`Archive ignorée (pas de fichiers cibles) : ${file.name}`);
        }
    }

    if (sendProgress) sendProgress(10, `Extraction des archives`);
    for (let i = 0; i < validArchives.length; i++) {
        const { file, fullPath, targets } = validArchives[i];
        if (sendLog) sendLog(`Extraction de ${file}...`);
        if (sendProgress) sendProgress(10 + (i / validArchives.length) * 20, `Extraction des archives`, i + 1, validArchives.length);
        await extractWith7z(fullPath, sourceDir, targets, sevenZipPath, sendLog);
        if (sendLog) sendLog(`Extraction terminée : ${file}`);
    }

    // Rafraîchir la liste des fichiers après extraction
    sourceFiles.length = 0; // Vider la liste précédente
    await walkDir(sourceDir);
    return sourceFiles.filter(f => targetExtensions.includes(path.extname(f.name).toLowerCase()));
}

async function extractWith7z(archivePath, destination, filesToExtract, sevenZipPath, sendLog) {
    return new Promise((resolve, reject) => {
        const outputArg = `-o${destination}`;
        const args = ['x', archivePath, '-y', outputArg, ...filesToExtract];
        const extraction = require('child_process').spawn(sevenZipPath, args, { cwd: destination });

        let errorOutput = '';
        extraction.stdout.on('data', data => { if (sendLog) sendLog(`7za stdout: ${data}`); });
        extraction.stderr.on('data', data => {
            errorOutput += data;
            if (sendLog) sendLog(`7za stderr: ${data}`);
        });
        extraction.on('close', code => {
            if (code === 0) {
                if (sendLog) sendLog(`Extraction terminée : ${archivePath} -> ${destination}`);
                resolve();
            } else {
                if (sendLog) sendLog(`Erreur lors de l'extraction de ${archivePath}: code ${code}`);
                reject(new Error(errorOutput));
            }
        });
        extraction.on('error', err => reject(err));
    });
}

async function prepareDirectories(dest, subFolder, sendLog) {
    const destination = dest.endsWith('\\') ? dest + subFolder : dest + '\\' + subFolder;
    await fsPromises.mkdir(destination, { recursive: true });
    if (sendLog) sendLog(`Dossier destination créé ou existant: ${destination}`);
    return destination;
}

async function cleanupFiles(sourceDir, extensionsToRemove, sendLog, sendProgress) {
    if (sendLog) sendLog('Nettoyage des fichiers extraits...');
    if (sendProgress) sendProgress(80, `Nettoyage`);
    const files = await fsPromises.readdir(sourceDir);
    for (const file of files) {
        if (extensionsToRemove.includes(path.extname(file).toLowerCase())) {
            const fullPath = path.join(sourceDir, file);
            await fsPromises.unlink(fullPath).catch(err => { if (sendLog) sendLog(`Erreur lors de la suppression de ${fullPath}: ${err.message}`); });
        }
    }
}

module.exports = {
    extractArchives,
    extractWith7z,
    prepareDirectories,
    cleanupFiles
};