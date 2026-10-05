import os

os.environ['SHARED_SECRET'] = 'test-secret'
os.environ['SECRET_KEY'] = 'test-session-key'
os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['ADMIN_USERNAME'] = 'admin'
os.environ['ADMIN_PASSWORD'] = 'admin'

import pytest
from central_server import db


@pytest.fixture
def session_db():
    db.Base.metadata.create_all(bind=db.engine)
    yield db
    db.Base.metadata.drop_all(bind=db.engine)
