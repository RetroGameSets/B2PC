// renderer.js

// Générer un logFilePath unique au démarrage
const logDir = 'C:\\Users\\Admin\\Desktop\\B2PC\\LOG';
const timestamp = new Date().toISOString().slice(0, 16).replace('T', '_').replace(/:/g, 'h');
let logFilePath = `${logDir}/LOG-${timestamp}.txt`;

// Gestion des boutons Parcourir
document.getElementById('selectSourceFolder').addEventListener('click', selectSourceFolder);
document.getElementById('selectDestinationFolder').addEventListener('click', selectDestinationFolder);

// Gestion des boutons de conversion
document.getElementById('mergeBinCue').addEventListener('click', mergeBinCue);
document.getElementById('convertToPbp').addEventListener('click', convertToPbp);
document.getElementById('convertToChdv5').addEventListener('click', convertToChdv5);
document.getElementById('extractChdToBin').addEventListener('click', extractChdToBin);
document.getElementById('convertWiiToWbfs').addEventListener('click', convertWiiToWbfs);
document.getElementById('zipAllRoms').addEventListener('click', zipAllRoms);
document.getElementById('patchXboxIso').addEventListener('click', patchXboxIso);

// Gestion des boutons du modal
document.getElementById('openLogFolder').addEventListener('click', openLogFolder);
document.getElementById('closeLogModal').addEventListener('click', closeLogModal);

// Gestion des onglets
const tabs = document.querySelectorAll('.tab-button');
const tabContents = document.querySelectorAll('.tab-content');

tabs.forEach(tab => {
    tab.addEventListener('click', () => {
        // Désactiver l'onglet actif
        tabs.forEach(t => {
            t.classList.remove('border-blue-500', 'text-blue-600');
            t.classList.add('border-transparent', 'text-gray-500', 'hover:text-gray-700', 'hover:border-gray-300');
        });
        tabContents.forEach(content => content.classList.add('hidden'));

        // Activer l'onglet cliqué
        tab.classList.remove('border-transparent', 'text-gray-500', 'hover:text-gray-700', 'hover:border-gray-300');
        tab.classList.add('border-blue-500', 'text-blue-600');
        document.getElementById(`content-${tab.id.replace('tab-', '')}`).classList.remove('hidden');
    });
});

// Fonctions de sélection
async function selectSourceFolder() {
    const folder = await window.electronAPI.selectSourceFolder();
    if (folder) document.getElementById('sourceFolder').value = folder;
}

async function selectDestinationFolder() {
    const folder = await window.electronAPI.selectDestinationFolder();
    if (folder) document.getElementById('destinationFolder').value = folder;
}

// Modal log
function showLogModal(functionName) {
    document.getElementById('logModal').classList.remove('hidden');
    document.getElementById('logContent').innerHTML = '';
    updateProgress(0, 'Initialisation...');
}

function closeLogModal() {
    document.getElementById('logModal').classList.add('hidden');
}

async function appendLog(message) {
    const logContent = document.getElementById('logContent');
    logContent.innerHTML += `<p>${message}</p>`;
    logContent.scrollTop = logContent.scrollHeight;
    if (logFilePath) {
        await window.electronAPI.writeLog(logFilePath, message).catch(console.error);
    }
}

function updateProgress(percentage, stepMessage = 'Progression :', currentStep = 0, totalSteps = 0) {
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    const progressLabel = document.getElementById('progressLabel');
    percentage = Math.min(100, Math.max(0, percentage));
    progressBar.style.width = `${percentage}%`;
    progressText.textContent = `${Math.round(percentage)}%`;
    progressLabel.textContent = totalSteps > 0 ? `${stepMessage} (${currentStep}/${totalSteps})` : stepMessage;
    console.log(`Reçu progression: ${stepMessage} (${currentStep}/${totalSteps}) - ${percentage}%`);
}

async function openLogFolder() {
    await window.electronAPI.openLogFolder().catch(console.error);
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

// Conversions simples
async function convertToPbp() { await simpleConversion('convertToPbp', 'Conversion en PBP'); }
async function mergeBinCue() { await simpleConversion('mergeBinCue', 'Fusion BIN/CUE'); }
async function convertToChdv5() { await simpleConversion('convertToChdv5', 'Conversion en CHDv5'); }
async function extractChdToBin() { await simpleConversion('extractChdToBin', 'Extraction CHD vers BIN'); }
async function convertWiiToWbfs() { await simpleConversion('convertWiiToWbfs', 'Conversion Wii en WBFS'); }
async function zipAllRoms() { await simpleConversion('zipAllRoms', 'Compression des ROMs'); }

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

// Log temps réel
window.addEventListener('DOMContentLoaded', () => {
    window.electronAPI.onLogMessage((message) => {
        appendLog(message);
    });
    window.electronAPI.onProgressUpdate?.(({ percent, current, total, message }) => {
        updateProgress(percent, message, current, total);
    });
});