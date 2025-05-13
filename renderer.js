const logDir = 'C:\\Users\\Admin\\Desktop\\B2PC\\LOG';
const timestamp = new Date().toISOString().slice(0, 16).replace('T', '_').replace(/:/g, 'h');
let logFilePath = `${logDir}/LOG-${timestamp}.txt`;

document.getElementById('selectSourceFolder').addEventListener('click', selectSourceFolder);
document.getElementById('selectDestinationFolder').addEventListener('click', selectDestinationFolder);
document.getElementById('mergeBinCue').addEventListener('click', mergeBinCue);
document.getElementById('convertToPbp').addEventListener('click', convertToPbp);
document.getElementById('convertToChdv5').addEventListener('click', convertToChdv5);
document.getElementById('extractChdToBin').addEventListener('click', extractChdToBin);
document.getElementById('convertWiiToWbfs').addEventListener('click', convertWiiToWbfs);
document.getElementById('zipAllRoms').addEventListener('click', zipAllRoms);
document.getElementById('patchXboxIso').addEventListener('click', patchXboxIso);
document.getElementById('runUpdate').addEventListener('click', runUpdate);
document.getElementById('openLogFolder').addEventListener('click', openLogFolder);
document.getElementById('closeLogModal').addEventListener('click', closeLogModal);

const tabs = document.querySelectorAll('.tab-button');
const tabContents = document.querySelectorAll('.tab-content');

function setActiveTab(tab) {
    console.log(`Activation onglet: ${tab.id}`);
    tabs.forEach(t => {
        t.classList.remove('border-blue-500', 'text-blue-600', 'active');
        t.classList.add('border-transparent', 'text-gray-500', 'hover:text-gray-700', 'hover:border-gray-300');
    });
    tabContents.forEach(content => {
        content.classList.add('hidden');
        content.classList.remove('active');
    });
    tab.classList.remove('border-transparent', 'text-gray-500', 'hover:text-gray-700', 'hover:border-gray-300');
    tab.classList.add('border-blue-500', 'text-blue-600', 'active');
    const content = document.getElementById(`content-${tab.id.replace('tab-', '')}`);
    content.classList.remove('hidden');
    content.classList.add('active');
}

tabs.forEach(tab => {
    tab.addEventListener('click', () => setActiveTab(tab));
});

window.addEventListener('DOMContentLoaded', () => {
    console.log('DOM chargé, tabs:', tabs.length);
    const conversionTab = document.getElementById('tab-conversion');
    if (conversionTab) {
        setActiveTab(conversionTab);
    } else {
        console.error('Onglet tab-conversion non trouvé');
    }
    updateButtonStates();
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

async function convertToChdv5() {
    const source = document.getElementById('sourceFolder').value;
    const destination = document.getElementById('destinationFolder').value;
    if (!source || !destination) return alert('Veuillez sélectionner les dossiers source et destination.');
    alert('Attention, CHDv5 peut ne pas être compatible avec certains émulateurs');
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

async function convertToPbp() { await simpleConversion('convertToPbp', 'Conversion en PBP'); }
async function mergeBinCue() { await simpleConversion('mergeBinCue', 'Fusion BIN/CUE'); }
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

window.addEventListener('DOMContentLoaded', () => {
    window.electronAPI.onLogMessage((message) => {
        appendLog(message);
    });
    window.electronAPI.onProgressUpdate?.(({ percent, current, total, message }) => {
        updateProgress(percent, message, current, total);
    });
});