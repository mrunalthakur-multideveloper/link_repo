# #!/usr/bin/env python3
# """LinkedIn scraper with resume support - Repository 1"""

# import sys
# import os
# import time
# import requests
# import urllib.parse
# from dotenv import load_dotenv

# load_dotenv()

# sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# from src.linkedin_scraper import LinkedInScraper


# SUPABASE_URL = os.getenv("SUPABASE_URL")
# SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# TABLE = "scraper_progress_repo1"

# HEADERS = {
#     "apikey": SUPABASE_KEY,
#     "Authorization": f"Bearer {SUPABASE_KEY}",
#     "Content-Type": "application/json"
# }


# # --------------------------------------------------
# # Extract external apply links
# # --------------------------------------------------

# def extract_external_link(link):

#     if not link:
#         return link

#     if "linkedin.com/jobs/redirect" in link:

#         parsed = urllib.parse.urlparse(link)
#         params = urllib.parse.parse_qs(parsed.query)

#         if "url" in params:
#             return urllib.parse.unquote(params["url"][0])

#     return link


# # --------------------------------------------------
# # Ensure progress row exists
# # --------------------------------------------------

# def ensure_row_exists():

#     url = f"{SUPABASE_URL}/rest/v1/{TABLE}?id=eq.1"

#     r = requests.get(url, headers=HEADERS)

#     if r.status_code == 200 and len(r.json()) == 0:

#         insert_url = f"{SUPABASE_URL}/rest/v1/{TABLE}"

#         data = {"id": 1, "last_index": 0}

#         headers = HEADERS.copy()
#         headers["Prefer"] = "return=minimal"

#         requests.post(insert_url, headers=headers, json=data)


# # --------------------------------------------------
# # Get progress
# # --------------------------------------------------

# def get_progress():

#     ensure_row_exists()

#     url = f"{SUPABASE_URL}/rest/v1/{TABLE}?id=eq.1"

#     r = requests.get(url, headers=HEADERS)

#     if r.status_code == 200 and r.json():
#         return r.json()[0]["last_index"]

#     return 0


# # --------------------------------------------------
# # Update progress
# # --------------------------------------------------

# def update_progress(index):

#     url = f"{SUPABASE_URL}/rest/v1/{TABLE}?id=eq.1"

#     headers = HEADERS.copy()
#     headers["Prefer"] = "return=minimal"

#     data = {"last_index": index}

#     r = requests.patch(url, headers=headers, json=data)

#     if r.status_code in [200,204]:
#         print(f"✅ Progress updated → {index}")
#     else:
#         print("⚠️ Failed to update progress:", r.text)


# # --------------------------------------------------
# # Main scraper
# # --------------------------------------------------

# def main():

#     print("=" * 70)
#     print("🚀 LINKEDIN SCRAPER WITH AUTO RESUME - REPO 1")
#     print("=" * 70)

#     all_keywords = [
#         "Actimize Developer","Active Directory","Agronomy Operations","AI/ML Engineer",
#         "Anti Money Laundering (AML)","Atlassian Engineer / Jira","Big Data Engineer",
#         "Bioinformatics","Bioinformatics for UK","Biotechnology","Biotechnology Internship",
#         "Business Analyst","Business Analyst for Canada","Business Intelligence Engineer",
#         "Business Intelligence Engineer Internships","Chemical Engineer","CLINICAL DATA ANALYST",
#         "Clinical Research Coordinator","Cloud Engineer","Cloud Engineer for Ireland",
#         "Computer Science","Computer Science Internship","Construction Management",
#         "Credit controller for UK","CRM Sales","CRM Specialist","Cyber security",
#         "Cybersecurity for Ireland","Cybersecurity for UK","Data Analyst",
#         "Data Analyst for Canada","Data Analyst for UK","Data Analyst Internship for Ireland",
#         "Data Analyst Internships","Database Administration","Data Center Technician",
#         "Data Engineer","Data Engineer (citizen/h4ead)","Data Engineer for UK",
#         "Data Science for Germany","Data Scientist","Design Verification Engineer",
#         "DevOps","DevOps for India","DevOps for Ireland","DevOps for UK","DevOps Internships",
#         "Dynamics 365","Electrical Engineer","Electrical Project",
#         "Electronic Health Records (EHR)","Embedded Software Engineer",
#         "Environmental Health and Safety (EHS)","Epic Analyst","ERP","Financial analyst",
#         "Financial analyst for Ireland","Frontend Engineering","Full Stack",
#         "Game Developer","Game UI / Interactive UI Designer","Generative AI"
#     ]

#     location = os.getenv("LOCATION","United States")
#     max_workers = int(os.getenv("MAX_WORKERS","5"))

#     scraper = LinkedInScraper(use_database=True)

#     start_index = get_progress()

#     print(f"\n▶ Resuming from keyword index: {start_index}")
#     print(f"📊 Total keywords: {len(all_keywords)}")

