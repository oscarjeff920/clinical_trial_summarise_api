import json
import os
import re

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


def parse_table_title(title_text: str) -> tuple[str | None, str]:
    """
    Extracts the table number and description from a title string.

      "Table 2.1.1 Serious AEs by Preferred term"
      -> ("2.1.1", "Serious AEs by Preferred term")
    """
    pattern = r"^[Tt]able\s+(\d+(?:\.\d+)*)[\s.:]*(.*)$"
    match = re.match(pattern, title_text.strip())
    if match:
        return match.group(1), match.group(2).strip()
    return None, title_text.strip()


def iter_block_items(document: Document):
    """
    Walk the document body in order, yielding each Paragraph or Table as we
    encounter it. python-docx only gives document.paragraphs OR document.tables
    separately, with no indication of how they interleave; this restores order.
    """
    body = document.element.body
    for child in body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, document)
        elif isinstance(child, CT_Tbl):
            yield Table(child, document)


def is_sae_title(text: str) -> bool:
    """
    Check if a paragraph's text looks like an SAE table title.

    FIX: leading word-boundary instead of plain substring. This avoids a keyword
    accidentally matching inside an unrelated word, while still matching plurals
    such as "SAEs" (\\bsae matches the start of "saes").
    """
    lowered = text.lower()
    return any(re.search(rf"\b{re.escape(keyword)}", lowered) for keyword in SAE_KEYWORDS)


def is_totals_row(first_cell_text: str) -> bool:
    """Check if a table row is the 'totals' row, based on its first cell."""
    lowered = first_cell_text.lower()
    matched = sum(1 for word in TOTALS_ROW_KEYWORDS if word in lowered)
    return matched >= TOTALS_ROW_MIN_MATCHES


def first_int(text: str) -> int:
    """
    Pull the leading integer out of a cell, tolerating thousands separators and
    trailing text. FIX: replaces the old `str.isdigit()` check, which silently
    returned 0 for values like '19 (100%)' or '1,234'.
    """
    match = re.search(r"\d[\d,]*", text or "")
    return int(match.group(0).replace(",", "")) if match else 0


def parse_cell_value(val_str: str) -> tuple[str, str]:
    """
    Splits a cell like '1 (33%)' into ('1', '33%'), or '0'/'' into ('0', '0%').

    FIX: strip spaces inside the bracket so '1 (33 %)' -> ('1', '33%').
    NOTE/assumption: percentages only ever come from brackets (per the spec, we
    extract rather than calculate). A bare non-zero count therefore has no
    percentage to report; in the sample data bare cells are always '0'.
    """
    val_str = (val_str or "").strip()
    if not val_str or val_str == "0":
        return "0", "0%"

    if "(" in val_str:
        count, _, rest = val_str.partition("(")
        percent = rest.replace(")", "").replace(" ", "").strip()
        return count.strip(), percent

    return val_str, "0%"


def find_sae_tables(document: Document):
    """
    Walk the document, tracking the most recent non-empty paragraph as a
    candidate title. When we hit a table, if that candidate matches an SAE
    keyword we keep the table. The title is reset after every table so it
    can't accidentally attach to a second, unrelated table further down.
    """
    candidate_title = None
    matches = []

    for block in iter_block_items(document):
        if isinstance(block, Paragraph):
            text = block.text.strip()
            if text:
                candidate_title = text
            # blank paragraph -> leave candidate_title as-is, so a blank line
            # between the title and the table doesn't break the pairing
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
            candidate_title = None

    return matches


def extract_found_tables_into_json(found: list) -> dict:
    extracted_data = {"tables": []}

    for match in found:
        # FIX: use the keys find_sae_tables actually emits. The previous chain
        # looked for "table_description"/"raw_title" (neither exists) and only
        # worked by falling through to "table_name".
        title = match.get("table_name") or match.get("title", "")

        table_data = {
            "table_number": match.get("table_number", ""),
            "table_title": title,
            "compounds_data": [],
        }

        table = match["table"]
        col_to_compound = {}
        compounds_list = []

        # -----------------------------------------------------------------
        # FIX: locate the header row by finding the "Preferred Term" cell,
        # instead of assuming it's row 0. Also remember which column the term
        # lives in rather than hardcoding column 0.
        # -----------------------------------------------------------------
        header_idx = None
        term_col = 0
        for r_idx, row in enumerate(table.rows):
            for c_idx, cell in enumerate(row.cells):
                if "preferred term" in cell.text.strip().lower():
                    header_idx, term_col = r_idx, c_idx
                    break
            if header_idx is not None:
                break

        # Fallback: first non-empty row is the header (old behaviour).
        if header_idx is None:
            for r_idx, row in enumerate(table.rows):
                if any(cell.text.strip() for cell in row.cells):
                    header_idx, term_col = r_idx, 0
                    break

        if header_idx is None:
            continue  # genuinely empty table

        # ---------------------------------------------------------------------
        # HEADER ROW: every column except the term column is a compound.
        # ---------------------------------------------------------------------
        header_cells = [cell.text.strip() for cell in table.rows[header_idx].cells]
        for col_idx, header_text in enumerate(header_cells):
            if col_idx == term_col or not header_text:
                continue
            compound_entry = {
                "compound": header_text,  # 'Placebo' / 'Compound X' as written
                "total_with_SAE": 0,
                "terms": [],
            }
            compounds_list.append(compound_entry)
            col_to_compound[col_idx] = compound_entry

        # ---------------------------------------------------------------------
        # DATA ROWS: classify each row after the header as totals or term row.
        # ---------------------------------------------------------------------
        for row in table.rows[header_idx + 1:]:
            cells = [cell.text.strip() for cell in row.cells]
            if term_col >= len(cells) or not cells[term_col]:
                continue  # skip structurally empty rows

            label = cells[term_col]

            if is_totals_row(label):
                for col_idx, entry in col_to_compound.items():
                    if col_idx < len(cells):
                        entry["total_with_SAE"] = first_int(cells[col_idx])
            else:
                for col_idx, entry in col_to_compound.items():
                    if col_idx < len(cells):
                        count, percent = parse_cell_value(cells[col_idx])
                        entry["terms"].append(
                            {"term": label, "count": count, "percent": percent}
                        )

        table_data["compounds_data"] = compounds_list
        extracted_data["tables"].append(table_data)

    return extracted_data


def extract_file_name(file_path: str):
    return os.path.splitext(os.path.basename(file_path))[0]


def parse_docx_file(file_path: str):
    doc = Document(file_path)
    found = find_sae_tables(doc)
    return extract_found_tables_into_json(found)


if __name__ == "__main__":
    file_path = "mock_docx_files/client1_ae copy.docx"
    parsed_json = parse_docx_file(file_path)
    with open("parsed_data.json", "w") as f:
        json.dump(parsed_json, f)