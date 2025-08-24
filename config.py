import os
from dotenv import load_dotenv

load_dotenv()

# --- Application Constants ---
APP_NAME = "dynamic_splunk_agent_app"

# --- Model Configuration ---
# Central place to define the LLM to be used by all agents
CLAUDE_SONNET_BEDROCK = "bedrock/anthropic.claude-3-sonnet-20240229-v1:0"
MODEL_NAME = CLAUDE_SONNET_BEDROCK

# --- Security Configuration ---
API_KEY = os.getenv("API_KEY")

# --- Database Configuration ---
DATABASE_URL = os.getenv("DATABASE_URL")