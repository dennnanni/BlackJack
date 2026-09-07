import os
import tempfile

os.environ.setdefault('SHARED_SECRET', 'test-secret')

os.environ.setdefault('OUTBOX_PATH',
                      os.path.join(tempfile.gettempdir(), 'blackjack-test-outbox.db'))
