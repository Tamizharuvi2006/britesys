"""
Calder County — Caseworker's Morning Agent
Configuration.

All settings with sensible defaults, overridable via environment variables.
"""
import os

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SRC_DIR)

# History API
HISTORY_API_BASE = os.environ.get("HISTORY_API_BASE", "http://127.0.0.1:8083")
HISTORY_API_TIMEOUT = int(os.environ.get("HISTORY_API_TIMEOUT", "10"))
HISTORY_API_RETRIES = int(os.environ.get("HISTORY_API_RETRIES", "1"))

# Input files
REFERRAL_QUEUE_PATH = os.environ.get(
    "REFERRAL_QUEUE_PATH",
    os.path.join(REPO_ROOT, "data", "referral-queue.json"),
)
POLICY_RULES_PATH = os.environ.get(
    "POLICY_RULES_PATH",
    os.path.join(SRC_DIR, "policy_rules.json"),
)

# Output
OUTPUT_DIR = os.environ.get(
    "OUTPUT_DIR",
    os.path.join(REPO_ROOT, "output"),
)
