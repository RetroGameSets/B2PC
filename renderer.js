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

// Stocker le résumé pour l’afficher dans un tableau
let summary = { convertedGames: 0, skippedGames: 0, errorCount: 0, duration: 0 };
let hasExtractionError = false;

document.getElementById('selectSourceFolder').addEventListener('click', selectSourceFolder);
document.getElementById('selectDestinationFolder').addEventListener('click', selectDestinationFolder);
document.getElementById('convertToChdv5').addEventListener('click', convertToChdv5);
document.getElementById('extractChd').addEventListener('click', extractChd);
document.getElementById('patchXboxIso').addEventListener('click', patchXboxIso);
document.getElementById('convertIsoToRvz').addEventListener('click', convertIsoToRvz);
document.getElementById('mergeBinCue').addEventListener('click', mergeBinCue);
document.getElementById('compressWsquashFS').addEventListener('click', compressWsquashFS);
document.getElementById('openLogFolder').addEventListener('click', openLogFolder);
document.getElementById('closeLogModal').addEventListener('click', closeLogModal);
document.getElementById('extractWsquashFS').addEventListener('click', extractWsquashFS);

// Écouter les messages de log
window.electronAPI.onLogMessage((message) => {
    console.log('Log reçu dans renderer:', message); // Débogage
    const logContent = document.getElementById('logContent');
    if (logContent) {
        let messageClass = 'bg-blue-100 text-blue-800';
        let icon = 'ℹ️'; // Icône par défaut pour les infos

        // Déterminer le type de message pour appliquer la bonne classe et icône
        if (
            (message.includes('Erreur') || message.includes('Échec')) &&
            !(message.includes('Compression complete') && message.includes('final ratio'))
        ) {
            messageClass = 'bg-red-100 text-red-800';
            icon = '❌';
            hasExtractionError = true; // Marquer une erreur si présente
        } else if (
            message.includes('Conversion réussie') ||
            message.includes('Traitement terminé') ||
            message.includes('Extraction terminée') ||
            message.includes('Nettoyage terminé') ||
            message.includes('Extraction réussie') ||
            message.includes('Fusion réussie') ||
            (message.includes('Compression complete') && message.includes('final ratio'))
        ) {
            messageClass = 'bg-green-100 text-green-800';
            icon = '✅';
        } else if (
            message.includes('Demande de confirmation') ||
            message.includes('Nettoyage annulé') ||
            message.includes('Jeu déjà converti') ||
            message.includes('Fichiers déjà extraits') ||
            message.includes('Fichier déjà converti') ||
            message.includes('Total des fichiers') ||
            message.includes('Dossier source') ||
            message.includes('Dossier destination') ||
            message.includes('Compressing,')
        ) {
            messageClass = 'bg-yellow-100 text-yellow-800';
            icon = '⏳';
        }

        // Extraire les informations du résumé
        if (message.includes('Conversion RVZ terminée en') || message.includes('Conversion CHD terminée en') || message.includes('Extraction CHD terminée en') || message.includes('Fusion BIN/CUE terminée en')) {
            const durationMatch = message.match(/terminée en (\d+\.\d+)s/);
            if (durationMatch) summary.duration = parseFloat(durationMatch[1]);
        } else if (message.includes('Jeux convertis :') || message.includes('Jeux extraits :') || message.includes('Jeux fusionnés :')) {
            const convertedMatch = message.match(/(?:Jeux convertis|Jeux extraits|Jeux fusionnés) : (\d+)/);
            if (convertedMatch) summary.convertedGames = parseInt(convertedMatch[1]);
        } else if (message.includes('Jeux ignorés :')) {
            const skippedMatch = message.match(/Jeux ignorés : (\d+)/);
            if (skippedMatch) summary.skippedGames = parseInt(skippedMatch[1]);
        } else if (message.includes('Erreurs :')) {
            const errorMatch = message.match(/Erreurs : (\d+)/);
            if (errorMatch) {
                summary.errorCount = parseInt(errorMatch[1]);
                // Afficher le tableau de résumé après avoir reçu le dernier élément (Erreurs)
                appendSummaryTable();
            }
        }

        // Filtrer les messages d'extraction si pas d'erreur
        if (
            !hasExtractionError &&
            (message.includes('Exécution de 7za.exe') ||
             message.includes('7za stdout:') ||
             message.includes('Extraction terminée :') && message.includes('->'))
        ) {
            return; // Ignorer ces messages si pas d'erreur
        }

        // Ajouter le message au contenu du log avec Tailwind
        logContent.innerHTML += `
            <div class="flex items-center gap-2 p-2 my-1 rounded ${messageClass}">
                <span class="text-lg">${icon}</span>
                <span>${message}</span>
            </div>
        `;
        logContent.scrollTop = logContent.scrollHeight;
        appendLog(message); // Appeler appendLog pour écrire dans le fichier
    } else {
        console.error('Élément logContent non trouvé');
    }
});

