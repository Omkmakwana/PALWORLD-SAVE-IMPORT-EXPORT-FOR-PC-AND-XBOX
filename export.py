"""
Palworld Xbox Game Pass Save Exporter
Reads the Xbox container and extracts save files into a standard Palworld save folder structure.
"""

import os
import re
import sys
from sys import exit

from container_types import ContainerIndex, NotSupportedError, ContainerFileList


def main():
    print("========== Palworld Xbox Save Exporter ==========")
    print()

    # 1. Find the container
    package_path = os.path.expandvars(r"%LOCALAPPDATA%\Packages\PocketpairInc.Palworld_ad4psfrxyesvt")
    if not os.path.exists(package_path):
        print("Error: Could not find the package path. Make sure you have Xbox Palworld installed.")
        os.system("pause")
        exit(2)

    wgs_path = os.path.join(package_path, "SystemAppData", "wgs")
    container_regex = re.compile(r"[0-9A-F]{16}_[0-9A-F]{32}$")
    container_path = None
    for d in os.listdir(wgs_path):
        if container_regex.match(d):
            container_path = os.path.join(wgs_path, d)
            break

    if container_path is None:
        print("Error: Could not find the container path. Please try to run the game once to create it.")
        os.system("pause")
        exit(2)

    print(f"Found container path: {container_path}")

    # 2. Read the container index
    container_index_path = os.path.join(container_path, "containers.index")
    container_index_file = open(container_index_path, "rb")
    try:
        container_index = ContainerIndex.from_stream(container_index_file)
    except NotSupportedError as e:
        print(f"Error: Detected unsupported container format: {e}")
        os.system("pause")
        exit(3)
    container_index_file.close()

    print(f"Package: {container_index.package_name}")
    print(f"Found {len(container_index.containers)} containers:")
    print()

    # 3. Group containers by save name
    saves = {}
    for container in container_index.containers:
        name = container.container_name
        # Container names follow the format: <save_id>-<type>
        # e.g. "ABC123DEF-Level", "ABC123DEF-Players-000000001"
        parts = name.split("-", 1)
        if len(parts) == 2:
            save_id, file_type = parts
        else:
            save_id = name
            file_type = name

        if save_id not in saves:
            saves[save_id] = []
        saves[save_id].append((file_type, container))

    # 4. Display saves and let user choose
    save_ids = list(saves.keys())
    print("Available saves:")
    for i, save_id in enumerate(save_ids):
        files = [ft for ft, _ in saves[save_id]]
        print(f"  [{i + 1}] {save_id}  ({len(files)} files: {', '.join(files)})")
    print()

    if len(sys.argv) > 1 and sys.argv[1].lower() == "all":
        choice_input = "all"
    elif len(sys.argv) > 1:
        choice_input = sys.argv[1]
    else:
        choice_input = input(f"Select save to export (1-{len(save_ids)}, or 'all'): ")

    if choice_input.strip().lower() == "all":
        selected_indices = list(range(len(save_ids)))
    else:
        choice = int(choice_input)
        if choice < 1 or choice > len(save_ids):
            print("Invalid choice.")
            os.system("pause")
            exit(4)
        selected_indices = [choice - 1]

    output_base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exported_saves")

    for idx in selected_indices:
        selected_save_id = save_ids[idx]
        print(f"\nExporting save: {selected_save_id}")

        # 5. Create output folder
        output_path = os.path.join(output_base, selected_save_id)
        players_path = os.path.join(output_path, "Players")
        os.makedirs(output_path, exist_ok=True)
        os.makedirs(players_path, exist_ok=True)

        # 6. Extract each container
        for file_type, container in saves[selected_save_id]:
            container_dir = os.path.join(container_path, container.container_uuid.bytes_le.hex().upper())
            # Find the container.xxx file
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
                        print(f"  Exported: {os.path.relpath(out_file, output_base)}")

        print(f"  -> Saved to: {output_path}")

    print("\nAll done!")


if __name__ == "__main__":
    main()
