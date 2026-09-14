import os

os.environ['SHARED_SECRET'] = 'test-secret'
os.environ['DATABASE_URL'] = 'sqlite://'

import pytest
from central_server import db


@pytest.fixture
def session_db():
    db.Base.metadata.create_all(bind=db.engine)
    yield db
    db.Base.metadata.drop_all(bind=db.engine)
