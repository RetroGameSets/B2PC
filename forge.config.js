module.exports = {
  packagerConfig: {
    asar: true,
    icon: "file://C:/Users/Admin/Desktop/B2PC/ressources/icon.ico",
    extraResources: [
      { from: "ressources", to: "ressources" }
    ]
  },
  makers: [
    {
      name: "@electron-addons/electron-forge-maker-nsis",
      config: {
        options: {
          installerIcon: "file://C:/Users/Admin/Desktop/B2PC/ressources/icon.ico",
          uninstallerIcon: "file://C:/Users/Admin/Desktop/B2PC/ressources/icon.ico",
          shortcutName: "B2PC",
          setupExeName: "B2PC-Setup.exe",
          perMachine: true,
          allowToChangeInstallationDirectory: true,
          include: "./installer.nsi"
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
          owner: "RetroGameSets", // Remplace par ton nom d'utilisateur GitHub
          name: "B2PC"
        },
        prerelease: true, // Marque comme pre-release (bêta)
        draft: true
      }
    }
  ]
};