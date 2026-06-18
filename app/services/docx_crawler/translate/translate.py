from typing import Tuple

from app.services.docx_crawler.translate.config import OUTPUT_SENTENCES
from app.services.docx_crawler.translate.exceptions import CompoundNotFoundError


# ---- pure helpers -------------------------------------------------------


def select_compounds(rows: list[dict], compounds: list[str]) -> list[dict]:
    """Return the rows for the requested compounds, in request order.
    Raises if any requested compound is absent."""
    indexed = {row["compound"].lower(): row for row in rows}
    missing = [c for c in compounds if c.lower() not in indexed]
    if missing:
        raise CompoundNotFoundError(f"Compound/s not found in table data: {missing}")
    return [indexed[c.lower()] for c in compounds]


def base_substitutions(key_data: list[dict]) -> dict:
    """C1/C1N, C2/C2N ... from each compound's name and count."""
    subs = {}
    for index, compound in enumerate(key_data):
        n = index + 1
        subs[f"C{n}"] = compound["compound"]
        subs[f"C{n}N"] = compound["count"]
    return subs


def per_term_substitutions(key_data: list[dict], term: str) -> dict:
    """Adds the term and each present percentage to the base substitutions."""
    subs = base_substitutions(key_data)
    subs["T"] = term
    for index, compound in enumerate(key_data):
        if compound["percent_str"] is not None:
            subs[f"C{index + 1}%"] = compound["percent_str"]
    return subs


def fill_template(template: str, substitutions: dict) -> str:
    return template.format(**substitutions)


def select_per_term_template(
    comp_a: dict, comp_b: dict, templates: dict
) -> Tuple[str, list[dict]]:
    """Pick the sentence template and order the compounds so the rendered
    sentence is truthful (higher % first for 'both', non-zero first for 'one')."""
    a, b = comp_a["percent"], comp_b["percent"]

    if a == b:
        return templates["none"] if a == 0 else templates["equal"], [comp_a, comp_b]
    if a > 0 and b > 0:
        ordered = [comp_b, comp_a] if a < b else [comp_a, comp_b]
        return templates["both"], ordered
    # exactly one is zero
    ordered = [comp_a, comp_b] if a > 0 else [comp_b, comp_a]
    return templates["one"], ordered


# ---- sentence generators ------------------------------------------------


def generate_totals_sentence(total_with_sae: list[dict], compounds: list[str]) -> str:
    key_data = select_compounds(total_with_sae, compounds)
    return fill_template(OUTPUT_SENTENCES["totals"], base_substitutions(key_data))


def generate_per_term_sentence(term_data: dict, compounds: list[str]) -> str:
    comp_a, comp_b = select_compounds(term_data["compounds"], compounds)
    template, ordered = select_per_term_template(
        comp_a, comp_b, OUTPUT_SENTENCES["per_term"]
    )
    return fill_template(template, per_term_substitutions(ordered, term_data["term"]))


def translate_parsed_docx_content(
    parsed_content: dict, compounds: list[str]
) -> dict[str, list[dict]]:
    if len(compounds) != 2:
        raise ValueError(
            f"exactly two compounds are required, got {len(compounds)}: {compounds}"
        )

    translated_tables = []
    for table in parsed_content.get("tables", []):
        per_term = [
            {
                "term": term["term"],
                "per_term_sentence": generate_per_term_sentence(term, compounds),
            }
            for term in table.get("term_data", [])
        ]
        translated_tables.append(
            {
                "table_number": table.get("table_number"),
                "table_title": table.get("table_title"),
                "selected_compounds": compounds,
                "summary_sentences": {
                    "totals_sentence": generate_totals_sentence(
                        table.get("total_with_SAE", []), compounds
                    ),
                    "per_term_sentences": per_term,
                },
            }
        )
    return {"tables": translated_tables}
