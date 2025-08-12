const path = require('path');
const fs = require('fs');
const fsPromises = require('fs').promises;
const { spawn } = require('child_process');

async function runTool(toolPath, args, workingDir, fileName, totalFiles, fileIndex, operation, sendLog, sendProgress) {
    return new Promise((resolve, reject) => {
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
                if (line.includes('successfully rewritten') && sendLog) {
                    sendLog(`${path.basename(toolPath)} [${fileName}]: ${line}`);
                }
            }
        });

        tool.stderr.on('data', data => {
            const lines = data.toString().split('\n').filter(Boolean);
            for (const line of lines) {
                errorOutput += line + '\n';

                // Gestion des messages de progression pour chdman.exe (createcd ou extractcd)
                if (path.basename(toolPath).toLowerCase() === 'chdman.exe') {
                    const percentageMatch = line.match(/(\w+,\s*(\d+\.\d+)%\s*complete)/i);
                    if (percentageMatch && percentageMatch[2]) {
                        const percentage = parseFloat(percentageMatch[2]);
                        if (totalFiles > 0 && fileIndex >= 0 && sendProgress) {
                            const baseProgress = 30 + (fileIndex / totalFiles) * 50;
                            const fileProgress = (percentage / 100) * (50 / totalFiles);
                            sendProgress(baseProgress + fileProgress, operation, fileIndex + 1, totalFiles, percentage);
                        }
                    }
                    continue;
                }

                // Gestion des messages de progression pour dolphin-tool.exe
                if (path.basename(toolPath).toLowerCase() === 'dolphin-tool.exe' && line.includes('Compressing,')) {
                    const percentageMatch = line.match(/Compressing,\s*(\d+\.\d+)%\s*complete/);
                    if (percentageMatch) {
                        const percentage = parseFloat(percentageMatch[1]);
                        if (totalFiles > 0 && fileIndex >= 0 && sendProgress) {
                            const baseProgress = 30 + (fileIndex / totalFiles) * 50;
                            const fileProgress = (percentage / 100) * (50 / totalFiles);
                            sendProgress(baseProgress + fileProgress, operation, fileIndex + 1, totalFiles, percentage);
                        }
                    }
                    continue;
                }

                if (path.basename(toolPath).toLowerCase() === 'dolphin-tool.exe' && line.includes('The input file is not a GC/Wii disc image')) {
                    hasCriticalError = true;
                    if (sendLog) sendLog(`${path.basename(toolPath)} [${fileName}] Erreur critique: ${line}`);
                } else if (sendLog) {
                    sendLog(`${path.basename(toolPath)} [${fileName}] Erreur: ${line}`);
                }
            }
        });

        tool.on('close', code => {
            clearTimeout(timeout);
            if (code === 0 && !hasCriticalError) {
                resolve(stdoutOutput);
            } else {
                const errorMsg = hasCriticalError ? 'Fichier incompatible : non reconnu comme une image de disque GC/Wii' : (errorOutput || `Échec avec code ${code}`);
                if (sendLog) sendLog(`Erreur lors du traitement de ${fileName}: ${errorMsg}`);
                reject(new Error(errorMsg));
            }
        });

        tool.on('error', err => {
            clearTimeout(timeout);
            reject(err);
        });
    });
}

async function validateTools(tools, sendLog) {
    for (const [name, path] of Object.entries(tools)) {
        if (!fs.existsSync(path)) {
            if (sendLog) sendLog(`Erreur : ${name} non trouvé à ${path}`);
            throw new Error(`${name} non trouvé à ${path}`);
        }
    }
}

async function checkIsoCompatibility(isoPath, dolphinToolPath, sendLog) {
    return new Promise((resolve, reject) => {
        if (sendLog) sendLog(`Vérification de la compatibilité de ${path.basename(isoPath)} avec DolphinTool...`);
        const headerProcess = spawn(dolphinToolPath, ['header', '-i', isoPath]);
        let output = '';

        headerProcess.stdout.on('data', data => {
            output += data.toString();
        });

        headerProcess.stderr.on('data', data => {
            if (sendLog) sendLog(`DolphinTool header [${path.basename(isoPath)}] Erreur: ${data}`);
        });

        headerProcess.on('close', code => {
            if (code === 0 && output.trim().length > 0) {
                if (sendLog) sendLog(`ISO compatible : ${path.basename(isoPath)}`);
                resolve(true);
            } else {
                if (sendLog) sendLog(`ISO incompatible : ${path.basename(isoPath)} (pas une image GameCube/Wii)`);
                resolve(false);
            }
        });

        headerProcess.on('error', err => reject(err));
    });
}

module.exports = {
    runTool,
    validateTools,
    checkIsoCompatibility
};