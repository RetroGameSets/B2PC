module.exports = {
  packagerConfig: {
    asar: true, // Compresse les fichiers en .asar pour optimiser
    icon: "./ressources/icon", // Icône pour l'application (sans extension : .ico pour Windows, .icns pour macOS)
    extraResources: [
      { from: "ressources", to: "ressources" } // Inclut 7za.exe, chdman.exe, xiso.exe
    ]
  },
  makers: [
    {
    name: "@electron-addons/electron-forge-maker-nsis",
      config: {
        options: {
          installerIcon: "./ressources/icon.ico", // Icône de l'installateur
          uninstallerIcon: "./ressources/icon.ico", // Icône de désinstallation
          shortcutName: "B2PC", // Nom du raccourci dans le menu Démarrer
          setupExeName: "B2PC-Setup.exe", // Nom de l'installateur
          license: "./LICENSE", // Chemin vers le fichier de licence (optionnel)
          perMachine: true, // Installation pour tous les utilisateurs
          allowToChangeInstallationDirectory: true, // Permet de choisir le dossier d'installation
          include: "./installer.nsi" // Script NSIS personnalisé (créé ci-dessous)
        }
      }
    },
    {
      name: "@electron-forge/maker-zip",
      platforms: ["darwin", "win32", "linux"]
    },
    {
      name: "@electron-forge/maker-deb",
      config: {
        options: {
          maintainer: "RetroGameSets.fr",
          homepage: "https://retrogamesets.fr"
        }
      }
    },
    {
      name: "@electron-forge/maker-dmg",
      config: {
        format: "ULFO"
      }
    }
  ],
  publishers: [
    {
      name: "@electron-forge/publisher-github",
      config: {
        repository: {
          owner: "tonUtilisateur", // Remplace par ton nom d'utilisateur GitHub
          name: "B2PC"
        },
        prerelease: false,
        draft: true
      }
    }
  ]
};