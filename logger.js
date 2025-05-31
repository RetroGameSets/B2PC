function sendLog(mainWindow, msg) {
    if (mainWindow && msg) {
        const timestamp = new Date().toLocaleTimeString('fr-FR', { hour12: false });
        const logMessage = `${timestamp} - ${msg}`;
        mainWindow.webContents.send('log-message', logMessage);
    }
}

function sendProgress(mainWindow, totalProgress, message, currentFile = 0, totalFiles = 0, currentFileProgress = 0) {
    const progressMessage = totalFiles > 0 ? `${message} (${currentFile}/${totalFiles})` : message;
    mainWindow.webContents.send('progress-update', {
        totalProgress: Math.round(totalProgress * 10) / 10,
        currentFileProgress: Math.round(currentFileProgress * 10) / 10,
        message: progressMessage
    });
}

module.exports = { sendLog, sendProgress };