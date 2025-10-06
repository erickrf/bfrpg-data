from xml.dom.minidom import parseString
import zipfile


def parse_dom(path: str):
    """
    Load the DOM of an XML document.

    :return:
    """
    with zipfile.ZipFile(path, "r") as odt_zip:
        content_xml = odt_zip.read("content.xml")
        dom = parseString(content_xml)

    return dom


def explore_element(element, depth=1, prefix=""):
    """
    Explore the contents of some XML element, printing results to the screen.
    """
    print(f"{prefix}Tag: {element.tagName}")
    print(f"{prefix}Children:")
    for child in element.childNodes:
        print(f"{prefix}    {child}")

    depth -= 1
    if depth:
        prefix += "  "
        for child in element.childNodes:
            explore_element(child, depth, prefix)


def get_direct_text(node):
    return "".join(
        child.data for child in node.childNodes if child.nodeType == child.TEXT_NODE
    ).strip()


def get_recursive_text(node) -> list[str | list[str]]:
    """
    Get all the text of an XML node and its descendents.

    :return: a list with the text of each child
    """
    text_parts = []

    for child in node.childNodes:
        if child.nodeType == child.TEXT_NODE:
            content = child.data
        elif child.nodeType == child.ELEMENT_NODE:
            content = get_recursive_text(child)
        else:
            continue

        if content:
            text_parts.append(content)

    return text_parts


def concat_text_parts(parts: list[list[str] | str], separator="") -> str:
    """
    Concatenate strings and lists of strings in the order they appear.
    """
    result = []

    for part in parts:
        if isinstance(part, str):
            result.append(part)
        elif isinstance(part, list):
            result.extend(concat_text_parts(part, separator))

    return separator.join(result)


def prune_empty_elements(node):
    # Work on a *copy* of childNodes list because we may modify it while iterating
    for child in list(node.childNodes):
        if child.nodeType == child.ELEMENT_NODE:
            prune_empty_elements(child)  # recurse into children

            # After recursion, check if it's empty
            if not child.childNodes and (
                not child.attributes.length
                or child.attributes.keys() == set(["text:style-name"])
            ):
                node.removeChild(child)


class ODTStyleParser:
    """Parses ODT style definitions and converts them to HTML equivalents."""

    def __init__(self):
        self.style_map = {}

    def parse_styles(self, dom):
        """Extract style definitions from ODT document."""
        # Get automatic styles
        auto_styles = dom.getElementsByTagName("office:automatic-styles")
        if auto_styles:
            self._parse_style_section(auto_styles[0])

        # Get document styles if present
        doc_styles = dom.getElementsByTagName("office:styles")
        if doc_styles:
            self._parse_style_section(doc_styles[0])

    def _parse_style_section(self, style_section):
        """Parse a style section (automatic or document styles)."""
        styles = style_section.getElementsByTagName("style:style")

        for style in styles:
            style_name = style.getAttribute("style:name")
            if not style_name:
                continue

            style_properties = self._extract_style_properties(style)
            if style_properties:
                self.style_map[style_name] = style_properties

    def _extract_style_properties(self, style_element):
        """Extract formatting properties from a style element."""
        properties = {}

        # Check text properties
        text_props = style_element.getElementsByTagName("style:text-properties")
        if text_props:
            text_prop = text_props[0]

            # Font weight (bold)
            if text_prop.getAttribute("fo:font-weight") == "bold":
                properties["bold"] = True
            if text_prop.getAttribute("style:font-weight-asian") == "bold":
                properties["bold"] = True

            # Font style (italic)
            if text_prop.getAttribute("fo:font-style") == "italic":
                properties["italic"] = True
            if text_prop.getAttribute("style:font-style-asian") == "italic":
                properties["italic"] = True

            # Font family
            font_family = text_prop.getAttribute("style:font-name")
            if font_family:
                properties["font_family"] = font_family

            # Font size
            font_size = text_prop.getAttribute("fo:font-size")
            if font_size:
                properties["font_size"] = font_size

        # Check paragraph properties
        para_props = style_element.getElementsByTagName("style:paragraph-properties")
        if para_props:
            para_prop = para_props[0]

            # Text alignment
            text_align = para_prop.getAttribute("fo:text-align")
            if text_align:
                properties["text_align"] = text_align

        return properties

    def get_html_tags(self, style_name: str) -> tuple[str, str]:
        """Get opening and closing HTML tags for a style."""
        if style_name not in self.style_map:
            return "", ""

        properties = self.style_map[style_name]
        tags = []

        # Convert properties to HTML tags
        if properties.get("bold"):
            tags.append("strong")
        if properties.get("italic"):
            tags.append("em")

        # Build opening and closing tags
        opening = "".join(f"<{tag}>" for tag in tags)
        closing = "".join(f"</{tag}>" for tag in reversed(tags))

        return opening, closing


def element_to_html(element, style_parser) -> str:
    """Convert an ODT element to HTML with styling preserved."""
    if element.nodeType == element.TEXT_NODE:
        return element.data

    if not hasattr(element, "tagName"):
        return ""

    # Get style information
    style_name = element.getAttribute("text:style-name")
    opening_tag, closing_tag = style_parser.get_html_tags(style_name)

    # Process children recursively
    content_parts = []
    for child in element.childNodes:
        child_html = element_to_html(child, style_parser)
        if child_html:
            content_parts.append(child_html)

    content = "".join(content_parts)

    # Wrap with HTML tags if we have styling
    if opening_tag:
        return f"{opening_tag}{content}{closing_tag}"
    else:
        return content


def convert_table_to_html(node, style_parser: ODTStyleParser) -> str:
    """
    Convert an XML table node to HTML.
    """
    rows = node.getElementsByTagName("table:table-row")
    if not rows:
        return ""

    table_data = []

    for row in rows:
        cells = row.getElementsByTagName("table:table-cell")
        row_data = []

        for cell in cells:
            cell_html = element_to_html(cell, style_parser)
            row_data.append(cell_html.strip())

        if any(cell.strip() for cell in row_data):  # Only add non-empty rows
            table_data.append(row_data)

    html_parts = ["<table>"]

    for i, row in enumerate(table_data):
        html_parts.append("<tr>")
        cell_tag = "th" if i == 0 else "td"

        for cell in row:
            html_parts.append(f"<{cell_tag}>{cell}</{cell_tag}>")
        html_parts.append("</tr>")

    html_parts.append("</table>")
    return "".join(html_parts)
