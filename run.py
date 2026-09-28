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
    max_workers = int(os.getenv("MAX_WORKERS", "15"))
    proxies = os.getenv("PROXIES")
    max_jobs_env = os.getenv("MAX_JOBS")
    max_jobs = int(max_jobs_env) if max_jobs_env and max_jobs_env.strip().isdigit() and int(max_jobs_env) > 0 else None
    max_jobs_per_kw_env = os.getenv("MAX_JOBS_PER_KEYWORD")
    max_jobs_per_kw = int(max_jobs_per_kw_env) if max_jobs_per_kw_env and max_jobs_per_kw_env.strip().isdigit() and int(max_jobs_per_kw_env) > 0 else None
    keyword_delay = int(os.getenv("KEYWORD_DELAY", "30"))

    # Initialize scraper and database
    scraper = LinkedInScraper(proxies=proxies, use_database=True)
    
    if not scraper.db or not scraper.db.initialized:
        print("⚠️ Database not initialized. Check your Neon DB settings in .env")

    custom_keyword = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else None
    custom_location = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("-") else os.getenv("LOCATION", "United States")

    if custom_keyword:
        search_targets = [{"keyword": custom_keyword, "country": custom_location}]
        start_index = 0
    else:
        # Dynamically fetch (keyword, country) search targets from active clients endpoint (synced to Neon DB)
        domain_filter = os.getenv("DOMAIN_FILTER") or os.getenv("CRM_DOMAIN_FILTER")
        client_targets = scraper.db.get_client_search_targets(domain_filter=domain_filter) if scraper.db else []
        if client_targets:
            search_targets = client_targets
            active_clients_count = len(getattr(scraper.db, 'active_clients', []))
            print(f"📋 Loaded {len(search_targets)} unique (keyword, country) search target(s) from {active_clients_count} active client(s)")
        else:
            # Fallback to source database get_primary_functions or default_keywords
            db_functions = scraper.db.get_primary_functions() if scraper.db and scraper.db.initialized else []
            default_loc = os.getenv("LOCATION", "United States")
            if db_functions:
                search_targets = [{"keyword": fn, "country": default_loc} for fn in db_functions]
                print(f"📋 Loaded {len(search_targets)} primary function(s) from source table (location: '{default_loc}')")
            else:
                print(f"ℹ️ No active clients or primary functions found. Using default keyword list (location: '{default_loc}').")
                search_targets = [{"keyword": kw, "country": default_loc} for kw in default_keywords]

        # Progress retrieval from Neon DB
        start_index = scraper.db.get_progress() if scraper.db else 0
        if start_index >= len(search_targets):
            print(f"🔄 Checkpoint index ({start_index}) is >= total targets ({len(search_targets)}). Resetting start index to 0.")
            start_index = 0
            if scraper.db:
                scraper.db.update_progress(0)

    backend = getattr(scraper.db, "backend_type", "connected") if scraper.db else "disabled"

    print(f"\n▶ Starting at search target index: {start_index}")
    print(f"📊 Targets to process: {len(search_targets)}")
    for idx, st in enumerate(search_targets[:10]):
        print(f"   {idx+1}. '{st['keyword']}' in '{st['country']}'")
    if len(search_targets) > 10:
        print(f"   ... and {len(search_targets) - 10} more target(s)")
    print(f"⚡ Parallel workers: {max_workers}")
    limit_display = f"up to {max_jobs_per_kw} jobs/target (posted in last 24h)" if max_jobs_per_kw else "UNLIMITED (all jobs posted in last 24h)"
    print(f"🎯 Target limit: {limit_display}")
    print(f"⏱️ Rotation pause: {keyword_delay} seconds between target rotations")
    print(f"💾 Real-time storage: ENABLED (Saving to Neon DB [{backend}])")
    if max_jobs:
        print(f"🧪 Test Mode: ACTIVE (Global limit: {max_jobs} jobs)")
    if proxies:
        proxy_display = proxies.split('@')[-1] if '@' in proxies else 'Enabled'
        print(f"🛡️ Proxy rotation: ENABLED ({proxy_display})")
    else:
        print("🌐 Proxy rotation: DISABLED (Direct connection)")

    continuous_mode = os.getenv("CONTINUOUS_MODE", "false").lower() in ("true", "1", "yes")
    if custom_keyword or max_jobs:
        continuous_mode = False

    start_time = time.time()
    total_jobs = 0
    rotation_cycle = 1

    try:
        while True:
            if rotation_cycle > 1:
                print("\n" + "=" * 70)
                print(f"🔄 STARTING SEARCH TARGET ROTATION CYCLE #{rotation_cycle}")
                print("=" * 70)
                domain_filter = os.getenv("DOMAIN_FILTER") or os.getenv("CRM_DOMAIN_FILTER")
                refreshed_targets = scraper.db.get_client_search_targets(domain_filter=domain_filter) if scraper.db else []
                if refreshed_targets:
                    search_targets = refreshed_targets
                    print(f"📋 Refreshed {len(search_targets)} unique (keyword, country) search target(s) from active clients")

            for i in range(start_index, len(search_targets)):
                target = search_targets[i]
                keyword = target["keyword"]
                target_country = target.get("country") or os.getenv("LOCATION", "United States")

                print("\n" + "-" * 60)
                print(f"🔍 [Cycle {rotation_cycle}] Scraping target {i+1}/{len(search_targets)}: '{keyword}' in '{target_country}'")
                print("-" * 60)

                if max_jobs and total_jobs >= max_jobs:
                    print(f"\n🎯 Test limit of {max_jobs} jobs reached across run. Stopping.")
                    break

                remaining_jobs = (max_jobs - total_jobs) if max_jobs else None

                try:
                    # Dynamically pass keyword and target country into scraper
                    jobs = scraper.scrape_all_jobs_batch(
                        keywords=[keyword],
                        location=target_country,
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
                        print(f"🔗 Resolved {redirected} external redirect(s) for '{keyword}' ({target_country})")
                    
                    total_jobs += len(jobs)
                    
                    # Update progress in Neon DB (only for default multi-target runs)
                    if not custom_keyword and scraper.db:
                        scraper.db.update_progress(i + 1)

                    if max_jobs and total_jobs >= max_jobs:
                        print(f"\n🎯 Test limit of {max_jobs} jobs reached. Completing test run.")
                        break

                    if i < len(search_targets) - 1:
                        print(f"\n⏱️ Target '{keyword}' ({target_country}) complete. Waiting {keyword_delay}s before next rotation...")
                        time.sleep(keyword_delay)

                except Exception as e:
                    print(f"❌ Error scraping target '{keyword}' in '{target_country}': {e}")
                    time.sleep(5)
                    continue

            # Reset progress to 0 after full multi-target run
            if not custom_keyword and scraper.db:
                scraper.db.update_progress(0)
            start_index = 0

            if not continuous_mode or (max_jobs and total_jobs >= max_jobs):
                break

            print(f"\n🔄 Full target rotation #{rotation_cycle} complete ({total_jobs} total jobs scraped so far)!")
            print(f"⏱️ Waiting {keyword_delay} seconds before starting next rotation cycle...")
            time.sleep(keyword_delay)
            rotation_cycle += 1

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


