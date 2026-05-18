import os
import sys
from pathlib import Path

# Ensure `backend/be` is on sys.path so `pages.draft`, `ppa_api.ppa_client`, etc.
# resolve when tests are run from the project root or from the backend folder.
_BACKEND_BE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_BE))

# Set safe dummy env vars BEFORE any module that touches them gets imported.
# orm/session.py builds a SQLAlchemy engine at import time using DB_*; security.py
# reads JWT_SECRET at import time. Engines are created lazily-connected (no actual
# network call until a query runs), so dummy values are fine for unit tests that
# never execute SQL.
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "3306")
os.environ.setdefault("DB_NAME", "test")
os.environ.setdefault("JWT_SECRET", "test-secret-for-unit-tests-only")
os.environ.setdefault("EXTERNAL_API_BASE_URL", "https://api.test.local")
os.environ.setdefault("EXTERNAL_API_KEY", "test-api-key")
os.environ.setdefault("EXTERNAL_API_TIMEOUT_SECONDS", "5")
