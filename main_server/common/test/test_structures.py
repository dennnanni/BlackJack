from common.structures import UserDatabase


def test_user_is_valid():
    """
    Test the is_valid method of the User class.
    """
    user = UserDatabase(username='test_user', password='test_password', salt='test_salt', balance=0.0)
    assert user.is_valid() is True
    
    user_invalid = UserDatabase(username='', password='test_password', salt='test_salt', balance=0.0)
    assert user_invalid.is_valid() is False
    