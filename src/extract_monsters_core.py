"""
This script extracts structured monster data from the ODT rules document,
specifically from Chapter 6 (Monster Descriptions).
"""

import json
import logging
import zipfile
from pathlib import Path
from typing import Optional, Any
from xml.dom.minidom import parseString, Element, Node
import argparse

from xml_utils import ODTStyleParser


# Set up logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class RulesMonsterExtractor:
    """Main class for extracting monster data from ODT rules document."""

    def __init__(self, odt_path: str):
        self.odt_path = Path(odt_path)
        self.style_parser = ODTStyleParser()
        self.dom = None

    def extract_monsters(self) -> dict[str, Any]:
        """Main extraction method."""
        logger.info("Loading ODT file...")
        self._load_odt()

        logger.info("Parsing styles...")
        self.style_parser.parse_styles(self.dom)

        logger.info("Extracting monster data")
        monster_data = self._extract_monster_data()

        logger.info("Validating extraction...")
        self._validate_extraction(monster_data)

        return monster_data

    def _load_odt(self):
        """Load and parse the ODT file."""
        with zipfile.ZipFile(self.odt_path, "r") as odt_zip:
            content_xml = odt_zip.read("content.xml")
            self.dom = parseString(content_xml)

    def _extract_monster_data(self) -> dict[str, dict]:
        """Extract all monster data from Chapter 6 (Monster Descriptions)."""
        text_element = self.dom.getElementsByTagName("office:text")[0]
        headers = text_element.getElementsByTagName("text:h")

        # Find "Monster Descriptions" section (Level 2 header)
        monster_desc_index = None
        for i, header in enumerate(headers):
            text_content = self._get_text_content(header).strip()
            outline_level = header.getAttribute("text:outline-level")
            if text_content == "Monster Descriptions" and outline_level == "2":
                monster_desc_index = i
                break

        if monster_desc_index is None:
            raise ValueError(
                "Could not find 'Monster Descriptions' section in document"
            )

        # Find where monsters section ends (next Level 1 header containing "PART")
        monsters_end_index = None
        for i in range(monster_desc_index + 1, len(headers)):
            header = headers[i]
            outline_level = header.getAttribute("text:outline-level")
            text_content = self._get_text_content(header).strip().upper()
            if outline_level == "1" and "PART" in text_content:
                monsters_end_index = i
                logger.info(
                    f"Found end of monsters section at header: '{text_content}'"
                )
                break

        if monsters_end_index is None:
            monsters_end_index = len(headers)
            logger.warning("No end boundary found, processing until end of document")

        # Get all monster headers (Level 3 headers between Monster Descriptions and next PART)
        monster_headers = headers[monster_desc_index + 1 : monsters_end_index]
        logger.info(f"Found {len(monster_headers)} monster entries to process")

        # Process each monster
        monster_data = {}

        for i, monster_header in enumerate(monster_headers):
            monster_name = self._extract_monster_name_from_header(monster_header)
            if not monster_name:
                logger.warning(f"Could not extract name from header {i}")
                continue

            logger.debug(f"Processing: {monster_name}")

            # Find content between this monster header and the next one
            next_monster_header = (
                monster_headers[i + 1] if i + 1 < len(monster_headers) else None
            )
            monster_content = self._get_monster_content(
                monster_header, next_monster_header
            )

            # Process the content
            processed_content = self._process_monster_content(monster_content)
            monster_data[monster_name] = processed_content

        return monster_data

    def _extract_monster_name_from_header(self, header_element) -> Optional[str]:
        """Extract monster name from header element."""
        text = self._get_text_content(header_element).strip()
        return text if text else None

    def _get_monster_content(
        self, monster_header, next_monster_header
    ) -> list[Element]:
        """Get all elements between this monster header and the next one."""
        content_elements = []
        current = monster_header.nextSibling

        while current and current != next_monster_header:
            if current.nodeType == current.ELEMENT_NODE:
                content_elements.append(current)
            current = current.nextSibling

        return content_elements

    def _process_monster_content(self, elements: list[Element]) -> dict:
        """Process all content elements for a single monster."""
        content = {
            "description_paragraphs": [],
            "tables": [],
            "other_elements": [],
            "source": "Basic Fantasy RPG Rules",
        }

        for element in elements:
            if not hasattr(element, "tagName"):
                continue

            if element.tagName == "text:p":
                # Paragraph - likely description
                para_html = self._element_to_html(element)
                if para_html.strip():
                    content["description_paragraphs"].append(para_html)

            elif element.tagName == "table:table":
                # Table - likely stats
                table_data = self._table_to_html(element)
                if table_data:
                    content["tables"].append(table_data)

            else:
                # Other element types
                other_html = self._element_to_html(element)
                if other_html.strip():
                    content["other_elements"].append(
                        {"type": element.tagName, "html": other_html}
                    )

        return content

    def _element_to_html(self, element) -> str:
        """Convert an ODT element to HTML with styling preserved."""
        if element.nodeType == Node.TEXT_NODE:
            return element.data

        if not hasattr(element, "tagName"):
            return ""

        # Get style information
        style_name = element.getAttribute("text:style-name")
        opening_tag, closing_tag = self.style_parser.get_html_tags(style_name)

        # Process children recursively
        content_parts = []
        for child in element.childNodes:
            child_html = self._element_to_html(child)
            if child_html:
                content_parts.append(child_html)

        content = "".join(content_parts)

        # Wrap with HTML tags if we have styling
        if opening_tag:
            return f"{opening_tag}{content}{closing_tag}"
        else:
            return content

    def _table_to_html(self, table_element) -> Optional[dict]:
        """Convert an ODT table to HTML table structure."""
        rows = table_element.getElementsByTagName("table:table-row")
        if not rows:
            return None

        table_data = []

        for row in rows:
            cells = row.getElementsByTagName("table:table-cell")
            row_data = []

            for cell in cells:
                cell_html = self._element_to_html(cell)
                row_data.append(cell_html.strip())

            if any(cell.strip() for cell in row_data):  # Only add non-empty rows
                table_data.append(row_data)

        if not table_data:
            return None

        return {
            "type": "table",
            "rows": table_data,
            "html": self._table_data_to_html_table(table_data),
        }

    def _table_data_to_html_table(self, table_data: list[list[str]]) -> str:
        """Convert table data to HTML table format."""
        if not table_data:
            return ""

        html_parts = ["<table>"]

        for i, row in enumerate(table_data):
            html_parts.append("<tr>")
            # For the first row, check if it contains typical monster stat headers
            cell_tag = "th" if i == 0 and self._is_stat_header_row(row) else "td"

            for cell in row:
                html_parts.append(f"<{cell_tag}>{cell}</{cell_tag}>")
            html_parts.append("</tr>")

        html_parts.append("</table>")
        return "".join(html_parts)

    def _is_stat_header_row(self, row: list[str]) -> bool:
        """Determine if a row contains monster stat headers."""
        if not row:
            return False

        # Check for common monster stat headers
        stat_headers = {
            "ac",
            "armor class",
            "hd",
            "hit dice",
            "hp",
            "hit points",
            "move",
            "movement",
            "attacks",
            "damage",
            "no. appearing",
            "save as",
            "morale",
            "treasure type",
            "xp",
        }

        # Convert row to lowercase for comparison
        row_text = " ".join(cell.lower().strip() for cell in row)

        # Check if any known stat headers appear in this row
        header_matches = sum(1 for header in stat_headers if header in row_text)

        # If we find multiple stat headers, it's likely a header row
        return header_matches >= 2

    def _get_text_content(self, element) -> str:
        """Recursively get all text content from an element."""
        text = ""
        for child in element.childNodes:
            if child.nodeType == child.TEXT_NODE:
                text += child.data
            elif child.nodeType == child.ELEMENT_NODE:
                text += self._get_text_content(child)
        return text

    def _validate_extraction(self, monster_data: dict):
        """Validate that extraction was complete."""
        extracted_count = len(monster_data)

        logger.info(
            f"Extracted {extracted_count} monsters from Basic Fantasy RPG Rules"
        )

        # Validate that each monster has required components
        monsters_with_tables = 0
        monsters_with_descriptions = 0

        for name, data in monster_data.items():
            if data.get("tables"):
                monsters_with_tables += 1
            if data.get("description_paragraphs"):
                monsters_with_descriptions += 1

        logger.info(f"{monsters_with_tables} monsters have stat tables")
        logger.info(f"{monsters_with_descriptions} monsters have descriptions")


def main():
    parser = argparse.ArgumentParser(
        description="Extract monster data from Basic Fantasy RPG Rules"
    )
    parser.add_argument(
        "input",
        help="Path to rules ODT file",
    )
    parser.add_argument("output", help="Output JSON file path")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Extract monster data
    extractor = RulesMonsterExtractor(args.input)
    data = extractor.extract_monsters()

    # Save to JSON
    output_path = Path(args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info(f"Monster data saved to {output_path}")


if __name__ == "__main__":
    main()
