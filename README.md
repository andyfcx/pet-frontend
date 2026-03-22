# Description
A friendly UI app designed for biometeo, shows function documentation, default values

## Installation and launch
`pip install biometeo-frontend`

`(venv) $ biometeo-front`


## Usage
1. Select the function you would like to use
2. Input the function args or select your csv file with corresponding variable name (Calculate automatically). You can also drag it.
3. Click run to calculate
4. The results will show in tabular view.
5. You can export the result in csv/json format, to file or clipboard.
6. Clear the tabular view

## macOS DMG build
This project now targets Python `3.13` for macOS release builds.

Build a drag-and-drop installable `.dmg`:

```bash
chmod +x scripts/build_macos_dmg.sh
./scripts/build_macos_dmg.sh
```

Apple Silicon:

```bash
TARGET_ARCH=arm64 ./scripts/build_macos_dmg.sh
```

Intel x86_64:

```bash
TARGET_ARCH=x86_64 ./scripts/build_macos_dmg.sh
```

The script will:

1. Create a fresh build virtualenv with Python 3.13
2. Install the app and `pyinstaller`
3. Build `dist/Biometeo Frontend.app`
4. Wrap it into `dist/Biometeo-Frontend-0.1.1-macos-<arch>.dmg`

Notes:

- On Apple Silicon, building `x86_64` requires a Python 3.13 interpreter with Intel support plus Rosetta 2.
- On Intel Macs, only `x86_64` builds are supported by this script.
- The generated app and DMG are ad-hoc signed only.
- For a public download that opens without Gatekeeper warnings, you still need Apple Developer ID signing and notarization.