// Écouter les mises à jour de progression
window.electronAPI.onProgressUpdate((data) => {
    updateProgress(data.totalProgress, data.currentFileProgress, data.message);
});

// Mettre à jour la version dans le footer
window.addEventListener('DOMContentLoaded', () => {
    const versionElement = document.querySelector('footer');
    if (versionElement) {
        const appVersion = window.electronAPI.getAppVersion();
        versionElement.innerHTML = `RetroGameSets 2025 // Version ${appVersion}`;
    } else {
        console.error('Élément footer non trouvé');
    }
});

function updateButtonStates() {
    const source = document.getElementById('sourceFolder').value;
    const destination = document.getElementById('destinationFolder').value;
    const patchButton = document.getElementById('patchXboxIso');
    const chdButton = document.getElementById('convertToChdv5');
    const rvzButton = document.getElementById('convertIsoToRvz');
    const mergeButton = document.getElementById('mergeBinCue');
    const wsquashfsButton = document.getElementById('compressWsquashFS');
    const buttons = [patchButton, chdButton, rvzButton, mergeButton, wsquashfsButton];
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
            summary = { convertedGames: 0, skippedGames: 0, errorCount: 0, duration: 0 }; // Réinitialiser le résumé
            hasExtractionError = false; // Réinitialiser l'état d'erreur d'extraction
            logContent.classList.add('bg-gray-100', 'max-h-96', 'overflow-y-auto', 'p-4', 'rounded-lg');
        }
        updateProgress(0, 0, 'Initialisation...');
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

function appendSummaryTable() {
    const logContent = document.getElementById('logContent');
    if (logContent) {
        logContent.innerHTML += `
            <table class="w-full border-collapse mt-4 bg-white shadow-md">
                <thead>
                    <tr>
                        <th class="bg-gray-200 text-left p-2 font-bold text-gray-700">Métrique</th>
                        <th class="bg-gray-200 text-left p-2 font-bold text-gray-700">Valeur</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td class="p-2 border-b border-gray-300 text-gray-600">Temps écoulé</td>
                        <td class="p-2 border-b border-gray-300 text-gray-600">${summary.duration.toFixed(2)}s</td>
                    </tr>
                    <tr>
                        <td class="p-2 border-b border-gray-300 text-gray-600">Jeux convertis</td>
                        <td class="p-2 border-b border-gray-300 text-gray-600">${summary.convertedGames}</td>
                    </tr>
                    <tr>
                        <td class="p-2 border-b border-gray-300 text-gray-600">Jeux ignorés</td>
                        <td class="p-2 border-b border-gray-300 text-gray-600">${summary.skippedGames}</td>
                    </tr>
                    <tr>
                        <td class="p-2 text-gray-600">Erreurs</td>
                        <td class="p-2 text-gray-600">${summary.errorCount}</td>
                    </tr>
                </tbody>
            </table>
        `;
        logContent.scrollTop = logContent.scrollHeight;
    }
}

