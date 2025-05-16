// renderer.js
const logDir = window.electronAPI.getLogDir(); // Obtenir logDir depuis preload.js
// Générer le timestamp en heure locale
const now = new Date();
const year = now.getFullYear();
const month = String(now.getMonth() + 1).padStart(2, '0'); // Mois de 0 à 11, donc +1
const day = String(now.getDate()).padStart(2, '0');
const hours = String(now.getHours()).padStart(2, '0');
const minutes = String(now.getMinutes()).padStart(2, '0');
const timestamp = `${year}-${month}-${day}_${hours}h${minutes}`;
let logFilePath = `${logDir}/LOG-${timestamp}.txt`;

document.getElementById('selectSourceFolder').addEventListener('click', selectSourceFolder);
document.getElementById('selectDestinationFolder').addEventListener('click', selectDestinationFolder);
document.getElementById('convertToChdv5').addEventListener('click', convertToChdv5);
document.getElementById('patchXboxIso').addEventListener('click', patchXboxIso);
document.getElementById('openLogFolder').addEventListener('click', openLogFolder);
document.getElementById('closeLogModal').addEventListener('click', closeLogModal);

// Écouter les messages de log
window.electronAPI.onLogMessage((message) => {
    console.log('Log reçu dans renderer:', message); // Débogage
    const logContent = document.getElementById('logContent');
    if (logContent) {
        logContent.innerHTML += `<p>${message}</p>`;
        logContent.scrollTop = logContent.scrollHeight;
        appendLog(message); // Appeler appendLog pour écrire dans le fichier
    } else {
        console.error('Élément logContent non trouvé');
    }
});

// Écouter les mises à jour de progression
window.electronAPI.onProgressUpdate(({ percent, message, current, total }) => {
    updateProgress(percent, message, current, total);
});

// Mettre à jour la version dans le footer
window.addEventListener('DOMContentLoaded', () => {
    const versionElement = document.querySelector('footer');
    if (versionElement) {
        const appVersion = window.electronAPI.getAppVersion();
        versionElement.innerHTML = `RetroGameSets 2025 // Version ${appVersion} // <a href="#" class="text-blue-500">AIDE - INSTRUCTIONS</a>`;
    } else {
        console.error('Élément footer non trouvé');
    }
});



function updateButtonStates() {
    const source = document.getElementById('sourceFolder').value;
    const destination = document.getElementById('destinationFolder').value;
    const patchButton = document.getElementById('patchXboxIso');
    const chdButton = document.getElementById('convertToChdv5');
    const buttons = [patchButton, chdButton];
    buttons.forEach(button => {
        button.disabled = !(source && destination);
    });
}

document.getElementById('sourceFolder').addEventListener('input', updateButtonStates);
document.getElementById('destinationFolder').addEventListener('input', updateButtonStates);

async function selectSourceFolder() {
    const folder = await window.electronAPI.selectSourceFolder();
    if (folder) {
        document.getElementById('sourceFolder').value = folder;
        updateButtonStates();
    }
}

async function selectDestinationFolder() {
    const folder = await window.electronAPI.selectDestinationFolder();
    if (folder) {
        document.getElementById('destinationFolder').value = folder;
        updateButtonStates();
    }
}

function showLogModal(functionName) {
    const logModal = document.getElementById('logModal');
    if (logModal) {
        logModal.classList.remove('hidden');
        const logContent = document.getElementById('logContent');
        if (logContent) {
            logContent.innerHTML = ''; // Réinitialiser le contenu
        }
        updateProgress(0, 'Initialisation...');
    } else {
        console.error('Modal logModal non trouvé');
    }
}

function closeLogModal() {
    const logModal = document.getElementById('logModal');
    if (logModal) {
        logModal.classList.add('hidden');
    } else {
        console.error('Modal logModal non trouvé');
    }
}

