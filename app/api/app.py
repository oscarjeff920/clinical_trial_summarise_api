from fastapi import FastAPI

medical_docs_api = FastAPI(
    title="Medical Docs Api",
    description="An Api that accepts docx files in the payload and returns a summary of the data",
)
