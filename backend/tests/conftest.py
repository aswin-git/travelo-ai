import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine, SessionLocal

@pytest.fixture(scope="session")
def db_engine():
    # We use the existing engine, but we could override DATABASE_URL in environment for tests.
    try:
        Base.metadata.create_all(bind=engine)
    except Exception:
        pass
    yield engine

@pytest.fixture(scope="session")
def db_session(db_engine):
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c
