import argparse
import logging
import re
from textwrap import indent

import json
from typing import Any

from utils import setup_logging
from xml_utils import (
    parse_dom,
    prune_empty_elements,
    get_recursive_text,
    concat_text_parts,
)

setup_logging()
logger = logging.getLogger(__file__)


def identify_part(part) -> tuple[str, Any]:
    """
    Identify which part of the metadata is contained.
    """
    match = re.match(r"Necromancer\s*(\d)", part)
    if match:
        level = int(match.group(1))
        return "level", level

    if cleaned := part.strip():
        return "name", cleaned

    return "", None


def main():
    """
    Main function.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Path to the Necromancer supplement")
    parser.add_argument("output", help="Path to save json output")
    args = parser.parse_args()

    dom = parse_dom(path=args.input)
    root = dom.documentElement
    prune_empty_elements(root)
    body = root.getElementsByTagName("office:body")[0]
    text = body.getElementsByTagName("office:text")[0]
    children = text.childNodes

    # this is the child with all relevant content for spells
    content_node = children[6]

    found_spells = False
    has_metadata = False
    spells = []
    current_spell = {}

    known_exceptions = ["Protection from Undead*", "Protection from Undead 10' Radius*"]

    content_children = content_node.childNodes
    for _child in content_children:
        child_text_parts = get_recursive_text(_child)

        if child_text_parts[0] == "DESCRIPTION OF NEW SPELLS":
            found_spells = True
            continue

        if not found_spells:
            continue

        # spells are structured like this:
        # SPELL NAME  Range: RANGE
        # Necromancer LEVEL  Duration: DURATION
        # DESCRIPTION
        child_text = concat_text_parts(child_text_parts)

        if child_text in known_exceptions:
            # a new spell starts here

            if current_spell:
                spells.append(current_spell)
                current_spell = {}

            current_spell["name"] = child_text
            continue

        if "Range:" in child_text:
            # a new spell starts here

            if current_spell and "range" in current_spell:
                spells.append(current_spell)
                current_spell = {}

            parts = child_text.split("Range:")
            current_spell["range"] = parts[1].strip()
            has_metadata = True

        elif "Duration:" in child_text:

            parts = child_text.split("Duration:")
            current_spell["duration"] = parts[1].strip()
            has_metadata = True

        if has_metadata:
            key, value = identify_part(parts[0])
            if key:
                current_spell[key] = value

            has_metadata = False
            continue

        # here, expect the description
        if "description" not in current_spell:
            current_spell["description"] = []

        p = f"<p>{child_text}</p>"
        current_spell["description"].append(p)

    spells.append(current_spell)

    for spell in spells:
        keys = ["name", "range", "duration", "level", "description"]
        for key in keys:
            if key not in spell:
                name = spell.get("name", "unknown")
                logger.error(f"Spell {name} is missing {key}")

    with open(args.output, "w") as f:
        logger.info(f"Saving {len(spells)} spells to {args.output}")
        json.dump(spells, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
