"""
Palworld Xbox Game Pass Save Transfer Tool
Transfer saves between devices by exporting from one and importing on another.
Combines export and import into a single user-friendly tool.
"""

import datetime
import os
import re
import shutil
import sys
import uuid
from sys import exit

from container_types import ContainerIndex, NotSupportedError, ContainerFile, ContainerFileList, FILETIME, Container


BANNER = r"""
=====================================================
   Palworld XGP Save Transfer Tool v1.0
   Transfer saves between devices easily
=====================================================
"""

PACKAGE_SUBPATH = r"Packages\PocketpairInc.Palworld_ad4psfrxyesvt"


# ──────────────────────────────────────────────
#  Shared helpers
# ──────────────────────────────────────────────

def pause_and_exit(code=0):
    os.system("pause")
    exit(code)


def find_container_path():
    """Locate the Xbox Game Pass Palworld container directory."""
    package_path = os.path.expandvars(rf"%LOCALAPPDATA%\{PACKAGE_SUBPATH}")
    if not os.path.exists(package_path):
        print("  [ERROR] Could not find Xbox Palworld install path.")
        print(f"  Expected: {package_path}")
        print("  Make sure Xbox Palworld is installed and has been launched at least once.")
        pause_and_exit(2)

    wgs_path = os.path.join(package_path, "SystemAppData", "wgs")
    container_regex = re.compile(r"[0-9A-F]{16}_[0-9A-F]{32}$")
    for d in os.listdir(wgs_path):
        if container_regex.match(d):
            return os.path.join(wgs_path, d)

    print("  [ERROR] Could not find the save container folder.")
    print("  Please launch Palworld on Xbox at least once to create it.")
    pause_and_exit(2)


def read_container_index(container_path):
    """Read and return the ContainerIndex from the given container path."""
    index_path = os.path.join(container_path, "containers.index")
    with open(index_path, "rb") as f:
        try:
            return ContainerIndex.from_stream(f)
        except NotSupportedError as e:
            print(f"  [ERROR] Unsupported container format: {e}")
            pause_and_exit(3)


def group_saves(container_index):
    """Group containers by save ID. Returns dict {save_id: [(file_type, container), ...]}"""
    saves = {}
    for container in container_index.containers:
        name = container.container_name
        parts = name.split("-", 1)
        if len(parts) == 2:
            save_id, file_type = parts
        else:
            save_id = name
            file_type = name
        saves.setdefault(save_id, []).append((file_type, container))
    return saves


# ──────────────────────────────────────────────
#  EXPORT  (Device A → folder)
# ──────────────────────────────────────────────

def do_export():
    print()
    print("─── EXPORT: Extract saves from this device ───")
    print()

    # 1. Find container
    container_path = find_container_path()
    print(f"  Found container: {container_path}")

    # 2. Read index
    container_index = read_container_index(container_path)
    print(f"  Package: {container_index.package_name}")
    print(f"  Total containers: {len(container_index.containers)}")
    print()

    # 3. Group by save
    saves = group_saves(container_index)
    if not saves:
        print("  No saves found in the container.")
        pause_and_exit(4)

    save_ids = list(saves.keys())
    print("  Available saves:")
    for i, save_id in enumerate(save_ids):
        files = [ft for ft, _ in saves[save_id]]
        print(f"    [{i + 1}] {save_id}  ({len(files)} files: {', '.join(files)})")
    print()

    # 4. Let user choose
    choice_input = input(f"  Select save to export (1-{len(save_ids)}, or 'all'): ").strip()

    if choice_input.lower() == "all":
        selected_indices = list(range(len(save_ids)))
    else:
        try:
            choice = int(choice_input)
        except ValueError:
            print("  Invalid input.")
            pause_and_exit(4)
        if choice < 1 or choice > len(save_ids):
            print("  Invalid choice.")
            pause_and_exit(4)
        selected_indices = [choice - 1]

    # 5. Ask for output location
    default_output = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exported_saves")
    custom = input(f"  Output folder [{default_output}]: ").strip()
    output_base = custom if custom else default_output

    # 6. Extract
    for idx in selected_indices:
        selected_save_id = save_ids[idx]
        print(f"\n  Exporting save: {selected_save_id}")

        output_path = os.path.join(output_base, selected_save_id)
        players_path = os.path.join(output_path, "Players")
        os.makedirs(output_path, exist_ok=True)
        os.makedirs(players_path, exist_ok=True)

        for file_type, container in saves[selected_save_id]:
            container_dir = os.path.join(container_path, container.container_uuid.bytes_le.hex().upper())
            for f in os.listdir(container_dir):
                if f.startswith("container."):
                    file_list = ContainerFileList.from_stream(open(os.path.join(container_dir, f), "rb"))
                    for cf in file_list.files:
                        if file_type.startswith("Players-"):
                            player_id = file_type.replace("Players-", "")
                            out_file = os.path.join(players_path, f"{player_id}.sav")
                        else:
                            out_file = os.path.join(output_path, f"{file_type}.sav")

                        with open(out_file, "wb") as outf:
                            outf.write(cf.data)
                        print(f"    Exported: {os.path.relpath(out_file, output_base)}")

        print(f"    -> Saved to: {output_path}")

    print()
    print("  ✓ Export complete!")
    print()
    print("  NEXT STEPS:")
    print(f"    1. Copy the '{os.path.basename(output_base)}' folder to your other device")
    print("       (USB drive, cloud storage, network share, etc.)")
    print("    2. On the other device, run this tool again and choose 'Import'")
    print("    3. Point it to the exported save folder")
    print()


