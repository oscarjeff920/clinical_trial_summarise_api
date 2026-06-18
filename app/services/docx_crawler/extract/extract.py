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
    """'Table 2.1.1 Serious AEs ...' -> ('2.1.1', 'Serious AEs ...')."""
    match = re.match(r"^[Tt]able\s+(\d+(?:\.\d+)*)[\s.:]*(.*)$", title_text.strip())
    if match:
        return match.group(1), match.group(2).strip()
    return None, title_text.strip()


def iter_block_items(document: Document):
    """Yield each Paragraph or Table in document order. python-docx exposes
    paragraphs and tables separately, losing their interleaving; this restores it."""
    for child in document.element.body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, document)
        elif isinstance(child, CT_Tbl):
            yield Table(child, document)


def is_sae_title(text: str) -> bool:
    """Match an SAE keyword on a leading word boundary, so it isn't matched mid-word
    while plurals like 'SAEs' still match (\\bsae matches the start of 'saes')."""
    lowered = text.lower()
    return any(
        re.search(rf"\b{re.escape(keyword)}", lowered) for keyword in SAE_KEYWORDS
    )


def is_totals_row(first_cell_text: str) -> bool:
    """Is this the totals row, judged by keyword density in its label cell."""
    lowered = first_cell_text.lower()
    return (
        sum(1 for word in TOTALS_ROW_KEYWORDS if word in lowered)
        >= TOTALS_ROW_MIN_MATCHES
    )


def first_int(text: str) -> int:
    """Leading integer from a cell, tolerating separators/trailing text:
    '19 (100%)' -> 19, '1,234' -> 1234, '' -> 0."""
    match = re.search(r"\d[\d,]*", text or "")
    return int(match.group(0).replace(",", "")) if match else 0


def build_cell(compound_name: str, cell_text: str) -> dict:
    """
    '1 (33%)'  -> count=1, int_percent=33, percent='33%'
    '0' or ''  -> count=0, int_percent=0,  percent=None
    '3 (16 %)' -> count=3, int_percent=16, percent='16%'  (internal space dropped)
    """
    text = (cell_text or "").strip()
    if not text or text == "0":
        return {
            "compound": compound_name,
            "count": 0,
            "int_percent": 0,
            "percent": None,
        }
    if "(" in text:
        count_part, _, rest = text.partition("(")
        percent = rest.replace(")", "").replace(" ", "").strip()
        num = percent.rstrip("%")
        return {
            "compound": compound_name,
            "count": first_int(count_part),
            "int_percent": round(float(num)) if num else 0,
            "percent": percent,
        }
    # non-zero count, no bracket: count present, but no percentage to extract
    return {
        "compound": compound_name,
        "count": first_int(text),
        "int_percent": 0,
        "percent": None,
    }


def find_sae_tables(document: Document) -> list[dict]:
    """Pair each table with its preceding non-empty paragraph; keep the ones
    whose title matches an SAE keyword. Title resets after each table so it
    can't attach to an unrelated table further down."""
    candidate_title = None
    matches = []
    for block in iter_block_items(document):
        if isinstance(block, Paragraph):
            if block.text.strip():
                candidate_title = block.text.strip()
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


def locate_header(table: Table) -> tuple[int, int] | None:
    """Return (header_row_index, term_column_index), found via the 'Preferred Term'
    cell. Falls back to the first non-empty row, term column 0. None if empty."""
    for r_idx, row in enumerate(table.rows):
        for c_idx, cell in enumerate(row.cells):
            if "preferred term" in cell.text.strip().lower():
                return r_idx, c_idx
    for r_idx, row in enumerate(table.rows):
        if any(cell.text.strip() for cell in row.cells):
            return r_idx, 0
    return None


def read_term_column(
    table: Table, term_col: int, header_idx: int
) -> tuple[dict[int, str], int | None]:
    """Walk the term column. Return {row_position: term_label} for term rows
    (in table order), plus the row position of the totals row (or None)."""
    terms_by_row, totals_row = {}, None
    for row_pos, label in enumerate(
        c.text.strip() for c in table.columns[term_col].cells
    ):
        if row_pos == header_idx or not label:
            continue
        if is_totals_row(label):
            totals_row = row_pos
        else:
            terms_by_row[row_pos] = label
    return terms_by_row, totals_row


def compound_columns(
    table: Table, header_idx: int, term_col: int
) -> list[tuple[int, str]]:
    """(col_idx, compound_name) for every non-term column with a header label, in order."""
    header_cells = [c.text.strip() for c in table.rows[header_idx].cells]
    return [(i, name) for i, name in enumerate(header_cells) if i != term_col and name]


def extract_table(table: Table, table_number: str, table_title: str) -> dict | None:
    """Build one term-first table dict, or None if the table has no header."""
    header = locate_header(table)
    if header is None:
        return None
    header_idx, term_col = header
    cols = compound_columns(table, header_idx, term_col)

    term_data, total_with_sae = [], []
    for row in table.rows[header_idx + 1 :]:
        cells = [c.text.strip() for c in row.cells]
        if term_col >= len(cells) or not cells[term_col]:
            continue
        label = cells[term_col]
        if is_totals_row(label):
            for col_idx, name in cols:
                if col_idx < len(cells):
                    total_with_sae.append(
                        {"compound": name, "count": first_int(cells[col_idx])}
                    )
        else:
            compounds = [
                build_cell(name, cells[col_idx])
                for col_idx, name in cols
                if col_idx < len(cells)
            ]
            term_data.append({"term": label, "compounds": compounds})

    return {
        "table_number": table_number,
        "table_title": table_title,
        "term_data": term_data,
        "total_with_SAE": total_with_sae,
    }


def extract_found_tables_into_json(found: list[dict]) -> dict:
    tables = []
    for match in found:
        title = match.get("table_name") or match.get("title", "")
        table = extract_table(match["table"], match.get("table_number"), title)
        if table is not None:
            tables.append(table)
    return {"tables": tables}


def parse_docx_file(file_path: str) -> dict:
    return extract_found_tables_into_json(find_sae_tables(Document(file_path)))
