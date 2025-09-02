#!/usr/bin/env python3
"""
Monster Data Extraction Script for Basic Fantasy RPG Field Guide

This script extracts structured monster data from the ODT field guide document,
preserving styling information by converting ODT formatting to HTML tags.

Usage:
    python extract_monsters.py [--field-guide PATH] [--output PATH]
"""

import json
import re
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from xml.dom.minidom import parse, parseString, Element, Node
import argparse


class ODTStyleParser:
    """Parses ODT style definitions and converts them to HTML equivalents."""
    
    def __init__(self):
        self.style_map = {}
        
    def parse_styles(self, dom):
        """Extract style definitions from ODT document."""
        # Get automatic styles
        auto_styles = dom.getElementsByTagName('office:automatic-styles')
        if auto_styles:
            self._parse_style_section(auto_styles[0])
            
        # Get document styles if present
        doc_styles = dom.getElementsByTagName('office:styles')
        if doc_styles:
            self._parse_style_section(doc_styles[0])
    
    def _parse_style_section(self, style_section):
        """Parse a style section (automatic or document styles)."""
        styles = style_section.getElementsByTagName('style:style')
        
        for style in styles:
            style_name = style.getAttribute('style:name')
            if not style_name:
                continue
                
            style_properties = self._extract_style_properties(style)
            if style_properties:
                self.style_map[style_name] = style_properties
    
    def _extract_style_properties(self, style_element):
        """Extract formatting properties from a style element."""
        properties = {}
        
        # Check text properties
        text_props = style_element.getElementsByTagName('style:text-properties')
        if text_props:
            text_prop = text_props[0]
            
            # Font weight (bold)
            if text_prop.getAttribute('fo:font-weight') == 'bold':
                properties['bold'] = True
            if text_prop.getAttribute('style:font-weight-asian') == 'bold':
                properties['bold'] = True
                
            # Font style (italic)  
            if text_prop.getAttribute('fo:font-style') == 'italic':
                properties['italic'] = True
            if text_prop.getAttribute('style:font-style-asian') == 'italic':
                properties['italic'] = True
                
            # Font family
            font_family = text_prop.getAttribute('style:font-name')
            if font_family:
                properties['font_family'] = font_family
                
            # Font size
            font_size = text_prop.getAttribute('fo:font-size')
            if font_size:
                properties['font_size'] = font_size
        
        # Check paragraph properties
        para_props = style_element.getElementsByTagName('style:paragraph-properties')
        if para_props:
            para_prop = para_props[0]
            
            # Text alignment
            text_align = para_prop.getAttribute('fo:text-align')
            if text_align:
                properties['text_align'] = text_align
        
        return properties
    
    def get_html_tags(self, style_name: str) -> tuple[str, str]:
        """Get opening and closing HTML tags for a style."""
        if style_name not in self.style_map:
            return '', ''
            
        properties = self.style_map[style_name]
        tags = []
        
        # Convert properties to HTML tags
        if properties.get('bold'):
            tags.append('strong')
        if properties.get('italic'):
            tags.append('em')
            
        # Build opening and closing tags
        opening = ''.join(f'<{tag}>' for tag in tags)
        closing = ''.join(f'</{tag}>' for tag in reversed(tags))
        
        return opening, closing


