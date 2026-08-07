import os

# Must be set before any central_server module is imported: config reads the
# environment at import time. The sqlite in-memory DB keeps tests self-contained.
# Assigned, not setdefault: the tests sign their own JWTs with this value, so a
# real SHARED_SECRET inherited from the environment (compose passes `.env` to
# the containers) would leave them signing with one key and verifying with
# another. The suite owns this key.
os.environ['SHARED_SECRET'] = 'test-secret'
os.environ['DATABASE_URL'] = 'sqlite://'

import pytest

from central_server import db


@pytest.fixture
def session_db():
    db.Base.metadata.create_all(bind=db.engine)
    yield db
    db.Base.metadata.drop_all(bind=db.engine)
