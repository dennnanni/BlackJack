import pytest
from src.model.database_actions import add_user


def test_add_user():
    assert add_user('test_user', 'test_password', 'test_salt', 0) == 'User added successfully'
    