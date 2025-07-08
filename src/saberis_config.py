"""
Configuration for the Saberis API.
Loads the API key from environment variables.
"""
import os
from typing import Final
from dotenv import load_dotenv

load_dotenv()

try:
    # Renamed to match the API's parameter
    SABERIS_AUTH_TOKEN: Final[str] = os.environ["SABERIS_AUTH_TOKEN"]
except KeyError as e:
    raise EnvironmentError(
        f"Missing required environment variable: {e}. "
        "Please set SABERIS_AUTH_TOKEN in your .env file."
    ) from e

# Updated to the correct API endpoint
SABERIS_BASE_URL: Final[str] = "https://connect.saberis.com:9000"
SABERIS_TOKEN_FILE_PATH: str = "saberis_token.json"