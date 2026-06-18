import json

from app.services.docx_crawler.translate.config import OUTPUT_SENTENCES


def extract_key_data_for_totals_sentence(compounds_data: dict, compounds: list):
    indexed_compound_data = {c["compound"]: c for c in compounds_data}
    compounds_summary = []
    
    for compound in compounds:
        compound_data = indexed_compound_data.get(compound)
        if compound_data is None:
            print(f"compound: {compound} not found in the data..")
            continue
        else:
            key_data = {
                "compound": compound_data['compound'], "count": compound_data['total_with_SAE']
            }
            compounds_summary.append(key_data)

    return compounds_summary


def fill_in_totals_sentence(key_data: list[dict], sentence_template: str) -> str:
    substitutions = {}
    for index, compound in enumerate(key_data):
        n = index + 1
        substitutions[f"C{n}"] = compound["compound"]
        substitutions[f"C{n}N"] = str(compound["count"])

    return sentence_template.format(**substitutions)

def generate_totals_sentence(compounds_data: dict, compounds: list[str]):
    totals_sentence_template = OUTPUT_SENTENCES.get("totals")

    extracted_key_data = extract_key_data_for_totals_sentence(compounds_data, compounds)

    completed_totals_sentence = fill_in_totals_sentence(extracted_key_data, totals_sentence_template)

    return completed_totals_sentence



def translate_parsed_docx_content(parsed_content: dict, compounds: list):
    translated_tables = []
    parsed_tables = parsed_content.get("tables", [])

    for table in parsed_tables:
        transformed_table_content = {
            "table_number": table.get("table_number"),
            "table_title": table.get("table_title")
        }

        compounds_data = table.get("compounds_data")
        summary_sentences = {
            "totals_sentence": generate_totals_sentence(compounds_data, compounds),
            "per-term_sentences": []
        }


        for term in compounds_data["terms"]:
            term_output = {"term": term["term"]}


        print(f"trans_tables: {transformed_table_content}")
        print(f"sum_sent: {summary_sentences}\n\n")




    return 1
