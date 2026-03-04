# Palworld XGP Save Transfer Tool

A tool to **export** and **import** Palworld Xbox Game Pass save files between devices.

Directly forked from the Starfield XGP Save Importer.

## Features

- **Export** – Extract saves from the Xbox Game Pass container into a portable folder
- **Import** – Load exported saves onto another device's Xbox Game Pass container
- Interactive menu with save selection
- Automatic backup before importing
- Standalone `.exe` – no Python required on the target device

## Usage

### Transfer Tool (recommended)

Run the standalone executable or the Python script:

```
$ python transfer.py
```

You'll be presented with a menu:

```
[1] EXPORT - Extract saves from THIS device
[2] IMPORT - Load saves onto THIS device
```

You can also pass the mode directly:

```
$ python transfer.py export
$ python transfer.py import
```

Or use the pre-built `palworld-xgp-transfer.exe` from the `dist/` folder — just double-click it on any Windows PC.

### Transferring saves between devices

1. **On Device A** – Run the tool and choose **Export**. Select the save you want. It will be extracted to an `exported_saves/` folder.
2. **Copy** the `exported_saves/` folder (and the `.exe`) to Device B via USB, cloud storage, etc.
3. **On Device B** – Run the tool and choose **Import**. It will auto-detect the exported saves and let you pick one to import.

### Legacy scripts

The original standalone scripts are still available:

```
$ python main.py <path to save folder>    # Import only
$ python export.py                         # Export only
```

## Building the exe

```
pip install pyinstaller
pyinstaller --onefile --console --name palworld-xgp-transfer transfer.py
```

The output will be in `dist/palworld-xgp-transfer.exe`.

## Notes

- The cloud sync feature of Xbox app might interfere with outside modifications to the savefile containers. After shutting down the game, **wait 1–2 minutes** before trying to import saves to give the Xbox app time to sync.
- The tool creates a backup of your container before importing. You can find it next to the original container folder.
- Both devices must have Xbox Palworld installed and launched at least once.

## Path references

| Version | Path |
|---------|------|
| Steam | `%LOCALAPPDATA%\Pal\Saved\SaveGames\<steamid64>\` |
| Xbox | `%LOCALAPPDATA%\Packages\PocketpairInc.Palworld_ad4psfrxyesvt\SystemAppData\wgs` |