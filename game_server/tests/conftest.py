import os

# Config modules require these at import time. Assigned, not setdefault: the
# tests sign their own JWTs with this value, so a real SHARED_SECRET inherited
# from the environment (compose passes `.env` to the containers) would leave
# them signing with one key and verifying with another. The suite owns this key.
os.environ['SHARED_SECRET'] = 'test-secret'
