import json

from app.services.docx_crawler.translate.config import OUTPUT_SENTENCES


def extract_key_data_for_totals_sentence(total_with_sae: list[dict], compounds: list[str]) -> list[dict]:
    indexed = {entry["compound"]: entry for entry in total_with_sae}
    summary = []
    for compound in compounds:
        entry = indexed.get(compound)
        if entry is None:
            print(f"compound: {compound} not found in the data..")
            continue
        summary.append({"compound": entry["compound"], "count": entry["count"]})
    return summary


def fill_in_totals_sentence(key_data: list[dict], sentence_template: str) -> str:
    substitutions = {}
    for index, compound in enumerate(key_data):
        n = index + 1
        substitutions[f"C{n}"] = compound["compound"]
        substitutions[f"C{n}N"] = str(compound["count"])

    return sentence_template.format(**substitutions)


def generate_totals_sentence(total_with_sae: list[dict], compounds: list[str]) -> str:
    template = OUTPUT_SENTENCES.get("totals")
    key_data = extract_key_data_for_totals_sentence(total_with_sae, compounds)
    return fill_in_totals_sentence(key_data, template)


def translate_parsed_docx_content(parsed_content: dict, compounds: list[str]) -> list[dict]:
    translated_tables = []
    parsed_tables = parsed_content.get("tables", [])

    for table in parsed_tables:
        total_with_sae = table.get("total_with_SAE", [])
        term_data = table.get("term_data", [])

        summary_sentences = {
            "totals_sentence": generate_totals_sentence(total_with_sae, compounds),
            "per_term_sentences": [],
        }

        for term in term_data:
            term_output = {"term": term["term"]}
            # TODO (yours): build the per-term sentence here.
            #   - pull the two selected compounds' int_percent for this term
            #   - pick the branch (none / equal / one / both) -- check none before equal
            #   - fill OUTPUT_SENTENCES["per-term"][branch] with .format
            summary_sentences["per_term_sentences"].append(term_output)

        translated_tables.append({
            "table_number": table.get("table_number"),
            "table_title": table.get("table_title"),
            "selected_compounds": compounds,
            "summary_sentences": summary_sentences,
        })

        print(f"translated_tables: {translated_tables}")

    return translated_tables