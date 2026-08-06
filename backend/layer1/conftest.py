from __future__ import annotations
import os

# Must be set before any app module is imported.
os.environ.setdefault("DATABASE_URL", "postgresql://user:password@localhost/prism_test_db")
