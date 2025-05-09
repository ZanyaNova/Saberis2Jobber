"""
Configuration for Jobber API and OAuth.
Loads sensitive information from environment variables.
"""
import os
from dotenv import load_dotenv

load_dotenv()

JOBBER_CLIENT_ID = os.environ.get("JOBBER_CLIENT_ID")
JOBBER_CLIENT_SECRET = os.environ.get("JOBBER_CLIENT_SECRET")

JOBBER_REDIRECT_URI = os.environ.get("JOBBER_REDIRECT_URI")
JOBBER_SCOPES = os.environ.get("JOBBER_SCOPES", "clients.read,quotes.write")

JOBBER_AUTHORIZATION_URL = "https://api.getjobber.com/api/oauth/authorize"
JOBBER_TOKEN_URL = "https://api.getjobber.com/api/oauth/token"
JOBBER_GRAPHQL_URL = "https://api.getjobber.com/api/graphql"

if not all([JOBBER_CLIENT_ID, JOBBER_CLIENT_SECRET, JOBBER_REDIRECT_URI, JOBBER_SCOPES]):
    raise ValueError(
        "Missing critical Jobber OAuth configuration. "
        "Please set JOBBER_CLIENT_ID, JOBBER_CLIENT_SECRET, JOBBER_REDIRECT_URI, and JOBBER_SCOPES "
        "in your environment or .env file."
    )

TOKEN_FILE_PATH = "jobber_tokens.json"