function updateProgress(totalProgress, currentFileProgress, message) {
    const totalProgressBar = document.getElementById('totalProgressBar');
    const totalProgressText = document.getElementById('totalProgressText');
    const totalProgressLabel = document.getElementById('totalProgressLabel');
    const currentFileProgressBar = document.getElementById('currentFileProgressBar');
    const currentFileProgressLabel = document.getElementById('currentFileProgressLabel');

    // Mettre à jour la progression totale
    if (totalProgressBar && totalProgressText && totalProgressLabel) {
        totalProgress = Math.min(100, Math.max(0, totalProgress));
        totalProgressBar.style.width = `${totalProgress}%`;
        totalProgressText.textContent = `${Math.round(totalProgress)}%`;
        totalProgressLabel.textContent = `Progression totale : ${message}`;
    } else {
        console.error('Un élément de progression totale est manquant');
    }

    // Mettre à jour la progression du fichier en cours
    if (currentFileProgressBar && currentFileProgressLabel) {
        currentFileProgress = Math.min(100, Math.max(0, currentFileProgress));
        currentFileProgressBar.style.width = `${currentFileProgress}%`;
        if (currentFileProgress > 0) {
            currentFileProgressLabel.textContent = `Progression fichier en cours : ${Math.round(currentFileProgress)}%`;
        } else {
            currentFileProgressLabel.textContent = `Progression fichier en cours : ${message}`;
        }
    } else {
        console.error('Un élément de progression du fichier en cours est manquant');
    }

    console.log(`Reçu progression: ${message} - Total: ${totalProgress}%, Fichier: ${currentFileProgress}%`);
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
        updateProgress(100, 0, 'Conversion terminée');
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
        updateProgress(100, 0, 'Conversion terminée');
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

async function extractChd() {
    const source = document.getElementById('sourceFolder').value;
    const destination = document.getElementById('destinationFolder').value;
    if (!source || !destination) return alert('Veuillez sélectionner les dossiers source et destination.');
    showLogModal('Extraction CHD');
    try {
        const result = await window.electronAPI.extractChd(source, destination);
        updateProgress(100, 0, 'Extraction terminée');
        const { extractedGames, skippedGames, errorCount } = result.summary;
        if (errorCount > 0) {
            alert(`Opération terminée avec ${errorCount} erreur(s). Consultez le journal pour plus de détails.`);
        } else {
            alert('Tous les jeux sont extraits, y\'a plus qu\'à jouer :D');
        }
    } catch (error) {
        appendLog(`Erreur: ${error.message}`);
        alert(`Erreur: ${error.message}`);
    }
}

async function convertIsoToRvz() {
    const source = document.getElementById('sourceFolder').value;
    const destination = document.getElementById('destinationFolder').value;
    if (!source || !destination) return alert('Veuillez sélectionner les dossiers source et destination.');
    alert('Cette fonction convertit les ISO GameCube/Wii en RVZ pour Dolphin Emulator');
    showLogModal('Conversion ISO to RVZ');
    try {
        const result = await window.electronAPI.convertIsoToRvz(source, destination);
        updateProgress(100, 0, 'Conversion terminée');
        const { convertedGames, errorCount } = result.summary;
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

async function mergeBinCue() {
    const source = document.getElementById('sourceFolder').value;
    const destination = document.getElementById('destinationFolder').value;
    if (!source || !destination) return alert('Veuillez sélectionner les dossiers source et destination.');
    alert('Cette fonction fusionne les fichiers BIN multiples associés à un fichier CUE en un seul fichier BIN via une conversion CHD intermédiaire.');
    showLogModal('Fusion BIN/CUE');
    try {
        const result = await window.electronAPI.mergeBinCue(source, destination);
        updateProgress(100, 0, 'Fusion terminée');
        const { mergedGames, skippedGames, errorCount } = result.summary;
        if (errorCount > 0) {
            alert(`Opération terminée avec ${errorCount} erreur(s). Consultez le journal pour plus de détails.`);
        } else {
            alert('Tous les jeux sont fusionnés, y\'a plus qu\'à jouer :D');
        }
    } catch (error) {
        appendLog(`Erreur: ${error.message}`);
        alert(`Erreur: ${error.message}`);
    }
}

async function compressWsquashFS() {
    const source = document.getElementById('sourceFolder').value;
    const destination = document.getElementById('destinationFolder').value;
    const compressionLevel = document.getElementById('compressionLevel').value;
    if (!source || !destination) return alert('Veuillez sélectionner les dossiers source et destination.');
    showLogModal('Compression wSquashFS');
    try {
        const result = await window.electronAPI.compressWsquashFS(source, destination, compressionLevel);
        updateProgress(100, 0, 'Compression terminée');
        const { compressedFolders, skippedFolders, errorCount } = result.summary;
        if (errorCount > 0) {
            alert(`Opération terminée avec ${errorCount} erreur(s). Consultez le journal pour plus de détails.`);
        } else {
            alert('Tous les dossiers sont compressés.');
        }
    } catch (error) {
        appendLog(`Erreur: ${error.message}`);
        alert(`Erreur: ${error.message}`);
    }
}

async function extractWsquashFS() {
    const source = document.getElementById('sourceFolder').value;
    const destination = document.getElementById('destinationFolder').value;
    if (!source || !destination) return alert('Veuillez sélectionner les dossiers source et destination.');
    showLogModal('Extraction wSquashFS');
    try {
        const result = await window.electronAPI.extractWsquashFS(source, destination);
        updateProgress(100, 0, 'Extraction terminée');
        const { extractedFiles, skippedFiles, errorCount } = result.summary;
        if (errorCount > 0) {
            alert(`Opération terminée avec ${errorCount} erreur(s). Consultez le journal pour plus de détails.`);
        } else {
            alert('Tous les fichiers sont extraits.');
        }
    } catch (error) {
        appendLog(`Erreur: ${error.message}`);
        alert(`Erreur: ${error.message}`);
    }
}

