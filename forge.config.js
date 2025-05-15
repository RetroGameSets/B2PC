module.exports = {
  packagerConfig: {
    asar: true,
    icon: "./icon.ico",
    extraResources: [
      { from: "ressources", to: "ressources" }
    ],
    ignore: [
      "^/LOG/",
      "^/out/",
      "^/.*\\.log$"
    ]
  },
  makers: [
    {
      name: "@felixrieseberg/electron-forge-maker-nsis",
      config: {
        nsis: {
          oneClick: false,
          perMachine: true,
          allowToChangeInstallationDirectory: true,
          installerIcon: "./icon.ico",
          uninstallerIcon: "./icon.ico",
          shortcutName: "B2PC",
          setupExeName: "B2PC-Setup.exe",
          runAfterFinish: false
        }
      }
    },
    {
      name: "@electron-forge/maker-zip",
      platforms: ["win32"]
    }
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