#     start_time = time.time()

#     total_jobs = 0

#     for i in range(start_index,len(all_keywords)):

#         keyword = all_keywords[i]

#         print("\n" + "-" * 60)
#         print(f"🔍 Scraping keyword {i+1}/{len(all_keywords)}: {keyword}")
#         print("-" * 60)

#         try:

#             jobs = scraper.scrape_all_jobs_batch(
#                 keywords=[keyword],
#                 location=location,
#                 max_workers=max_workers,
#                 save_to_db=False,
#             )

#             job_dicts = []
#             redirected = 0
#             for job in jobs:
#                 if job.apply_url:
#                     original = job.apply_url
#                     resolved = extract_external_link(original)
#                     if resolved != original:
#                         job.apply_url = resolved
#                         job.job_url_direct = resolved
#                         redirected += 1
#                 job_dicts.append(job.to_supabase_dict())
            
#             if redirected:
#                 print(f"🔗 Resolved {redirected} external redirect(s) for '{keyword}'")

#             # Save to DB after processing links
#             if job_dicts and scraper.db and scraper.db.initialized:
#                 scraper.db.save_jobs_batch(job_dicts)

#             total_jobs += len(jobs)

#             update_progress(i+1)

#         except Exception as e:
#             print(f"❌ Error scraping keyword {keyword}: {e}")

#     update_progress(0)

#     elapsed = time.time() - start_time

#     print("\n" + "=" * 70)
#     print("✅ SCRAPER RUN COMPLETE")
#     print("=" * 70)
#     print(f"Jobs scraped: {total_jobs}")
#     print(f"Total runtime: {elapsed/60:.1f} minutes")


# if __name__ == "__main__":
#     main()




















#!/usr/bin/env python3
"""LinkedIn scraper with resume support - Neon PostgreSQL Integration"""

import sys
import os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass

import time
import requests
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.linkedin_scraper import LinkedInScraper

# --------------------------------------------------
# Extract external apply links
# --------------------------------------------------

def extract_external_link(link):
    if not link:
        return link
    if "linkedin.com/jobs/redirect" in link:
        parsed = urllib.parse.urlparse(link)
        params = urllib.parse.parse_qs(parsed.query)
        if "url" in params:
            return urllib.parse.unquote(params["url"][0])
    return link


# --------------------------------------------------
# Main scraper
# --------------------------------------------------

