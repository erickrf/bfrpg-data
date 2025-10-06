import argparse
import logging
import re

import json
from typing import Any

from utils import setup_logging
from xml_utils import (
    parse_dom,
    prune_empty_elements,
    get_recursive_text,
    concat_text_parts,
    ODTStyleParser,
    convert_table_to_html,
)

setup_logging()
logger = logging.getLogger(__file__)


def identify_part(part) -> dict[str, Any]:
    """
    Identify which part of the metadata is contained.
    """
    match = re.match(r"([-\w\s]+)(\d)", part)
    if match:
        _class = match.group(1).strip()
        level = int(match.group(2))
        return {"level": level, "class": _class}

    if cleaned := part.strip():
        return {"name": cleaned}

    return {}


def main():
    """
    Main function.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Path to the supplement")
    parser.add_argument("output", help="Path to save json output")
    args = parser.parse_args()

    dom = parse_dom(path=args.input)
    root = dom.documentElement
    prune_empty_elements(root)
    body = root.getElementsByTagName("office:body")[0]
    text = body.getElementsByTagName("office:text")[0]

    style_parser = ODTStyleParser()
    style_parser.parse_styles(dom)

    has_metadata = False
    spell_root_node = None
    spells = []
    current_spell = {}

    known_exceptions = ["Protection from Undead*", "Protection from Undead 10' Radius*"]

    for _child in text.childNodes:
        child_text_parts = get_recursive_text(_child)
        child_text = concat_text_parts(child_text_parts)

        if "DESCRIPTION OF NEW SPELLS" in child_text:
            # this section contains the spell descriptions
            spell_root_node = _child
            break

    if spell_root_node is None:
        logger.error("Couldn't find spell header")
        exit()

    found_spell_list = False

    for _child in spell_root_node.childNodes:

        child_text_parts = get_recursive_text(_child)
        child_text = concat_text_parts(child_text_parts)

        if "DESCRIPTION OF NEW SPELLS" == child_text:
            found_spell_list = True
            continue

        if not found_spell_list:
            continue

        # spells are structured like this:
        # SPELL NAME  Range: RANGE
        # Necromancer LEVEL  Duration: DURATION
        # DESCRIPTION

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
            metadata = identify_part(parts[0])
            current_spell.update(metadata)

            has_metadata = False
            continue

        # here, expect the description
        if "description" not in current_spell:
            current_spell["description"] = []

        if _child.nodeName == "table:table":
            desc_item = convert_table_to_html(_child, style_parser)
        else:
            desc_item = f"<p>{child_text}</p>"

        current_spell["description"].append(desc_item)

    spells.append(current_spell)

    for spell in spells:
        keys = ["name", "range", "duration", "level", "description", "class"]
        for key in keys:
            if key not in spell:
                name = spell.get("name", "unknown")
                logger.error(f"Spell {name} is missing {key}")

    with open(args.output, "w") as f:
        logger.info(f"Saving {len(spells)} spells to {args.output}")
        json.dump(spells, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
