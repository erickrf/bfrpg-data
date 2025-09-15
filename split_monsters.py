#!/usr/bin/env python3
"""
Monster Post-Processing Script

This script processes the extracted monster JSON to split multi-monster entries
into individual monster entries. Multi-monster entries are identified by stats
tables with more than 2 columns.
"""

import json
import re
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import copy

import utils


class MonsterPostProcessor:
    """Post-processes monster JSON to split multi-monster entries."""

    # Patterns to identify stats tables
    STATS_ATTRIBUTES = {
        "armor class:",
        "hit dice:",
        "no. of attacks:",
        "damage:",
        "movement:",
        "no. appearing:",
        "save as:",
        "morale:",
        "treasure type:",
        "xp:",
        "attacks:",
        "treasure:",
    }

    def __init__(self, input_file: str, skip_families: bool = True):
        self.input_file = Path(input_file)
        self.input_data = None
        self.output_monsters = {}
        self.stats = {
            "original_entries": 0,
            "multi_monster_entries": 0,
            "single_monster_entries": 0,
            "no_table_entries": 0,
            "split_monsters": 0,
            "total_output_monsters": 0,
        }
        self.skip_families = skip_families

    def load_input(self):
        """Load the input JSON file."""
        print(f"Loading {self.input_file}...")
        with open(self.input_file, "r", encoding="utf-8") as f:
            self.input_data = json.load(f)

        self.stats["original_entries"] = len(self.input_data)
        logging.info(f"Loaded {self.stats['original_entries']} monster entries")

    def process_monsters(self) -> Dict[str, Any]:
        """Process all monsters, splitting multi-monster entries."""
        logging.debug("Processing monster entries...")

        for monster_name, monster_data in self.input_data.items():
            logging.debug(f"Processing: {monster_name}")

            # Check if entry has any tables
            tables = monster_data.get("tables", [])
            if not tables:
                # No tables - likely a monster family/category description
                logging.debug(
                    f"  → No tables found; {monster_name} is likely a monster family"
                )
                if self.skip_families:
                    continue

                self._process_single_monster_entry(monster_name, monster_data)
                self.stats["no_table_entries"] += 1
                continue

            # Find the main stats table
            stats_table = self._find_stats_table(tables)

            if stats_table and self._is_multi_monster_table(stats_table):
                # Split multi-monster entry
                self._process_multi_monster_entry(
                    monster_name, monster_data, stats_table
                )
                self.stats["multi_monster_entries"] += 1
            else:
                # Single monster entry with stats - copy as-is
                logging.debug(f"  → Single monster with stats table")
                self._process_single_monster_entry(monster_name, monster_data)
                self.stats["single_monster_entries"] += 1

        self.stats["total_output_monsters"] = len(self.output_monsters)

        return self.output_monsters

    def _find_stats_table(self, tables: List[Dict]) -> Optional[Dict]:
        """Find the main stats table among all tables for a monster."""
        if not tables:
            return None

        # Look for table with the most RPG stats attributes
        best_table = None
        best_score = 0

        for table in tables:
            if not table.get("rows") or len(table["rows"]) == 0:
                continue

            # Count how many rows contain stats attributes
            score = 0
            for row in table["rows"]:
                if len(row) > 0:
                    first_cell = self._clean_text(row[0]).lower()
                    if any(attr in first_cell for attr in self.STATS_ATTRIBUTES):
                        score += 1

            if score > best_score:
                best_score = score
                best_table = table

        return best_table

    def _is_multi_monster_table(self, table: Dict) -> bool:
        """Check if a stats table contains multiple monsters (>2 columns)."""
        if not table.get("rows") or len(table["rows"]) == 0:
            return False

        # Check if first row has more than 2 columns
        first_row = table["rows"][0]
        return len(first_row) > 2

    def _extract_column_headers(self, header_row: List[str]) -> List[str]:
        """Extract column headers from the header row of a stats table."""
        column_headers = []

        # Skip first column (attribute names), extract from columns 2+
        for i in range(1, len(header_row)):
            header = self._clean_text(header_row[i])
            # Add even empty headers to maintain column correspondence
            column_headers.append(header if header else "")

        return column_headers

    def _process_multi_monster_entry(
        self, original_name: str, monster_data: Dict, stats_table: Dict
    ):
        """Split a multi-monster entry into individual monster entries."""
        # Extract column headers from first row (may be subtypes like "Adult", "Male", etc.)
        column_headers = self._extract_column_headers(stats_table["rows"][0])
        logging.debug(f"  → Found column headers: {column_headers}")

        if not column_headers:
            logging.error(
                f"  → Warning: Could not extract column headers, keeping as single entry"
            )
            self._process_single_monster_entry(original_name, monster_data)
            return

        # Create individual entries for each monster
        for i, column_header in enumerate(column_headers):
            column_index = i + 1  # +1 because first column is attributes

            # Create safer monster name by combining original name with column header
            if column_header.strip():
                safe_monster_name = f"{original_name} {column_header.strip()}"
            else:
                safe_monster_name = f"{original_name} ({i+1})"

            # Create new monster data
            new_monster_data = {
                "description_paragraphs": monster_data.get(
                    "description_paragraphs", []
                ),
                "tables": self._create_individual_stats_table(
                    stats_table, column_index
                ),
                "other_elements": copy.deepcopy(monster_data.get("other_elements", [])),
                "split": True,
            }

            # Add any non-stats tables to all split monsters
            for table in monster_data.get("tables", []):
                if table != stats_table:
                    new_monster_data["tables"].append(copy.deepcopy(table))

            # Use clean monster name as key
            clean_name = self._clean_monster_name(safe_monster_name)

            # Handle duplicate names by adding numbers
            final_name = clean_name
            counter = 2
            while final_name in self.output_monsters:
                final_name = f"{clean_name} ({counter})"
                counter += 1

            self.output_monsters[final_name] = new_monster_data
            self.stats["split_monsters"] += 1
            logging.info(f"  → Created: {final_name}")

    def _process_single_monster_entry(self, monster_name: str, monster_data: Dict):
        """Process a single monster entry (copy as-is)."""
        new_monster_data = copy.deepcopy(monster_data)
        new_monster_data["split"] = False
        self.output_monsters[monster_name] = new_monster_data

    def _create_individual_stats_table(
        self, stats_table: Dict, column_index: int
    ) -> List[Dict]:
        """Create a 2-column stats table for an individual monster."""
        # Create new table with 2 columns: attributes + monster's values
        new_rows = []

        for row_idx, row in enumerate(stats_table["rows"]):
            if row_idx == 0:  # Skip header row
                continue

            monster_value = None
            if len(row) > column_index:
                # Get the value for this monster's column
                monster_value = row[column_index].strip() if row[column_index] else ""

            # If the value is empty or missing, check if there's a shared value
            # A shared value would be in a column with a single non-empty cell spanning multiple columns conceptually
            if not monster_value:
                if len(row) == 2:
                    monster_value = row[1].strip()
                else:
                    logging.error(f"Value missing for monster")

            # Create 2-column row: [attribute_name, monster_value]
            new_row = [row[0], monster_value]
            new_rows.append(new_row)

        if not new_rows:
            return []

        return [{"type": "table", "rows": new_rows}]

    def _clean_text(self, text: str) -> str:
        """Clean text by removing HTML tags and extra whitespace."""
        if not text:
            return ""

        # Remove HTML tags
        clean = re.sub(r"<[^>]+>", "", text)
        # Remove extra whitespace
        clean = " ".join(clean.split())
        return clean.strip()

    def _clean_monster_name(self, name: str) -> str:
        """Clean monster name for use as dictionary key."""
        clean = self._clean_text(name)

        # Remove common formatting artifacts
        clean = clean.replace("*", "").replace("**", "")

        return clean.strip()

    def print_stats(self):
        """Print processing statistics."""
        print("\n" + "=" * 50)
        print("PROCESSING STATISTICS")
        print("=" * 50)
        print(f"Original entries:           {self.stats['original_entries']}")
        print(f"Multi-monster entries:      {self.stats['multi_monster_entries']}")
        print(f"Single monster entries:     {self.stats['single_monster_entries']}")
        print(f"No-table entries (families): {self.stats['no_table_entries']}")
        print(f"Monsters from splitting:    {self.stats['split_monsters']}")
        print(f"Total output monsters:      {self.stats['total_output_monsters']}")
        print(
            f"Net increase:              {self.stats['total_output_monsters'] - self.stats['original_entries']}"
        )


def main():
    parser = argparse.ArgumentParser(
        description="Post-process monster JSON to split multi-monster entries"
    )
    parser.add_argument("input", help="Input JSON file extracted from a book")
    parser.add_argument("output", help="Output JSON file")
    parser.add_argument("--stats", action="store_true", help="Show detailed statistics")
    parser.add_argument(
        "--keep-families",
        action="store_true",
        help='Keep monster families (i.e. "Bear" or "Dragon")',
    )

    args = parser.parse_args()
    utils.setup_logging()

    # Check if input exists
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        return 1

    processor = MonsterPostProcessor(args.input, skip_families=not args.keep_families)
    processor.load_input()
    output_data = processor.process_monsters()

    # Save output
    output_path = Path(args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    processor.print_stats()
    print(f"\n✓ Processed monsters saved to {output_path}")


if __name__ == "__main__":
    main()
