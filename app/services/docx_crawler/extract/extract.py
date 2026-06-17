import json
import os

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl

from app.services.docx_crawler.extract.config import (
    TOTALS_ROW_KEYWORDS,
    TOTALS_ROW_MIN_MATCHES,
    SAE_KEYWORDS,
)

import re


def parse_table_title(title_text: str) -> tuple[str | None, str]:
    """
    Extracts the table number and description from a title string.

    Example:
      "Table 2.1.1 Serious AEs by Preferred term"
      -> ("2.1.1", "Serious AEs by Preferred term")
    """
    # This regex looks for:
    # ^[Tt]able\s+  -> Starts with "Table" or "table" followed by spaces
    # (\d+(?:\.\d+)*) -> Group 1: Matches numbers separated by dots (e.g., 2, 14.2, 2.1.1)
    # [\s.:]* -> Matches any trailing spaces, periods, or colons between number and text
    # (.*)$         -> Group 2: Captures everything else until the end of the line
    pattern = r"^[Tt]able\s+(\d+(?:\.\d+)*)[\s.:]*(.*)$"

    match = re.match(pattern, title_text.strip())

    if match:
        table_number = match.group(1)
        table_description = match.group(2).strip()
        return table_number, table_description

    # Fallback: if it doesn't match the standard pattern, return None for number
    return None, title_text.strip()


def iter_block_items(document: Document):
    """
    Walk the document body in order, yielding each Paragraph or Table
    as we encounter it. This is the bit python-docx doesn't give us
    for free - by default you only get document.paragraphs (all of them,
    no tables) or document.tables (all of them, no paragraphs), with no
    indication of how they interleave.
    """
    body = document.element.body
    for child in body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, document)
        elif isinstance(child, CT_Tbl):
            yield Table(child, document)


def is_sae_title(text: str) -> bool:
    """Check if a paragraph's text looks like an SAE table title."""
    lowered = text.lower()
    return any(keyword in lowered for keyword in SAE_KEYWORDS)


def is_totals_row(first_cell_text: str) -> bool:
    """Check if a table row is the 'totals' row, based on its first cell."""
    lowered = first_cell_text.lower()
    matched = sum(1 for word in TOTALS_ROW_KEYWORDS if word in lowered)
    return matched >= TOTALS_ROW_MIN_MATCHES


def find_sae_tables(document: Document):
    """
    Walk the document, tracking the most recent non-empty paragraph as a
    candidate title. When we hit a table, check if that candidate title
    matches an SAE keyword - if so, this table is one we want.
    """
    candidate_title = None
    matches = []

    for block in iter_block_items(document):
        if isinstance(block, Paragraph):
            text = block.text.strip()
            if text:
                candidate_title = text
            # if it's a blank paragraph, we just leave candidate_title as-is
            # (so a blank line between title and table doesn't break the pairing)
        elif isinstance(block, Table):
            if candidate_title and is_sae_title(candidate_title):
                table_num, table_name = parse_table_title(candidate_title)

                matches.append(
                    {
                        "title": candidate_title,
                        "table_number": table_num,
                        "table_name": table_name,
                        "table": block,
                    }
                )
            # reset so the same title can't accidentally attach to a
            # second, unrelated table further down
            candidate_title = None

    return matches


def extract_found_tables_into_json(found: list) -> dict:
    extracted_data = {"tables": []}

    for match in found:
        # Pull table description/number extracted from the earlier step
        title = match.get(
            "table_description", match.get("table_name", match.get("raw_title", ""))
        )

        table_data = {
            "table_number": match.get("table_number", ""),
            "table_title": title,
            "compounds_data": [],
        }

        table = match["table"]
        col_to_compound = {}
        compounds_list = []

        def parse_cell_value(val_str: str) -> tuple[str, str]:
            """Splits a cell like '1 (33%)' into ('1', '33%') or '0' into ('0', '0%')"""
            val_str = val_str.strip()
            if not val_str or val_str == "0":
                return "0", "0%"

            if "(" in val_str:
                parts = val_str.split("(")
                count = parts[0].strip()
                percent = parts[1].replace(")", "").strip()
                return count, percent

            return val_str, "0%"

        for i, row in enumerate(table.rows):
            # Clean up trailing spaces and internal newlines like 'Placebo\n'
            cells = [cell.text.strip() for cell in row.cells]
            if not cells or not cells[0]:
                continue  # Skip structurally empty rows

            if i == 0:
                # -----------------------------------------------------------
                # HEADER ROW: Blindly trust whatever headers are in the table
                # -----------------------------------------------------------
                for col_idx in range(1, len(cells)):
                    header_text = cells[col_idx]

                    compound_entry = {
                        "compound": header_text,  # Extracts 'Placebo' or 'Compound X' as written
                        "total_with_SAE": 0,
                        "terms": [],
                    }
                    compounds_list.append(compound_entry)
                    col_to_compound[col_idx] = compound_entry

            elif is_totals_row(cells[0]):
                # -----------------------------------------------------------
                # TOTALS ROW: Extract integers
                # -----------------------------------------------------------
                for col_idx in range(1, len(cells)):
                    if col_idx in col_to_compound:
                        tot_str = cells[col_idx].strip()
                        total_val = int(tot_str) if tot_str.isdigit() else 0
                        col_to_compound[col_idx]["total_with_SAE"] = total_val

            else:
                # -----------------------------------------------------------
                # TERM ROW: Extract terms, counts, and percentages
                # -----------------------------------------------------------
                term_name = cells[0]
                for col_idx in range(1, len(cells)):
                    if col_idx in col_to_compound:
                        count, percent = parse_cell_value(cells[col_idx])

                        col_to_compound[col_idx]["terms"].append(
                            {"term": term_name, "count": count, "percent": percent}
                        )

        table_data["compounds_data"] = compounds_list
        extracted_data["tables"].append(table_data)

    return extracted_data


def extract_file_name(file_path: str):
    return os.path.splitext(os.path.basename(file_path))[0]


def parse_docx_file(file_path: str):
    doc = Document(file_path)
    found = find_sae_tables(doc)

    parsed_tables_into_json = extract_found_tables_into_json(found)

    return parsed_tables_into_json



if __name__ == "__main__":
    file_path = "../mock_docx_files/client1_ae copy.docx"

    parsed_json = parse_docx_file(file_path)

    with open("parsed_data.json", "w") as f:
        json.dump(parsed_json, f)