from docx.document import Document

from app.services.docx_crawler.extract.extract import parse_docx_file
from app.services.docx_crawler.translate.translate import translate_parsed_docx_content


def run_docx_content_extraction(document: Document, compound_a: str, compound_b: str) -> dict[str, list[dict]]:
    parsed_content = parse_docx_file(document)
    translated_content = translate_parsed_docx_content(
        parsed_content, [compound_a, compound_b]
    )

    return translated_content
