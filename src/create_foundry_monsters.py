"""
Script to create json files for Foundry.
"""

import argparse
import logging
import json
import re
import uuid
from pathlib import Path
from typing import Any


# Set up logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def generate_foundry_data(name, data) -> dict[str, Any]:
    """
    Generate data in the format expected by the Foundry BFRPG system.
    """
    hd = data.get("Hit Dice")
    if "½" in hd or "d4" in hd:
        hd_type = "d4"
        hd_num = 1
    else:
        hd_type = "d8"
        if match := re.match(r"\d+", hd):
            hd_num = int(match.group())
        else:
            logger.warning(f"Number of HD not clear: {hd}")
            hd_num = 1

    if m := re.search(r"\+\d+", hd):
        hd_mod = int(m.group())
    else:
        hd_mod = 0

    # the file format requires these values
    _id = uuid.uuid4().hex[:16]
    key = f"!actors!{_id}"

    foundry_data = {
        "name": name,
        "type": "monster",
        "img": "icons/svg/mystery-man.svg",
        "_id": _id,
        "_key": key,
        "system": {
            "armorClass": {"value": data["Armor Class"]},
            "biography": "\n".join([f"<p>{p}</p>" for p in data["description"]]),
            "move": {"value": data["Movement"]},
            "hitDice": {"size": hd_type, "mod": hd_mod, "number": hd_num},
            "morale": {"value": data["Morale"]},
            "numberAppearing": {"value": data["No. Appearing"]},
        },
    }

    return foundry_data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "input",
        help="Input json file; it should have already been split into monsters and postprocessed",
    )
    parser.add_argument(
        "output_dir", help="Output directory to write individual monster files"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    with open(args.input, "r") as f:
        bestiary = json.load(f)

    output_dir_path = Path(f"{args.output_dir}")
    output_dir_path.mkdir(parents=True, exist_ok=True)

    for monster_name, monster_data in bestiary.items():
        try:
            foundry_data = generate_foundry_data(monster_name, monster_data)
        except:
            logger.error(f"Unable to extract data for {monster_name}")
            continue

        output_path = output_dir_path / f"{monster_name}.json"
        logger.debug(f"Writing monster to {output_path}")
        with open(output_path, "w") as f:
            json.dump(foundry_data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
