#!/usr/bin/env python3
"""LinkedIn scraper with resume support - Repository 1"""

import sys
import os
import time
import requests
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.linkedin_scraper import LinkedInScraper


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

TABLE = "scraper_progress_repo1"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}


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
# Ensure progress row exists
# --------------------------------------------------

def ensure_row_exists():

    url = f"{SUPABASE_URL}/rest/v1/{TABLE}?id=eq.1"

    r = requests.get(url, headers=HEADERS)

    if r.status_code == 200 and len(r.json()) == 0:

        insert_url = f"{SUPABASE_URL}/rest/v1/{TABLE}"

        data = {"id": 1, "last_index": 0}

        headers = HEADERS.copy()
        headers["Prefer"] = "return=minimal"

        requests.post(insert_url, headers=headers, json=data)


# --------------------------------------------------
# Get progress
# --------------------------------------------------

def get_progress():

    ensure_row_exists()

    url = f"{SUPABASE_URL}/rest/v1/{TABLE}?id=eq.1"

    r = requests.get(url, headers=HEADERS)

    if r.status_code == 200 and r.json():
        return r.json()[0]["last_index"]

    return 0


# --------------------------------------------------
# Update progress
# --------------------------------------------------

def update_progress(index):

    url = f"{SUPABASE_URL}/rest/v1/{TABLE}?id=eq.1"

    headers = HEADERS.copy()
    headers["Prefer"] = "return=minimal"

    data = {"last_index": index}

    r = requests.patch(url, headers=headers, json=data)

    if r.status_code in [200,204]:
        print(f"✅ Progress updated → {index}")
    else:
        print("⚠️ Failed to update progress:", r.text)


# --------------------------------------------------
# Main scraper
# --------------------------------------------------

def main():

    print("=" * 70)
    print("🚀 LINKEDIN SCRAPER WITH AUTO RESUME - REPO 1")
    print("=" * 70)

    all_keywords = [
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

    location = os.getenv("LOCATION","United States")
    max_workers = int(os.getenv("MAX_WORKERS","5"))

    scraper = LinkedInScraper(use_database=True)

    start_index = get_progress()

    print(f"\n▶ Resuming from keyword index: {start_index}")
    print(f"📊 Total keywords: {len(all_keywords)}")

    start_time = time.time()

    total_jobs = 0

    for i in range(start_index,len(all_keywords)):

        keyword = all_keywords[i]

        print("\n" + "-" * 60)
        print(f"🔍 Scraping keyword {i+1}/{len(all_keywords)}: {keyword}")
        print("-" * 60)

        try:

            jobs = scraper.scrape_all_jobs_batch(
                keywords=[keyword],
                location=location,
                max_workers=max_workers,
                save_to_db=False,
            )

            job_dicts = []
            redirected = 0
            for job in jobs:
                if job.apply_url:
                    original = job.apply_url
                    resolved = extract_external_link(original)
                    if resolved != original:
                        job.apply_url = resolved
                        job.job_url_direct = resolved
                        redirected += 1
                job_dicts.append(job.to_supabase_dict())
            
            if redirected:
                print(f"🔗 Resolved {redirected} external redirect(s) for '{keyword}'")

            # Save to DB after processing links
            if job_dicts and scraper.db and scraper.db.initialized:
                scraper.db.save_jobs_batch(job_dicts)

            total_jobs += len(jobs)

            update_progress(i+1)

        except Exception as e:
            print(f"❌ Error scraping keyword {keyword}: {e}")

    update_progress(0)

    elapsed = time.time() - start_time

    print("\n" + "=" * 70)
    print("✅ SCRAPER RUN COMPLETE")
    print("=" * 70)
    print(f"Jobs scraped: {total_jobs}")
    print(f"Total runtime: {elapsed/60:.1f} minutes")


if __name__ == "__main__":
    main()













































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
# # Patch extracted URLs back into the database
# # --------------------------------------------------

# def patch_job_url_in_db(job_id, new_url):
#     """Update a single job's URL in the jobs table after external link extraction."""

#     # Adjust the table name below to match your actual jobs table
#     jobs_table = os.getenv("JOBS_TABLE", "jobs")

#     url = f"{SUPABASE_URL}/rest/v1/{jobs_table}?id=eq.{job_id}"

#     headers = HEADERS.copy()
#     headers["Prefer"] = "return=minimal"

#     data = {"url": new_url}

#     r = requests.patch(url, headers=headers, json=data)

#     if r.status_code not in [200, 204]:
#         print(f"⚠️  Failed to patch URL for job {job_id}: {r.text}")


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

#     if r.status_code in [200, 204]:
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

#     location = os.getenv("LOCATION", "United States")
#     max_workers = int(os.getenv("MAX_WORKERS", "5"))

#     scraper = LinkedInScraper(use_database=True)

#     start_index = get_progress()

#     print(f"\n▶ Resuming from keyword index: {start_index}")
#     print(f"📊 Total keywords: {len(all_keywords)}")

#     start_time = time.time()

#     total_jobs = 0

#     for i in range(start_index, len(all_keywords)):

#         keyword = all_keywords[i]

#         print("\n" + "-" * 60)
#         print(f"🔍 Scraping keyword {i+1}/{len(all_keywords)}: {keyword}")
#         print("-" * 60)

#         try:
#             # ── Step 1: Scrape without saving to DB yet ──────────────────
#             jobs = scraper.scrape_all_jobs_batch(
#                 keywords=[keyword],
#                 location=location,
#                 max_workers=max_workers,
#                 save_to_db=False,           # <-- hold off on DB save
#             )

#             # ── Step 2: Extract external links BEFORE any DB write ───────
#             redirected = 0
#             for job in jobs:
#                 if "url" in job:
#                     original = job["url"]
#                     resolved = extract_external_link(original)
#                     if resolved != original:
#                         job["url"] = resolved
#                         redirected += 1

#             if redirected:
#                 print(f"🔗 Resolved {redirected} external redirect(s) for '{keyword}'")

#             # ── Step 3: Now save the corrected jobs to DB ────────────────
#             if jobs:
#                 scraper.save_jobs_to_db(jobs)   # single bulk save with clean URLs

#             total_jobs += len(jobs)

#             update_progress(i + 1)

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