# ──────────────────────────────────────────────
#  IMPORT  (folder → Device B)
# ──────────────────────────────────────────────

def add_container(container_index, source_save_path, save_filename, container_name, container_path):
    """Create a new container entry and write its files."""
    files = [
        ContainerFile("Data", uuid.uuid4(), open(save_filename, "rb").read()),
    ]
    container_file_list = ContainerFileList(seq=1, files=files)

    container_uuid = uuid.uuid4()
    mtime = FILETIME.from_timestamp(os.path.getmtime(source_save_path))
    size = os.path.getsize(save_filename)
    container = Container(
        container_name=container_name,
        cloud_id="",
        seq=1,
        flag=5,
        container_uuid=container_uuid,
        mtime=mtime,
        size=size,
    )

    container_index.containers.append(container)
    container_index.mtime = FILETIME.from_timestamp(datetime.datetime.now().timestamp())

    container_content_path = os.path.join(container_path, container_uuid.bytes_le.hex().upper())
    os.makedirs(container_content_path, exist_ok=True)
    container_file_list.write_container(container_content_path)
    print(f"    Wrote container: {container_name}")


def validate_save_folder(path):
    """Check if a folder looks like a valid Palworld save (has Level.sav or level.sav)."""
    for name in ("Level.sav", "level.sav"):
        if os.path.exists(os.path.join(path, name)):
            return True
    return False


