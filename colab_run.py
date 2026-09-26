#!/usr/bin/env python3
"""One-click runner for Google Colab and remote environments."""
import os
import sys

# Ensure project root is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Auto-configure .env if not present
ENV_TEMPLATE = """# =============================================================================
# AUTO-GENERATED CONFIGURATION FOR COLAB / CLOUD RUN
# =============================================================================
CRM_BACKEND_URL=https://api.applyus.org
INTERNAL_SERVICE_API_KEY=applservice_key_2026
CRM_API_KEY=applservice_key_2026

DATABASE_URL=postgresql://neondb_owner:npg_ND7pS0dReFCJ@ep-damp-waterfall-b5noll06-pooler.c-7.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require
NEON_TABLE=links
TARGET_TABLE=links
PROGRESS_TABLE=scraper_progress_repo1

LOCATION=United States
MAX_WORKERS=15
MAX_JOBS_PER_KEYWORD=100
KEYWORD_DELAY=30
CONTINUOUS_MODE=true

PROXIES=http://ggmcopdi-rotate:tg8xvu345xss@p.webshare.io:80
"""

env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if not os.path.exists(env_path):
    with open(env_path, "w", encoding="utf-8") as f:
        f.write(ENV_TEMPLATE)
    print("✅ Created .env configuration file automatically.")

# Import and execute run.py main()
from dotenv import load_dotenv
load_dotenv(env_path, override=True)

import run

if __name__ == "__main__":
    run.main()
