from pydantic import BaseModel


class TermSentence(BaseModel):
    term: str
    per_term_sentence: str


class SummarySentences(BaseModel):
    totals_sentence: str
    per_term_sentences: list[TermSentence]


class TableSummary(BaseModel):
    table_number: str | None
    table_title: str
    selected_compounds: list[str]
    summary_sentences: SummarySentences


class SummariseTablesOutput(BaseModel):
    tables: list[TableSummary]
