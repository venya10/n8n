import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    # Using TestClient as a context manager runs the app's lifespan (startup
    # loads the semantic search model), same as a real server boot.
    with TestClient(app) as c:
        yield c
