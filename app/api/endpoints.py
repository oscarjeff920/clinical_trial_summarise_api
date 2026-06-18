from fastapi import UploadFile, Form, HTTPException, File

from docx import Document

from app.api.app import medical_docs_api
from app.api.models import SummariseTablesOutput
from app.services.docx_crawler.run_docx_extraction import run_docx_content_extraction
from app.services.docx_crawler.translate.exceptions import CompoundNotFoundError


@medical_docs_api.get("/")
async def index() -> dict:
    return {
        "Home": "Upload docx formatted medical files to receive summary",
        "Upload endpoint": "hit /summary endpoint with a payload consisting of a docx file and two compounds within the study",
    }


@medical_docs_api.post("/summarise", response_model=SummariseTablesOutput)
def summarise(
    file: UploadFile = File(...),
    compound_1: str = Form(...),
    compound_2: str = Form(...),
):
    if file.filename is None:
        raise HTTPException(
            status_code=400, detail="A .docx file is required in the payload"
        )
    if not file.filename.lower().endswith(".docx"):
        raise HTTPException(
            status_code=415, detail="Uploaded file needs to be in .docx format"
        )

    try:
        docx_document = Document(file.file)
    except Exception as ex:
        raise HTTPException(status_code=415, detail=f"Passed file is not a readable .docx document: {ex}")

    try:
        summarised_content = run_docx_content_extraction(
            docx_document, compound_1, compound_2
        )
    except CompoundNotFoundError as comp_error:
        raise HTTPException(status_code=422, detail=str(comp_error))

    return summarised_content
