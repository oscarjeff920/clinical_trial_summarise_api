import json

from app.services.docx_crawler.translate.config import OUTPUT_SENTENCES


def extract_key_data_for_totals_sentence(
    total_with_sae: list[dict], compounds: list[str]
) -> list[dict]:
    indexed = {entry["compound"]: entry for entry in total_with_sae}
    summary = []
    for compound in compounds:
        entry = indexed.get(compound)
        if entry is None:
            print(f"compound: {compound} not found in the data..")
            continue
        summary.append({"compound": entry["compound"], "count": entry["count"]})
    return summary


def base_generate_substitutions(
    key_data: list[dict]
) -> dict:
    substitutions = {}
    for index, compound in enumerate(key_data):
        n = index + 1
        substitutions[f"C{n}"] = compound["compound"]
        substitutions[f"C{n}N"] = str(compound["count"])

    return substitutions


def generate_per_term_substitutions(
    key_data: list[dict], term: str
) -> dict:
    substitutions = base_generate_substitutions(key_data)
    substitutions["T"] = term
    for index, compound in enumerate(key_data):
        n = index + 1
        substitutions[f"C{n}%"] = str(compound["percent"])

    return substitutions


def fill_in_template_string_with_substitutions(template, substitutions):
    return template.format(**substitutions)


def generate_totals_sentence(total_with_sae: list[dict], compounds: list[str]) -> str:
    template = OUTPUT_SENTENCES.get("totals")
    key_data = extract_key_data_for_totals_sentence(total_with_sae, compounds)
    substitutions = base_generate_substitutions(key_data)
    return fill_in_template_string_with_substitutions(template, substitutions)


def generate_per_term_sentence(term_data: dict, compounds: list[str]):
    indexed = {entry["compound"]: entry for entry in term_data["compounds"]}

    selected_compounds = [{"compound": compound} for compound in compounds]
    for idx, compound in enumerate(compounds):
        if compound in indexed:
            selected_compounds.append(indexed[compound].copy())

    print(f"selected comps: {selected_compounds}")

    per_term_sentences = OUTPUT_SENTENCES.get("per-term")

    comp_a, comp_b = selected_compounds[0], selected_compounds[1]
    comps = [comp_a, comp_b]
    if comp_a["int_percent"] > 0 and comp_b["int_percent"] > 0:
        per_term_sentence_template = per_term_sentences.get("both")
    elif comp_a["int_percent"] == comp_b["int_percent"]:
        if comp_a["int_percent"] == 0:
            per_term_sentence_template = per_term_sentences.get("none")
        else:
            per_term_sentence_template = per_term_sentences.get("equal")
    elif comp_a["int_percent"] == 0 and comp_b["int_percent"] > 0:
        per_term_sentence_template = per_term_sentences.get("one")
        comps = [comp_b, comp_a]
    elif comp_a["int_percent"] > 0 and comp_b["int_percent"] == 0:
        per_term_sentence_template = per_term_sentences.get("one")
    else:
        raise ValueError

    substitutions = generate_per_term_substitutions(comps, term_data['term'])
    completed_sentence = fill_in_template_string_with_substitutions(per_term_sentence_template, substitutions)

    return completed_sentence


def translate_parsed_docx_content(
    parsed_content: dict, compounds: list[str]
) -> list[dict]:
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
            generated_per_term_sentence = generate_per_term_sentence(term, compounds)

            term_output = {
                "term": term["term"],
                "per-term_sentence": generated_per_term_sentence,
            }

            summary_sentences["per_term_sentences"].append(term_output)

        translated_tables.append(
            {
                "table_number": table.get("table_number"),
                "table_title": table.get("table_title"),
                "selected_compounds": compounds,
                "summary_sentences": summary_sentences,
            }
        )

        print(f"translated_tables: {translated_tables}")

    return translated_tables