class MonsterExtractor:
    """Main class for extracting monster data from ODT field guide."""
    
    def __init__(self, odt_path: str):
        self.odt_path = Path(odt_path)
        self.style_parser = ODTStyleParser()
        self.dom = None
        self.monster_names_from_index = set()
        
        # Known fixes for header inconsistencies
        self.known_fixes = {
            "Badger (andBadger, Giant)": "Badger (and Badger, Giant)",
            "CowDragon": "Cow Dragon",
            "Deer, Huge (MegalocerosorIrish Deer)": "Deer, Huge (Megaloceros or Irish Deer)",
            "Eel, Common, Electric, Weed, &Giant": "Eel, Common, Electric, Weed, & Giant",
            "GreatOrb ofEyes": "Great Orb of Eyes",
            "Infernal, DreadHorseman": "Infernal, Dread Horseman",
            "Ear Worms": "Ear Worms"
        }
    
    def extract_monsters(self) -> Dict[str, Any]:
        """Main extraction method."""
        print("Loading ODT file...")
        self._load_odt()
        
        print("Parsing styles...")
        self.style_parser.parse_styles(self.dom)
        
        print("Extracting monster index...")
        self.monster_names_from_index = self._extract_monster_index()
        
        print("Extracting monster data...")
        monster_data = self._extract_monster_data()
        
        print("Validating extraction...")
        self._validate_extraction(monster_data)
        
        return monster_data
    
    def _load_odt(self):
        """Load and parse the ODT file."""
        with zipfile.ZipFile(self.odt_path, 'r') as odt_zip:
            content_xml = odt_zip.read('content.xml')
            self.dom = parseString(content_xml)
    
    def _extract_monster_index(self) -> set:
        """Extract monster names from the index section."""
        text_element = self.dom.getElementsByTagName('office:text')[0]
        sections = text_element.getElementsByTagName("text:section")
        
        # Index is in sections[2]
        if len(sections) < 3:
            print("Warning: Expected at least 3 sections, found", len(sections))
            return set()
            
        index_section = sections[2]
        
        # Navigate to index content
        try:
            index_element = index_section.childNodes[1].childNodes[1]
            index_raw = self._get_recursive_text_list(index_element)
            
            # Extract monster names (first element of each entry)
            monster_names = set()
            for entry in index_raw:
                if isinstance(entry, list) and len(entry) > 0:
                    monster_names.add(entry[0][0])

            print(f"Found {len(monster_names)} monsters in index")
            return monster_names
            
        except (IndexError, AttributeError) as e:
            print(f"Error extracting monster index: {e}")
            return set()
    
    def _extract_monster_data(self) -> Dict[str, Dict]:
        """Extract all monster data from the main section."""
        text_element = self.dom.getElementsByTagName('office:text')[0]
        sections = text_element.getElementsByTagName("text:section")
        
        # Main monster section is sections[1]
        if len(sections) < 2:
            raise ValueError("Expected at least 2 sections in document")
            
        main_section = sections[1]
        
        # Remove empty elements first (from your notebook)
        self._prune_empty_elements(main_section)
        
        monster_data = {}
        current_monster = None
        current_monster_content = []
        
        print("Processing elements in main section...")
        for element in main_section.childNodes:
            if not hasattr(element, 'tagName'):
                continue
                
            if element.tagName == 'text:h':
                # New monster header found
                if current_monster:
                    # Save previous monster
                    monster_data[current_monster] = self._process_monster_content(current_monster_content)
                
                # Start new monster
                monster_name = self._extract_monster_name_from_header(element)
                if monster_name:
                    current_monster = monster_name
                    current_monster_content = []
                    print(f"Processing: {monster_name}")
                else:
                    continue
            else:
                # Content for current monster
                if current_monster:
                    current_monster_content.append(element)
        
        # Don't forget the last monster
        if current_monster:
            monster_data[current_monster] = self._process_monster_content(current_monster_content)
        
        return monster_data
    
    def _extract_monster_name_from_header(self, header_element) -> Optional[str]:
        """Extract monster name from header element."""
        text_parts = self._get_recursive_text_list(header_element)
        text = self._concat_text_parts(text_parts).strip()
        
        if not text:
            return None
            
        # Apply postprocessing
        text = self._postprocess_title(text)
        
        # Check if it's in our known fixes
        if text in self.known_fixes:
            text = self.known_fixes[text]
        
        # Check if it matches our index (if loaded)
        if self.monster_names_from_index and text not in self.monster_names_from_index:
            if text == 'Monster Index':
                return None
            print(f"Warning: Header '{text}' not found in monster index")
        
        return text
    
    def _process_monster_content(self, elements: List[Element]) -> Dict:
        """Process all content elements for a single monster."""
        content = {
            'description_paragraphs': [],
            'tables': [],
            'other_elements': []
        }
        
        for element in elements:
            if not hasattr(element, 'tagName'):
                continue
                
            if element.tagName == 'text:p':
                # Paragraph - likely description
                para_html = self._element_to_html(element)
                if para_html.strip():
                    content['description_paragraphs'].append(para_html)
                    
            elif element.tagName == 'table:table':
                # Table - likely stats
                table_data = self._table_to_html(element)
                if table_data:
                    content['tables'].append(table_data)
                    
            else:
                # Other element types
                other_html = self._element_to_html(element)
                if other_html.strip():
                    content['other_elements'].append({
                        'type': element.tagName,
                        'html': other_html
                    })
        
        return content
    
    def _element_to_html(self, element) -> str:
        """Convert an ODT element to HTML with styling preserved."""
        if element.nodeType == Node.TEXT_NODE:
            return element.data
        
        if not hasattr(element, 'tagName'):
            return ''
        
        # Get style information
        style_name = element.getAttribute('text:style-name')
        opening_tag, closing_tag = self.style_parser.get_html_tags(style_name)
        
        # Process children recursively
        content_parts = []
        for child in element.childNodes:
            child_html = self._element_to_html(child)
            if child_html:
                content_parts.append(child_html)
        
        content = ''.join(content_parts)
        
        # Wrap with HTML tags if we have styling
        if opening_tag:
            return f"{opening_tag}{content}{closing_tag}"
        else:
            return content
    
    def _table_to_html(self, table_element) -> Optional[Dict]:
        """Convert an ODT table to HTML table structure."""
        rows = table_element.getElementsByTagName('table:table-row')
        if not rows:
            return None
        
        table_data = []
        
        for row in rows:
            cells = row.getElementsByTagName('table:table-cell')
            row_data = []
            
            for cell in cells:
                cell_html = self._element_to_html(cell)
                row_data.append(cell_html.strip())
            
            if any(cell.strip() for cell in row_data):  # Only add non-empty rows
                table_data.append(row_data)
        
        if not table_data:
            return None
        
        return {
            'type': 'table',
            'rows': table_data,
            'html': self._table_data_to_html_table(table_data)
        }
    
    def _table_data_to_html_table(self, table_data: List[List[str]]) -> str:
        """Convert table data to HTML table format."""
        if not table_data:
            return ""
        
        html_parts = ["<table>"]
        
        for i, row in enumerate(table_data):
            html_parts.append("<tr>")
            # First row might be headers
            cell_tag = "th" if i == 0 and self._looks_like_header_row(row) else "td"
            
            for cell in row:
                html_parts.append(f"<{cell_tag}>{cell}</{cell_tag}>")
            html_parts.append("</tr>")
        
        html_parts.append("</table>")
        return "".join(html_parts)
    
    def _looks_like_header_row(self, row: List[str]) -> bool:
        """Heuristic to determine if a row looks like a header row."""
        # Simple heuristic: if most cells are short and don't contain numbers
        if not row:
            return False
        
        short_cells = sum(1 for cell in row if len(cell.strip()) < 15)
        numeric_cells = sum(1 for cell in row if re.search(r'\d+', cell))
        
        return short_cells >= len(row) * 0.7 and numeric_cells < len(row) * 0.5
    
    def _get_recursive_text_list(self, node) -> List:
        """Get text content recursively, preserving structure."""
        text_parts = []
        
        for child in node.childNodes:
            if child.nodeType == child.TEXT_NODE:
                content = child.data.strip()
                if content:
                    text_parts.append(content)
            elif child.nodeType == child.ELEMENT_NODE:
                content = self._get_recursive_text_list(child)
                if content:
                    text_parts.append(content)
        
        return text_parts
    
    def _concat_text_parts(self, parts: List, separator: str = "") -> str:
        """Concatenate text parts, handling nested lists."""
        result = []
        
        for part in parts:
            if isinstance(part, str):
                result.append(part)
            elif isinstance(part, list):
                result.extend(self._flatten_text_list(part))
        
        return separator.join(result)
    
    def _flatten_text_list(self, text_list: List) -> List[str]:
        """Flatten nested text lists into a single list of strings."""
        result = []
        for item in text_list:
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, list):
                result.extend(self._flatten_text_list(item))
        return result
    
    def _postprocess_title(self, title: str) -> str:
        """Clean up title formatting to match index."""
        return title.replace(",", ", ").replace("(", " (").replace("  ", " ")
    
    def _prune_empty_elements(self, node):
        """Remove empty elements (from your notebook)."""
        for child in list(node.childNodes):
            if child.nodeType == child.ELEMENT_NODE:
                self._prune_empty_elements(child)
                
                # Remove if empty and only has style attributes
                if (not child.childNodes and 
                    (not child.attributes or 
                     (child.attributes.length == 1 and 
                      child.attributes.keys() == ['text:style-name']))):
                    node.removeChild(child)
    
    def _validate_extraction(self, monster_data: Dict):
        """Validate that extraction was complete."""
        extracted_names = set(monster_data.keys())
        
        print(f"Extracted {len(extracted_names)} monsters")
        print(f"Index contains {len(self.monster_names_from_index)} monsters")
        
        if self.monster_names_from_index:
            missing_from_extraction = self.monster_names_from_index - extracted_names
            extra_in_extraction = extracted_names - self.monster_names_from_index
            
            if missing_from_extraction:
                print(f"Warning: Missing from extraction: {missing_from_extraction}")
            
            if extra_in_extraction:
                print(f"Warning: Extra in extraction: {extra_in_extraction}")
            
            if not missing_from_extraction and not extra_in_extraction:
                print("✓ Extraction matches index perfectly!")


def main():
    parser = argparse.ArgumentParser(description='Extract monster data from Basic Fantasy RPG Field Guide')
    parser.add_argument('--field-guide', default='data/Field-Guide-Omnibus-r4.odt',
                        help='Path to field guide ODT file')
    parser.add_argument('--output', default='monsters.json',
                        help='Output JSON file path')
    
    args = parser.parse_args()
    
    # Check if field guide exists
    field_guide_path = Path(args.field_guide)
    if not field_guide_path.exists():
        print(f"Error: Field guide not found at {field_guide_path}")
        return 1
    
    try:
        # Extract monster data
        extractor = MonsterExtractor(args.field_guide)
        data = extractor.extract_monsters()
        
        # Save to JSON
        output_path = Path(args.output)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Monster data saved to {output_path}")
        print(f"✓ Extracted {len(data)} monsters")
        
        return 0
        
    except Exception as e:
        print(f"Error during extraction: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit(main())