async function appendLog(message) {
    const logContent = document.getElementById('logContent');
    if (logContent) {
        // Suppression de la mise à jour du DOM ici, car déjà fait dans onLogMessage
        if (logFilePath) {
            try {
                await window.electronAPI.writeLog(logFilePath, message);
                console.log('Log écrit dans:', logFilePath); // Débogage
            } catch (err) {
                console.error('Erreur écriture log:', err);
            }
        }
    } else {
        console.error('Élément logContent non trouvé');
    }
}

function updateProgress(percentage, stepMessage = 'Progression :', currentStep = 0, totalSteps = 0) {
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    const progressLabel = document.getElementById('progressLabel');
    if (progressBar && progressText && progressLabel) {
        percentage = Math.min(100, Math.max(0, percentage));
        progressBar.style.width = `${percentage}%`;
        progressText.textContent = `${Math.round(percentage)}%`;
        progressLabel.textContent = totalSteps > 0 ? `${stepMessage} (${currentStep}/${totalSteps})` : stepMessage;
        console.log(`Reçu progression: ${stepMessage} (${currentStep}/${totalSteps}) - ${percentage}%`);
    } else {
        console.error('Un élément de progression est manquant');
    }
}

async function openLogFolder() {
    try {
        await window.electronAPI.openLogFolder();
        console.log('Dossier LOG ouvert');
    } catch (err) {
        console.error('Erreur ouverture dossier LOG:', err);
    }
}

async function patchXboxIso() {
    const source = document.getElementById('sourceFolder').value;
    const destination = document.getElementById('destinationFolder').value;
    if (!source || !destination) return alert('Veuillez sélectionner les dossiers source et destination.');
    alert('Cette fonction permet de patcher vos ISO XBOX pour Xemu');
    showLogModal('Patch-XBOX-ISO-XEMU');
    try {
        const result = await window.electronAPI.patchXboxIso(source, destination);
        updateProgress(100, 'Conversion terminée');
        const { convertedGames, optimizedGames, ignoredArchives, errorCount } = result.summary;
        if (errorCount > 0) {
            alert(`Opération terminée avec ${errorCount} erreur(s). Consultez le journal pour plus de détails.`);
        } else {
            alert('Tous les jeux sont convertis, y\'a plus qu\'à jouer :D');
        }
    } catch (error) {
        appendLog(`Erreur: ${error.message}`);
        alert(`Erreur: ${error.message}`);
    }
}

async function convertToChdv5() {
    const source = document.getElementById('sourceFolder').value;
    const destination = document.getElementById('destinationFolder').value;
    if (!source || !destination) return alert('Veuillez sélectionner les dossiers source et destination.');
    showLogModal('Conversion en CHDv5');
    try {
        const result = await window.electronAPI.convertToChdv5(source, destination);
        updateProgress(100, 'Conversion terminée');
        const { convertedGames, skippedGames, errorCount } = result.summary;
        if (errorCount > 0) {
            alert(`Opération terminée avec ${errorCount} erreur(s). Consultez le journal pour plus de détails.`);
        } else {
            alert('Tous les jeux sont convertis, y\'a plus qu\'à jouer :D');
        }
    } catch (error) {
        appendLog(`Erreur: ${error.message}`);
        alert(`Erreur: ${error.message}`);
    }
}

async function simpleConversion(actionName, modalTitle) {
    const source = document.getElementById('sourceFolder').value;
    const destination = document.getElementById('destinationFolder').value;
    if (!source || !destination) return alert('Veuillez sélectionner les dossiers source et destination.');
    showLogModal(modalTitle);
    try {
        await window.electronAPI[actionName](source, destination);
        appendLog('Opération terminée avec succès.');
        updateProgress(100, 'Opération terminée');
    } catch (error) {
        appendLog(`Erreur: ${error.message}`);
        alert(`Erreur: ${error.message}`);
    }
}

async function runUpdate() {
    showLogModal('Mise à jour');
    try {
        await window.electronAPI.runUpdate();
        appendLog('Mise à jour terminée avec succès.');
        updateProgress(100, 'Mise à jour terminée');
    } catch (error) {
        appendLog(`Erreur: ${error.message}`);
        alert(`Erreur: ${error.message}`);
    }
}