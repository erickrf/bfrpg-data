#!/usr/bin/env python3
"""
Monster Post-Processing Script

This script processes the extracted monster JSON to split multi-monster entries
into individual monster entries. Multi-monster entries are identified by stats
tables with more than 2 columns.

Usage:
    python postprocess_monsters.py [--input INPUT_FILE] [--output OUTPUT_FILE]
"""

import json
import re
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import copy


class MonsterPostProcessor:
    """Post-processes monster JSON to split multi-monster entries."""
    
    # Patterns to identify stats tables
    STATS_ATTRIBUTES = {
        'armor class:', 'hit dice:', 'no. of attacks:', 'damage:', 'movement:',
        'no. appearing:', 'save as:', 'morale:', 'treasure type:', 'xp:',
        'ac:', 'hd:', 'attacks:', 'dmg:', 'mv:', 'ml:', 'treasure:',
        'hit points:', 'thac0:', 'special attacks:', 'special defenses:'
    }
    
    def __init__(self, input_file: str):
        self.input_file = Path(input_file)
        self.input_data = None
        self.output_monsters = {}
        self.stats = {
            'original_entries': 0,
            'multi_monster_entries': 0, 
            'single_monster_entries': 0,
            'no_table_entries': 0,
            'split_monsters': 0,
            'total_output_monsters': 0
        }
    
    def load_input(self):
        """Load the input JSON file."""
        print(f"Loading {self.input_file}...")
        with open(self.input_file, 'r', encoding='utf-8') as f:
            self.input_data = json.load(f)
        
        self.stats['original_entries'] = len(self.input_data['monsters'])
        print(f"Loaded {self.stats['original_entries']} monster entries")
    
    def process_monsters(self) -> Dict[str, Any]:
        """Process all monsters, splitting multi-monster entries."""
        print("Processing monster entries...")
        
        for monster_name, monster_data in self.input_data['monsters'].items():
            print(f"Processing: {monster_name}")
            
            # Check if entry has any tables
            tables = monster_data.get('tables', [])
            if not tables:
                # No tables - likely a monster family/category description
                print(f"  → No tables found (monster family/category)")
                self._process_single_monster_entry(monster_name, monster_data)
                self.stats['no_table_entries'] += 1
                continue
            
            # Find the main stats table
            stats_table = self._find_stats_table(tables)
            
            if stats_table and self._is_multi_monster_table(stats_table):
                # Split multi-monster entry
                self._process_multi_monster_entry(monster_name, monster_data, stats_table)
                self.stats['multi_monster_entries'] += 1
            else:
                # Single monster entry with stats - copy as-is
                print(f"  → Single monster with stats table")
                self._process_single_monster_entry(monster_name, monster_data)
                self.stats['single_monster_entries'] += 1
        
        self.stats['total_output_monsters'] = len(self.output_monsters)
        
        return {
            'monsters': self.output_monsters,
            'metadata': {
                'processing_stats': self.stats,
                'total_monsters': self.stats['total_output_monsters'],
                'split_from_multi_entries': self.stats['split_monsters'],
                'single_entries': self.stats['single_monster_entries']
            }
        }
    
    def _find_stats_table(self, tables: List[Dict]) -> Optional[Dict]:
        """Find the main stats table among all tables for a monster."""
        if not tables:
            return None
        
        # Look for table with the most RPG stats attributes
        best_table = None
        best_score = 0
        
        for table in tables:
            if not table.get('rows') or len(table['rows']) == 0:
                continue
                
            # Count how many rows contain stats attributes
            score = 0
            for row in table['rows']:
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
        if not table.get('rows') or len(table['rows']) == 0:
            return False
        
        # Check if first row has more than 2 columns
        first_row = table['rows'][0]
        return len(first_row) > 2
    
    def _extract_monster_names(self, header_row: List[str]) -> List[str]:
        """Extract monster names from the header row of a stats table."""
        monster_names = []
        
        # Skip first column (attribute names), extract from columns 2+
        for i in range(1, len(header_row)):
            name = self._clean_text(header_row[i])
            if name:  # Only add non-empty names
                monster_names.append(name)
        
        return monster_names
    
    def _process_multi_monster_entry(self, original_name: str, monster_data: Dict, stats_table: Dict):
        """Split a multi-monster entry into individual monster entries."""
        print(f"  → Splitting multi-monster entry: {len(stats_table['rows'][0])} columns")
        
        # Extract monster names from header row
        monster_names = self._extract_monster_names(stats_table['rows'][0])
        print(f"  → Found monsters: {monster_names}")
        
        if not monster_names:
            print(f"  → Warning: Could not extract monster names, keeping as single entry")
            self._process_single_monster_entry(original_name, monster_data)
            return
        
        # Create individual entries for each monster
        for i, monster_name in enumerate(monster_names):
            column_index = i + 1  # +1 because first column is attributes
            
            # Create new monster data
            new_monster_data = {
                'description_paragraphs': copy.deepcopy(monster_data.get('description_paragraphs', [])),
                'tables': self._create_individual_stats_table(stats_table, column_index, monster_name),
                'other_elements': copy.deepcopy(monster_data.get('other_elements', []))
            }
            
            # Add any non-stats tables to all split monsters
            for table in monster_data.get('tables', []):
                if table != stats_table:
                    new_monster_data['tables'].append(copy.deepcopy(table))
            
            # Use clean monster name as key
            clean_name = self._clean_monster_name(monster_name)
            
            # Handle duplicate names by adding numbers
            final_name = clean_name
            counter = 2
            while final_name in self.output_monsters:
                final_name = f"{clean_name} ({counter})"
                counter += 1
            
            self.output_monsters[final_name] = new_monster_data
            self.stats['split_monsters'] += 1
            print(f"  → Created: {final_name}")
    
    def _process_single_monster_entry(self, monster_name: str, monster_data: Dict):
        """Process a single monster entry (copy as-is)."""
        self.output_monsters[monster_name] = copy.deepcopy(monster_data)
    
    def _create_individual_stats_table(self, stats_table: Dict, column_index: int, monster_name: str) -> List[Dict]:
        """Create a 2-column stats table for an individual monster."""
        if column_index >= len(stats_table['rows'][0]):
            print(f"Warning: Column index {column_index} out of range for {monster_name}")
            return []
        
        # Create new table with 2 columns: attributes + monster's values
        new_rows = []
        
        for row in stats_table['rows']:
            if len(row) > column_index:
                # Create 2-column row: [attribute_name, monster_value]
                if row == stats_table['rows'][0]:  # Header row
                    # Skip header row or create a simple one
                    continue
                else:
                    new_row = [row[0], row[column_index]]
                    new_rows.append(new_row)
        
        if not new_rows:
            return []
        
        # Build HTML table
        html_rows = []
        for row in new_rows:
            html_rows.append(f"<tr><td>{row[0]}</td><td>{row[1]}</td></tr>")
        
        html_table = f"<table>{''.join(html_rows)}</table>"
        
        return [{
            'type': 'table',
            'rows': new_rows,
            'html': html_table
        }]
    
    def _clean_text(self, text: str) -> str:
        """Clean text by removing HTML tags and extra whitespace."""
        if not text:
            return ""
        
        # Remove HTML tags
        clean = re.sub(r'<[^>]+>', '', text)
        # Remove extra whitespace
        clean = ' '.join(clean.split())
        return clean.strip()
    
    def _clean_monster_name(self, name: str) -> str:
        """Clean monster name for use as dictionary key."""
        clean = self._clean_text(name)
        
        # Remove common formatting artifacts
        clean = clean.replace('*', '').replace('**', '')
        
        return clean.strip()
    
    def print_stats(self):
        """Print processing statistics."""
        print("\n" + "="*50)
        print("PROCESSING STATISTICS")
        print("="*50)
        print(f"Original entries:           {self.stats['original_entries']}")
        print(f"Multi-monster entries:      {self.stats['multi_monster_entries']}")  
        print(f"Single monster entries:     {self.stats['single_monster_entries']}")
        print(f"No-table entries (families): {self.stats['no_table_entries']}")
        print(f"Monsters from splitting:    {self.stats['split_monsters']}")
        print(f"Total output monsters:      {self.stats['total_output_monsters']}")
        print(f"Net increase:              {self.stats['total_output_monsters'] - self.stats['original_entries']}")


def main():
    parser = argparse.ArgumentParser(description='Post-process monster JSON to split multi-monster entries')
    parser.add_argument('--input', default='monsters.json',
                        help='Input JSON file (default: monsters.json)')
    parser.add_argument('--output', default='monsters_split.json',
                        help='Output JSON file (default: monsters_split.json)')
    parser.add_argument('--stats', action='store_true',
                        help='Show detailed statistics')
    
    args = parser.parse_args()
    
    # Check if input exists
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        return 1
    
    try:
        # Process monsters
        processor = MonsterPostProcessor(args.input)
        processor.load_input()
        
        output_data = processor.process_monsters()
        
        # Save output
        output_path = Path(args.output)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        processor.print_stats()
        print(f"\n✓ Processed monsters saved to {output_path}")
        
        return 0
        
    except Exception as e:
        print(f"Error during processing: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit(main())