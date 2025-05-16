from common.structures import Message, UserDatabase

def test_message_success():
    """
    Test the success method of the Message class.
    """
    message = Message.success('Test success message')
    assert message.message == 'Test success message'
    assert message.success is True
    
def test_message_failure():
    """
    Test the failure method of the Message class.
    """
    message = Message.failure('Test failure message')
    assert message.message == 'Test failure message'
    assert message.success is False
    
def test_message_to_dict():
    """
    Test the to_dict method of the Message class.
    """
    message = Message.success('Test success message')
    message_dict = message.to_dict()
    assert message_dict['message'] == 'Test success message'
    assert message_dict['success'] is True
    
def test_user_is_valid():
    """
    Test the is_valid method of the User class.
    """
    user = UserDatabase(username='test_user', password='test_password', salt='test_salt', balance=0.0)
    assert user.is_valid() is True
    
    user_invalid = UserDatabase(username='', password='test_password', salt='test_salt', balance=0.0)
    assert user_invalid.is_valid() is False