def do_import():
    print()
    print("─── IMPORT: Load saves onto this device ───")
    print()
    print("  WARNING: This is experimental. Always manually back up your saves first!")
    print()

    # 1. Find container
    container_path = find_container_path()
    print(f"  Found container: {container_path}")

    # 2. Read index
    container_index = read_container_index(container_path)
    print(f"  Package: {container_index.package_name}")
    print(f"  Existing containers: {len(container_index.containers)}")
    print()

    # 3. Show existing saves so user knows what's already there
    existing_saves = group_saves(container_index)
    if existing_saves:
        print("  Saves already on this device:")
        for save_id, files in existing_saves.items():
            file_types = [ft for ft, _ in files]
            print(f"    • {save_id}  ({', '.join(file_types)})")
        print()

    # 4. Ask for save folder path
    default_export_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exported_saves")
    print(f"  Enter the path to the exported save folder.")
    print(f"  This should be the folder containing Level.sav, LevelMeta.sav, etc.")

    # Check if exported_saves directory exists and list available saves
    available_saves = []
    if os.path.exists(default_export_dir):
        for d in os.listdir(default_export_dir):
            full = os.path.join(default_export_dir, d)
            if os.path.isdir(full) and validate_save_folder(full):
                available_saves.append((d, full))

    if available_saves:
        print()
        print("  Found exported saves ready to import:")
        for i, (name, path) in enumerate(available_saves):
            files = [f for f in os.listdir(path) if f.endswith(".sav")]
            players_dir = os.path.join(path, "Players")
            player_count = len(os.listdir(players_dir)) if os.path.exists(players_dir) else 0
            print(f"    [{i + 1}] {name}  ({len(files)} files, {player_count} players)")
        print(f"    [0] Enter a custom path instead")
        print()

        choice_input = input(f"  Select save to import (0-{len(available_saves)}): ").strip()
        try:
            choice = int(choice_input)
        except ValueError:
            print("  Invalid input.")
            pause_and_exit(4)

        if choice == 0:
            source_save_path = input("  Path to save folder: ").strip().strip('"')
        elif 1 <= choice <= len(available_saves):
            source_save_path = available_saves[choice - 1][1]
        else:
            print("  Invalid choice.")
            pause_and_exit(4)
    else:
        source_save_path = input("  Path to save folder: ").strip().strip('"')

    source_save_path = os.path.normpath(source_save_path)

    # 5. Validate the save folder
    if not os.path.exists(source_save_path):
        print(f"  [ERROR] Path does not exist: {source_save_path}")
        pause_and_exit(4)

    if os.path.isfile(source_save_path):
        source_save_path = os.path.dirname(source_save_path)

    if not validate_save_folder(source_save_path):
        print(f"  [ERROR] This doesn't look like a Palworld save folder (no Level.sav found).")
        print(f"  Path: {source_save_path}")
        pause_and_exit(4)

    save_name = os.path.basename(source_save_path)
    print(f"\n  Save folder: {source_save_path}")
    print(f"  Save ID:     {save_name}")

    # List files to be imported
    sav_files = [f for f in os.listdir(source_save_path) if f.endswith(".sav")]
    players_dir = os.path.join(source_save_path, "Players")
    player_files = []
    if os.path.exists(players_dir):
        player_files = [f for f in os.listdir(players_dir) if f.endswith(".sav")]

    print(f"  Files:       {', '.join(sav_files)}")
    if player_files:
        print(f"  Players:     {len(player_files)} player file(s)")
    print()

    # 6. Check for duplicates
    for container in container_index.containers:
        if container.container_name == f"{save_name}-Level":
            print(f"  [ERROR] A save with this ID already exists on this device: {save_name}")
            print(f"  Remove or rename the existing save first.")
            pause_and_exit(5)

    # 7. Confirm
    confirm = input("  Proceed with import? (y/n): ").strip().lower()
    if confirm not in ("y", "yes"):
        print("  Import cancelled.")
        pause_and_exit(0)

    # 8. Backup existing container
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    container_backup_path = f"{container_path}.backup.{timestamp}"
    shutil.copytree(container_path, container_backup_path)
    print(f"\n  Created backup: {container_backup_path}")

    # 9. Import save files into containers
    print("  Creating containers...")

    # Standard save files
    save_file_types = ["Level", "LevelMeta", "LocalData", "WorldOption"]
    for file_type in save_file_types:
        filename = os.path.join(source_save_path, f"{file_type}.sav")
        # Also try lowercase
        if not os.path.exists(filename):
            filename_lower = os.path.join(source_save_path, f"{file_type.lower()}.sav")
            if os.path.exists(filename_lower):
                filename = filename_lower
            else:
                # Skip if file doesn't exist (not all saves have WorldOption, etc.)
                print(f"    Skipped {file_type}.sav (not found)")
                continue

        add_container(container_index, source_save_path, filename, f"{save_name}-{file_type}", container_path)

    # Player files
    if os.path.exists(players_dir):
        for player_file in player_files:
            filename = os.path.join(players_dir, player_file)
            player_id = player_file.replace(".sav", "")
            add_container(container_index, source_save_path, filename,
                          f"{save_name}-Players-{player_id}", container_path)

    # 10. Write updated container index
    container_index.write_file(container_path)
    print("  Updated container index")

    print()
    print("  ✓ Import complete! The save should now appear in Palworld.")
    print()
    print("  IMPORTANT:")
    print("    • Wait 1-2 minutes before launching the game to let Xbox cloud sync settle")
    print("    • If the save doesn't appear, try restarting the Xbox app")
    print(f"    • Backup location: {container_backup_path}")
    print()


# ──────────────────────────────────────────────
#  Main menu
# ──────────────────────────────────────────────

def main():
    print(BANNER)

    # Allow command-line shortcuts: transfer.py export | transfer.py import <path>
    if len(sys.argv) >= 2:
        mode = sys.argv[1].lower()
        if mode in ("export", "e", "1"):
            do_export()
            pause_and_exit(0)
        elif mode in ("import", "i", "2"):
            do_import()
            pause_and_exit(0)

    print("  What would you like to do?")
    print()
    print("    [1] EXPORT - Extract saves from THIS device")
    print("        (Run this on the device you want to copy FROM)")
    print()
    print("    [2] IMPORT - Load saves onto THIS device")
    print("        (Run this on the device you want to copy TO)")
    print()

    choice = input("  Enter choice (1 or 2): ").strip()

    if choice in ("1", "export", "e"):
        do_export()
    elif choice in ("2", "import", "i"):
        do_import()
    else:
        print("  Invalid choice.")
        pause_and_exit(1)

    pause_and_exit(0)


if __name__ == "__main__":
    main()
