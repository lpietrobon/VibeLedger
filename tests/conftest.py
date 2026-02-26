import os

# Ensure required security settings exist before app import/startup in tests.
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=")
os.environ.setdefault("CONNECT_SIGNING_KEY", "test-connect-signing-key-32chars-min")
