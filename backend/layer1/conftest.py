import os

# Must be set before any app module is imported.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
