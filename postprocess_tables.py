#!/usr/bin/env python3
"""
Extract structured monster stats from monsters_split.json file.
Converts table data into structured JSON with camelCase keys.
"""

import json
import re
import logging
import argparse
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

# Expected stats and their variations
EXPECTED_STATS = {
    'armorClass': ['Armor Class:'],
    'hitDice': ['Hit Dice:'],
    'numberOfAttacks': ['No. of Attacks:', 'Number of Attacks:', 'Attacks:', 'No of Attacks:', 'No. Attacks:'],
    'damage': ['Damage:', 'Dam:', 'Damage'],
    'movement': ['Movement:', 'Move:', 'Movement'],
    'numberAppearing': ['No. Appearing:', 'Number Appearing:', 'No Appearing:', 'Appearing:', 'No. App:'],
    'saveClass': ['Save As:', 'Save as:', 'Saves As:', 'Saves as:', 'Save'],  # Now expects saveClass instead of saveAs
    'morale': ['Morale:', 'Mor:', 'Morale'],
    'treasureType': ['Treasure Type:', 'Treasure:', 'TT:', 'Treasure Type'],
    'xp': ['XP:', 'Experience:', 'Exp:', 'XP']
}

def parse_arguments() -> argparse.Namespace:
    """Parse and validate command line arguments."""
    parser = argparse.ArgumentParser(
        description='Extract structured monster stats from JSON file containing monster data.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s monsters_split.json
  %(prog)s monsters_split.json -o monsters_data.json
  %(prog)s input.json --indent 4 -v
  %(prog)s input.json --validate-only -q
        """.strip()
    )
    
    # Positional argument
    parser.add_argument(
        'input_file',
        help='Input JSON file containing monster data'
    )
    
    # Optional arguments
    parser.add_argument(
        '-o', '--output',
        help='Output file path (default: {input_basename}_structured.json)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='count',
        default=0,
        help='Increase verbosity (-v for INFO, -vv for DEBUG)'
    )
    
    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Suppress all output except errors'
    )
    
    parser.add_argument(
        '--indent',
        type=int,
        default=2,
        help='JSON indentation level (default: 2, use 0 for compact)'
    )
    
    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='Only validate structure, do not write output file'
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.quiet and args.verbose:
        parser.error("Cannot use both --quiet and --verbose")
    
    if args.indent < 0:
        parser.error("Indent level must be non-negative")
    
    return args

def setup_logging(args: argparse.Namespace) -> None:
    """Configure logging based on verbosity settings."""
    if args.quiet:
        level = logging.ERROR
    elif args.verbose >= 2:
        level = logging.DEBUG
    elif args.verbose >= 1:
        level = logging.INFO
    else:
        level = logging.WARNING
    
    logging.basicConfig(
        level=level,
        format='%(levelname)s: %(message)s',
        stream=sys.stdout
    )

def get_default_output_path(input_path: str) -> str:
    """Generate default output filename based on input filename."""
    path = Path(input_path)
    stem = path.stem
    return f"{stem}_structured.json"

def validate_files(args: argparse.Namespace) -> tuple[Path, Optional[Path]]:
    """Validate input and output file paths."""
    logger = logging.getLogger(__name__)
    
    # Validate input file
    input_path = Path(args.input_file)
    if not input_path.exists():
        logger.error(f"Input file does not exist: {input_path}")
        sys.exit(1)
    
    if not input_path.is_file():
        logger.error(f"Input path is not a file: {input_path}")
        sys.exit(1)
    
    try:
        with open(input_path, 'r') as f:
            f.read(1)  # Test readability
    except Exception as e:
        logger.error(f"Cannot read input file: {e}")
        sys.exit(1)
    
    # Determine output path
    output_path = None
    if not args.validate_only:
        output_file = args.output if args.output else get_default_output_path(args.input_file)
        output_path = Path(output_file)
        
        # Validate output directory
        output_dir = output_path.parent
        if not output_dir.exists():
            try:
                output_dir.mkdir(parents=True)
            except Exception as e:
                logger.error(f"Cannot create output directory: {e}")
                sys.exit(1)
        
        # Test writeability
        try:
            test_file = output_dir / f".test_write_{output_path.name}"
            test_file.touch()
            test_file.unlink()
        except Exception as e:
            logger.error(f"Cannot write to output directory: {e}")
            sys.exit(1)
    
    return input_path, output_path

def normalize_key(key: str) -> str:
    """Normalize a table key to match expected stats."""
    key = key.strip()
    for camel_key, variations in EXPECTED_STATS.items():
        if key in variations:
            return camel_key
    
    # Convert to camelCase for unknown keys
    clean_key = re.sub(r'[:\.]', '', key)
    words = clean_key.split()
    if not words:
        return key.lower()
    
    camel_case = words[0].lower()
    for word in words[1:]:
        camel_case += word.capitalize()
    
    return camel_case

def parse_save_as(value: str) -> tuple[Optional[str], Optional[str]]:
    """Parse Save As value into saveClass and saveLevel."""
    if not value or 'same as hit dice' in value.lower():
        return None, None
    
    # Extract class and level using regex
    # Matches patterns like "Fighter: 2", "Magic-User: 8", "Normal Man"
    import re
    match = re.match(r'^([^:]+?):\s*(\d+)', value.strip())
    if match:
        save_class = match.group(1).strip()
        save_level = match.group(2).strip()
        return save_class, save_level
    
    # Handle "Normal Man" case
    if 'normal man' in value.lower():
        return 'Normal Man', None
    
    return None, None

def parse_hit_dice(value: str) -> tuple[str, Optional[str]]:
    """Parse Hit Dice value, extracting attack bonus and cleaning the dice."""
    if not value:
        return value, None
    
    import re
    
    # Extract attack bonus from parentheses like "(+8)" or "(+10)"
    attack_bonus_match = re.search(r'\(\+(\d+)\)', value)
    attack_bonus = attack_bonus_match.group(1) if attack_bonus_match else None
    
    # Remove all parentheses and their contents
    cleaned_value = re.sub(r'\([^)]*\)', '', value)
    
    # Remove stars (*, **)
    cleaned_value = re.sub(r'\*+', '', cleaned_value)
    
    # Clean up extra whitespace
    cleaned_value = cleaned_value.strip()
    
    return cleaned_value, attack_bonus

def extract_stats_from_table(table: Dict[str, Any]) -> Dict[str, str]:
    """Extract stats from a table's rows."""
    stats = {}
    
    if 'rows' not in table:
        return stats
    
    for row in table['rows']:
        if len(row) >= 2:
            key = normalize_key(row[0])
            value = row[1].strip()
            
            # Special handling for Save As
            if key == 'saveClass':  # This matches what normalize_key returns after our EXPECTED_STATS change
                save_class, save_level = parse_save_as(value)
                if save_class:
                    stats['saveClass'] = save_class
                if save_level:
                    stats['saveLevel'] = save_level
            # Special handling for Hit Dice
            elif key == 'hitDice':
                cleaned_dice, attack_bonus = parse_hit_dice(value)
                stats['hitDice'] = cleaned_dice
                if attack_bonus:
                    stats['attackBonus'] = attack_bonus
            else:
                stats[key] = value
    
    return stats

def validate_stats(stats: Dict[str, str], monster_name: str) -> None:
    """Validate that all expected stats are present and log warnings for missing ones."""
    logger = logging.getLogger(__name__)
    missing_stats = []
    
    for expected_key in EXPECTED_STATS.keys():
        if expected_key not in stats:
            missing_stats.append(expected_key)
    
    if missing_stats:
        logger.warning(f"Monster '{monster_name}' missing stats: {', '.join(missing_stats)}")

def process_monster(name: str, monster_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process a single monster and extract its structured data."""
    logger = logging.getLogger(__name__)
    
    result = {
        'name': name,
        'description': monster_data.get('description_paragraphs', []),
        'split': monster_data.get('split', False)
    }
    
    # Only add otherElements if it's not empty
    other_elements = monster_data.get('other_elements', [])
    if other_elements:
        result['otherElements'] = other_elements
    
    tables = monster_data.get('tables', [])
    
    if not tables:
        logger.warning(f"Monster '{name}' has no tables")
        return result
    
    # Extract stats from the first table (assumed to be stats table)
    stats_table = tables[0]
    stats = extract_stats_from_table(stats_table)
    
    # Validate stats
    validate_stats(stats, name)
    
    # Add stats to result
    result.update(stats)
    
    # Only add remaining tables if there are any
    remaining_tables = tables[1:] if len(tables) > 1 else []
    if remaining_tables:
        result['tables'] = remaining_tables
    
    return result

def main():
    """Main function to process the monsters file."""
    # Parse arguments and setup
    args = parse_arguments()
    setup_logging(args)
    logger = logging.getLogger(__name__)
    
    # Validate files
    input_path, output_path = validate_files(args)
    
    try:
        # Read the input file
        logger.info(f"Reading {input_path}...")
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if 'monsters' not in data:
            logger.error("No 'monsters' key found in input file")
            sys.exit(1)
        
        # Process each monster
        structured_monsters = {}
        monsters = data['monsters']
        
        logger.info(f"Processing {len(monsters)} monsters...")
        
        for monster_name, monster_data in monsters.items():
            structured_monster = process_monster(monster_name, monster_data)
            structured_monsters[monster_name] = structured_monster
        
        if args.validate_only:
            logger.info(f"Validation complete - processed {len(structured_monsters)} monsters")
            return
        
        # Write the output file
        output_data = {'monsters': structured_monsters}
        
        logger.info(f"Writing structured data to {output_path}...")
        indent = None if args.indent == 0 else args.indent
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=indent, ensure_ascii=False)
        
        logger.info(f"Successfully processed {len(structured_monsters)} monsters")
        
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()