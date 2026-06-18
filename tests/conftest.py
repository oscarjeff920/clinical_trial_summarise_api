# tests/conftest.py
from pathlib import Path
import pytest

@pytest.fixture
def client1_docx_path():
    return Path(__file__).parent / "resources" / "client1.docx"

@pytest.fixture
def client1_docx_bytes(client1_docx_path):
    return client1_docx_path.read_bytes()