import argparse
import json
import logging
import re

import utils

logger = logging.getLogger(__file__)

# some replacements for matching all keys
STAT_NAME_REPLACEMENTS = {
    "Treasure": "Treasure Type",
    "Movements": "Movement",
    "Save as": "Save As",
    "No of Attacks": "No. of Attacks",
    "No. of Attack": "No. of Attacks",
    "No Appearing": "No. Appearing",
    "Attacks": "No. of Attacks",
    "Armour Class": "Armor Class",
    "XP value": "XP",
    "XP Value": "XP",
}

EXPECTED_STATS = {
    "Armor Class",
    "Movement",
    "XP",
    "Save As",
    "Morale",
    "Damage",
    "Hit Dice",
    "Treasure Type",
    "No. of Attacks",
    "No. Appearing",
}


def extract_stats(rows: list[str]):
    """
    Extract the stats of the given monster.
    """
    stats = {}

    for key, value in rows:
        # special treatment to some noisy cases like "Save As: Figher:"
        if key.startswith("Save") and key.count(":") == 2:
            key, save_class = key.split(":", 1)

            # fix value to "Fighter: xx"
            value = save_class + value

        key = key.strip(": ")
        key = STAT_NAME_REPLACEMENTS.get(key, key)

        stats[key] = value

    return stats


def split_attacks(damage: str, verbose: bool = False) -> list[str]:
    """
    Split the damage description into multiple ones.
    """
    final_components = []
    parts = damage.split(",")

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # safely split on "or" as an isolate word
        subparts = re.split(r"(^|\b)or\b", part)
        for subpart in subparts:
            subpart = subpart.strip()
            if not subpart:
                continue

            if verbose and not re.search(r"\dd\d", subpart):
                logger.info(f"No dice formula found in {subpart}")

            final_components.append(subpart)

    return final_components


def process_file(filename: str):
    """
    Process one file extracting structured data from the tables.
    """
    with open(filename) as f:
        data = json.load(f)

    result = {}

    for monster, monster_data in data.items():
        tables = monster_data["tables"]

        if len(tables) > 1:
            logger.info(f"{monster} has multiple tables; adding extra tables as HTML.")
            # first table contain stats
            for table in tables[1:]:
                monster_data["description_paragraphs"].append(table["html"])

        stat_table = tables[0]["rows"]
        stats = extract_stats(stat_table)
        stat_names = stats.keys()

        missing = EXPECTED_STATS - stat_names
        additional = stat_names - EXPECTED_STATS

        if missing:
            logger.info(f"{monster} is missing {missing}")

        if additional:
            logger.info(f"{monster} has additional stats: {additional}")

        if "Damage" in stats:
            stats["Damage"] = split_attacks(stats["Damage"])

        result[monster] = stats
        result[monster]["description"] = monster_data["description_paragraphs"]

    return result


def main():
    parser = argparse.ArgumentParser(description="Postprocess tables data")
    parser.add_argument("input_file", help="Input JSON file")
    parser.add_argument("output_file", help="Output JSON file")
    args = parser.parse_args()

    utils.setup_logging()

    monsters = process_file(args.input_file)

    with open(args.output_file, "w") as f:
        json.dump(monsters, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
