module.exports = {
  packagerConfig: {
    asar: true,
	icon: "./icon.ico",
    extraResources: [
      { from: "ressources", to: "ressources" }
    ]
  },
  makers: [
    {
      name: "@electron-addons/electron-forge-maker-nsis",
      config: {
        options: {
          installerIcon: "./icon.ico",
          uninstallerIcon: "./icon.ico",
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
  ],
  publishers: [
    {
      name: "@electron-forge/publisher-github",
      config: {
        repository: {
          owner: "RetroGameSets",
          name: "B2PC"
        },
        prerelease: true,
        draft: true
      }
    }
  ]
};