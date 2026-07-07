import os

# Config modules require these at import time; harmless defaults for tests.
os.environ.setdefault('SHARED_SECRET', 'test-secret')
