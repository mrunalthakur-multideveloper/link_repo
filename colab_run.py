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
CRM_ENDPOINT_PATH=/api/clients/active
INTERNAL_SERVICE_API_KEY=applyus_secret_microservice_key_2026
CRM_API_KEY=applservice_key_2026

# SOURCE DATABASE CONFIGURATION (Where onboarding_submissions table lives)
SOURCE_SUPABASE_URL=https://rfjgmocoteevwfkkwgcb.supabase.co/
SOURCE_SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJmamdtb2NvdGVldndma2t3Z2NiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODc3MTg1ODcsImV4cCI6MjEwMzI5NDU4N30.0MuB-1TNL7U5evfksj12GnQ30PtVBTMZiCl_IoyYVTk
SOURCE_TABLE=onboarding_submissions

# TARGET DATABASE CONFIGURATION - NEON DB
DATABASE_URL=postgresql://neondb_owner:npg_ND7pS0dReFCJ@ep-damp-waterfall-b5noll06-pooler.c-7.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require
NEON_TABLE=links
TARGET_TABLE=links
PROGRESS_TABLE=scraper_progress_repo1

# Fallback: Supabase REST API (used only if DATABASE_URL is empty)
SUPABASE_URL=https://gcccpggboacfalhjmunf.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdjY2NwZ2dib2FjZmFsaGptdW5mIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODg4NDkzMDIsImV4cCI6MjEwNDQyNTMwMn0.vBF4iApvvGHe61NB0k4-70SLWW_FK5Ot3AI1PJbBp9w

LOCATION=United States
MAX_WORKERS=15
# MAX_JOBS_PER_KEYWORD=100
KEYWORD_DELAY=30
CONTINUOUS_MODE=false

PROXIES=http://ltrabmxv-rotate:ayq2lqvdcey2@p.webshare.io:80
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
