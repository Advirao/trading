# core/__init__.py — marks this directory as the shared library package.
# Import the most-used symbols here so callers can write:
#   from core import trading_client, data_client
from core.config import trading_client, data_client, API_KEY, SECRET_KEY