def main():

    print("=" * 70)
    print("🚀 LINKEDIN SCRAPER - NEON DB VERSION")
    print("=" * 70)

    default_keywords = [
        "Actimize Developer","Active Directory","Agronomy Operations","AI/ML Engineer",
        "Anti Money Laundering (AML)","Atlassian Engineer / Jira","Big Data Engineer",
        "Bioinformatics","Bioinformatics for UK","Biotechnology","Biotechnology Internship",
        "Business Analyst","Business Analyst for Canada","Business Intelligence Engineer",
        "Business Intelligence Engineer Internships","Chemical Engineer","CLINICAL DATA ANALYST",
        "Clinical Research Coordinator","Cloud Engineer","Cloud Engineer for Ireland",
        "Computer Science","Computer Science Internship","Construction Management",
        "Credit controller for UK","CRM Sales","CRM Specialist","Cyber security",
        "Cybersecurity for Ireland","Cybersecurity for UK","Data Analyst",
        "Data Analyst for Canada","Data Analyst for UK","Data Analyst Internship for Ireland",
        "Data Analyst Internships","Database Administration","Data Center Technician",
        "Data Engineer","Data Engineer (citizen/h4ead)","Data Engineer for UK",
        "Data Science for Germany","Data Scientist","Design Verification Engineer",
        "DevOps","DevOps for India","DevOps for Ireland","DevOps for UK","DevOps Internships",
        "Dynamics 365","Electrical Engineer","Electrical Project",
        "Electronic Health Records (EHR)","Embedded Software Engineer",
        "Environmental Health and Safety (EHS)","Epic Analyst","ERP","Financial analyst",
        "Financial analyst for Ireland","Frontend Engineering","Full Stack",
        "Game Developer","Game UI / Interactive UI Designer","Generative AI"
    ]

    location = os.getenv("LOCATION", "United States")
    max_workers = int(os.getenv("MAX_WORKERS", "3"))
    proxies = os.getenv("PROXIES")
    max_jobs_env = os.getenv("MAX_JOBS")
    max_jobs = int(max_jobs_env) if max_jobs_env and max_jobs_env.strip().isdigit() and int(max_jobs_env) > 0 else None
    max_jobs_per_kw_env = os.getenv("MAX_JOBS_PER_KEYWORD", "100")
    max_jobs_per_kw = int(max_jobs_per_kw_env) if max_jobs_per_kw_env.strip().isdigit() and int(max_jobs_per_kw_env) > 0 else 100

    # Initialize scraper and database
    scraper = LinkedInScraper(proxies=proxies, use_database=True)
    
    if not scraper.db or not scraper.db.initialized:
        print("⚠️ Database not initialized. Check your Neon DB settings in .env")

    custom_keyword = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else None
    if custom_keyword:
        all_keywords = [custom_keyword]
        start_index = 0
    else:
        # Dynamically fetch desired job titles as search keywords from active clients endpoint (synced to Neon DB)
        domain_filter = os.getenv("DOMAIN_FILTER") or os.getenv("CRM_DOMAIN_FILTER")
        client_keywords = scraper.db.get_client_search_keywords(domain_filter=domain_filter) if scraper.db else []
        if client_keywords:
            all_keywords = client_keywords
            print(f"📋 Loaded {len(all_keywords)} desired job title(s) as search keyword(s) from active clients ({len(getattr(scraper.db, 'active_clients', []))} client(s))")
        else:
            # Fallback to source database get_primary_functions or default_keywords
            db_functions = scraper.db.get_primary_functions() if scraper.db and scraper.db.initialized else []
            if db_functions:
                all_keywords = db_functions
                print(f"📋 Loaded {len(all_keywords)} primary function(s) from source table")
            else:
                print("ℹ️ No active clients or primary functions found. Using default keyword list.")
                all_keywords = default_keywords

        # Progress retrieval from Supabase
        start_index = scraper.db.get_progress() if scraper.db else 0
        if start_index >= len(all_keywords):
            print(f"🔄 Checkpoint index ({start_index}) is >= total keywords ({len(all_keywords)}). Resetting start index to 0.")
            start_index = 0
            if scraper.db:
                scraper.db.update_progress(0)

    backend = getattr(scraper.db, "backend_type", "connected") if scraper.db else "disabled"

    print(f"\n▶ Starting at keyword index: {start_index}")
    print(f"📊 Keywords to process: {len(all_keywords)} -> {all_keywords}")
    print(f"🎯 Keyword limit: up to {max_jobs_per_kw} jobs/keyword (posted in last 24h)")
    print(f"💾 Real-time storage: ENABLED (Saving to Neon DB [{backend}])")
    if max_jobs:
        print(f"🧪 Test Mode: ACTIVE (Global limit: {max_jobs} jobs)")
    if proxies:
        proxy_display = proxies.split('@')[-1] if '@' in proxies else 'Enabled'
        print(f"🛡️ Proxy rotation: ENABLED ({proxy_display})")
    else:
        print("🌐 Proxy rotation: DISABLED (Direct connection)")

    start_time = time.time()
    total_jobs = 0

    try:
        for i in range(start_index, len(all_keywords)):
            keyword = all_keywords[i]

            print("\n" + "-" * 60)
            print(f"🔍 Scraping keyword {i+1}/{len(all_keywords)}: {keyword}")
            print("-" * 60)

            if max_jobs and total_jobs >= max_jobs:
                print(f"\n🎯 Test limit of {max_jobs} jobs reached across run. Stopping.")
                break

            remaining_jobs = (max_jobs - total_jobs) if max_jobs else None

            try:
                # The scraper now saves jobs in real-time internally if save_to_db=True
                jobs = scraper.scrape_all_jobs_batch(
                    keywords=[keyword],
                    location=location,
                    max_workers=max_workers,
                    save_to_db=True,
                    max_jobs=remaining_jobs,
                    max_jobs_per_keyword=max_jobs_per_kw,
                )
                
                # Optional: Post-process external links if needed
                redirected = 0
                for job in jobs:
                    if job.apply_url and "linkedin.com/jobs/redirect" in job.apply_url:
                        original = job.apply_url
                        resolved = extract_external_link(original)
                        if resolved != original:
                            job.apply_url = resolved
                            job.job_url_direct = resolved
                            redirected += 1
                
                if redirected:
                    print(f"🔗 Resolved {redirected} external redirect(s) for '{keyword}'")
                
                total_jobs += len(jobs)
                
                # Update progress in Neon DB (only for default multi-keyword runs)
                if not custom_keyword and scraper.db:
                    scraper.db.update_progress(i + 1)

                if max_jobs and total_jobs >= max_jobs:
                    print(f"\n🎯 Test limit of {max_jobs} jobs reached. Completing test run.")
                    break

            except Exception as e:
                print(f"❌ Error scraping keyword {keyword}: {e}")
                # Don't update progress here to allow retry
                raise

        # Reset progress to 0 after full multi-keyword run
        if not custom_keyword and scraper.db:
            scraper.db.update_progress(0)

    except KeyboardInterrupt:
        print("\n🛑 Scraper stopped by user. Progress saved.")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
    finally:
        elapsed = time.time() - start_time
        print("\n" + "=" * 70)
        print("✅ SCRAPER RUN SUMMARY")
        print("=" * 70)
        print(f"Jobs scraped: {total_jobs}")
        print(f"Total runtime: {elapsed/60:.1f} minutes")


if __name__ == "__main__":
    main()


