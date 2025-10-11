"""
Create json files for importing data to Foundry VTT.
"""

import argparse
import logging
import json
from pathlib import Path
from typing import Any

import utils


logger = logging.getLogger(__file__)


def generate_folder_structure(name, parent_id: str | None = None) -> dict[str, Any]:
    """
    Generate the structure of a folder json file.
    """
    _id = utils.generate_foundry_id()
    data = {
        "type": "Item",
        "name": name,
        "_id": _id,
        "_stats": {
            "systemId": "basicfantasyrpg",
        },
        "_key": f"!folders!{_id}",
    }

    if parent_id:
        data["folder"] = parent_id

    return data


def generate_spell_data(spell_data, icon_path: str, parent_id: str | None = None):
    """
    Generate the structure for the json import out of the existing json input.
    """
    _id = utils.generate_foundry_id()
    foundry_data = {
        "type": "spell",
        "name": spell_data["name"],
        "_id": _id,
        "_stats": {
            "systemId": "basicfantasyrpg",
        },
        "system": {
            "description": "\n".join(spell_data["description"]),
            "class": {
                "value": spell_data["class"].lower(),
                "label": "BASICFANTASYRPG.Class",
            },
            "duration": {
                "value": spell_data["duration"],
                "label": "BASICFANTASYRPG.Duration",
            },
            "prepared": {"value": 0, "label": "BASICFANTASYRPG.Prepared"},
            "range": {"value": spell_data["range"], "label": "BASICFANTASYRPG.Range"},
            "spellLevel": {
                "value": spell_data["level"],
                "label": "BASICFANTASYRPG.SpellLevel",
            },
        },
        "img": icon_path,
        "_key": f"!items!{_id}",
    }

    if parent_id:
        foundry_data["folder"] = parent_id

    return foundry_data


def write_json(output_path, contents):
    with open(output_path, "w") as f:
        json.dump(contents, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="json file with spells to import to Foundry.")
    parser.add_argument(
        "--folder", help="Optional folder name to place the spells under."
    )
    parser.add_argument(
        "--level-folders",
        action="store_true",
        help="Whether to create one subfolder for each spell level.",
    )
    parser.add_argument(
        "output_dir", help="Output directory to write individual json files"
    )
    parser.add_argument(
        "--icon",
        help="Custom spell icon (path inside Foundry)",
        default="icons/sundries/scrolls/scroll-writing-white.webp",
    )
    args = parser.parse_args()
    utils.setup_logging()

    output_dir_path = Path(f"{args.output_dir}")
    output_dir_path.mkdir(parents=True, exist_ok=True)

    with open(args.input, "r") as f:
        data = json.load(f)

    if args.folder:
        parent_folder = generate_folder_structure(args.folder)
        parent_id = parent_folder["_id"]
        write_json(output_dir_path / f"{args.folder}_folder.json", parent_folder)
    else:
        parent_id = None

    if args.level_folders:
        levels = {spell["level"] for spell in data}
        level_ids = {}

        for level in levels:
            if level == 1:
                name = "1st Level"
            elif level == 2:
                name = "2nd Level"
            elif level == 3:
                name = "3rd Level"
            else:
                name = f"{level}th Level"

            folder_data = generate_folder_structure(name, parent_id)
            level_ids[level] = folder_data["_id"]

            path = output_dir_path / f"{name}.json".replace(" ", "_")
            write_json(path, folder_data)

    written_files = 0

    for spell in data:
        if args.level_folders:
            parent = level_ids[spell["level"]]
        else:
            parent = parent_id

        spell_data = generate_spell_data(spell, args.icon, parent)
        path = output_dir_path / f'{spell["name"]}.json'.replace(" ", "_")
        write_json(path, spell_data)
        written_files += 1

    logger.info(f"Wrote {written_files} output files.")


if __name__ == "__main__":
    main()
