"""
Configuration for Jobber API and OAuth.
Loads sensitive information from environment variables.
Ensures required variables are strings.
"""
import os
from dotenv import load_dotenv
from typing import Final # Use Final for variables that are constants

load_dotenv()

try:
    JOBBER_CLIENT_ID: str = os.environ["JOBBER_CLIENT_ID"]
    JOBBER_CLIENT_SECRET: str = os.environ["JOBBER_CLIENT_SECRET"]
    JOBBER_REDIRECT_URI: str = os.environ["JOBBER_REDIRECT_URI"]

except KeyError as e:
    raise EnvironmentError(
        f"Missing required environment variable: {e}. "
        "Please set it in your environment or .env file."
    ) from e

JOBBER_SCOPES: str = os.getenv("JOBBER_SCOPES", "clients.read,clients.write,quotes.write")

if not JOBBER_SCOPES:
     raise ValueError(
        "JOBBER_SCOPES environment variable is set but is empty. "
        "Please provide a valid scope string."
     )

JOBBER_AUTHORIZATION_URL: Final[str] = "https://api.getjobber.com/api/oauth/authorize"
JOBBER_TOKEN_URL: Final[str] = "https://api.getjobber.com/api/oauth/token"
JOBBER_GRAPHQL_URL: Final[str] = "https://api.getjobber.com/api/graphql"

# --- Define Other Configuration ---
TOKEN_FILE_PATH: str = "jobber_tokens.json"
