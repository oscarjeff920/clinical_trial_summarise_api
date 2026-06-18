from fastapi.testclient import TestClient

from app.api.endpoints import medical_docs_api

client = TestClient(medical_docs_api)

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


# ---------------------------------------------------------------------------
# happy path
# ---------------------------------------------------------------------------

def test_summarise_happy_path_returns_200_and_expected_shape(client1_docx_bytes):
    resp = client.post(
        "/summarise",
        files={"file": ("client1.docx", client1_docx_bytes, DOCX_MIME)},
        data={"compound_1": "Placebo", "compound_2": "Compound X"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert list(body.keys()) == ["tables"]
    table = body["tables"][0]
    assert table["table_number"] == "2.1.1"
    assert table["selected_compounds"] == ["Placebo", "Compound X"]
    assert "totals_sentence" in table["summary_sentences"]
    assert len(table["summary_sentences"]["per_term_sentences"]) == 4


def test_summarise_compound_matching_is_case_insensitive(client1_docx_bytes):
    resp = client.post(
        "/summarise",
        files={"file": ("client1.docx", client1_docx_bytes, DOCX_MIME)},
        data={"compound_1": "placebo", "compound_2": "compound x"},  # wrong case on purpose
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# error paths
# ---------------------------------------------------------------------------

def test_summarise_wrong_file_extension_returns_415():
    resp = client.post(
        "/summarise",
        files={"file": ("notes.txt", b"hello", "text/plain")},
        data={"compound_1": "Placebo", "compound_2": "Compound X"},
    )
    assert resp.status_code == 415
    assert ".docx" in resp.json()["detail"]


def test_summarise_unreadable_docx_returns_415():
    # correct extension, but the bytes aren't a real docx zip
    resp = client.post(
        "/summarise",
        files={"file": ("broken.docx", b"not a real docx", DOCX_MIME)},
        data={"compound_1": "Placebo", "compound_2": "Compound X"},
    )
    assert resp.status_code == 415
    assert "readable" in resp.json()["detail"].lower()


def test_summarise_compound_not_in_table_returns_422(client1_docx_bytes):
    resp = client.post(
        "/summarise",
        files={"file": ("client1.docx", client1_docx_bytes, DOCX_MIME)},
        data={"compound_1": "Placebo", "compound_2": "Nonexistent Compound"},
    )
    assert resp.status_code == 422
    assert "not found" in resp.json()["detail"].lower()


def test_summarise_missing_file_returns_422_validation_error():
    # no file part at all -> FastAPI's own required-field validation
    resp = client.post(
        "/summarise",
        data={"compound_1": "Placebo", "compound_2": "Compound X"},
    )
    assert resp.status_code == 422


def test_summarise_missing_compound_field_returns_422_validation_error(client1_docx_bytes):
    resp = client.post(
        "/summarise",
        files={"file": ("client1.docx", client1_docx_bytes, DOCX_MIME)},
        data={"compound_1": "Placebo"},  # compound_2 missing
    )
    assert resp.status_code == 422