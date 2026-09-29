#!/usr/bin/env python3
"""LinkedIn Scraper - Round 2: Keyword-Driven & Domain-Deduplicated Pipeline.

Pipeline Logic:
1. Fetches active clients from CRM API (/api/clients/active-domains) with complete keywords list.
2. Deduplication Rule: If two or more clients share the same domain and country, they are
   consolidated into a single target. The domain is searched and scraped ONCE.
3. Search: Sends the domain / job roles + keywords to search recent LinkedIn jobs (last 24 hours).
4. Description Verification (5-Keyword Match Rule):
   - For every candidate job, extracts the full job description.
   - Checks the description against the target's keyword list.
   - If >= 5 keywords are matched -> ACCEPTED & SAVED to Neon DB 'links' table & CSV buffer.
   - If < 5 keywords are matched -> DISQUALIFIED & SKIPPED.
5. Checkpoint & Auto-Resume: Persists progress in 'scraper_progress_round2' table.
"""

import sys
import os
import re
import time
import csv
import threading
from typing import List, Dict, Any, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass

# Ensure project root is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Ensure progress table for Round 2 is isolated from Round 1
os.environ["PROGRESS_TABLE"] = os.getenv("ROUND2_PROGRESS_TABLE", "scraper_progress_round2")
os.environ["CRM_ENDPOINT_PATH"] = "/api/clients/active-domains"

load_dotenv(override=True)

from src.linkedin_scraper import LinkedInScraper
from src.models import JobPost


# -----------------------------------------------------------------------------
# Keyword Matcher Helper
# -----------------------------------------------------------------------------

def count_matching_keywords(text: str, keywords: List[str]) -> Tuple[int, List[str]]:
    """
    Check how many keywords from the list appear in the given text (e.g. job description).
    Uses boundary-aware, case-insensitive regex matching.
    Returns (match_count, list_of_matched_keywords).
    """
    if not text or not keywords:
        return 0, []

    text_lower = text.lower()
    matched = []

    for kw in keywords:
        kw_clean = str(kw).strip()
        if not kw_clean:
            continue
        kw_lower = kw_clean.lower()

        # Handle special programming characters safely: C++, C#, .NET, Node.js, Next.js
        escaped = re.escape(kw_lower)
        pattern = r'(?<!\w)' + escaped + r'(?!\w)'

        if re.search(pattern, text_lower):
            matched.append(kw_clean)

    return len(matched), matched


# -----------------------------------------------------------------------------
# Real-Time CSV Buffer Helper
# -----------------------------------------------------------------------------

def append_round2_job_to_csv(filename: str, job: JobPost, domain: str,
                             match_count: int, matched_keywords: List[str],
                             lock: threading.Lock):
    """Safely append a qualified Round 2 job to the CSV buffer file in real-time."""
    file_exists = os.path.isfile(filename)
    with lock:
        with open(filename, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists or os.path.getsize(filename) == 0:
                writer.writerow([
                    "Job ID", "Title", "Company", "Company Logo", "Company URL",
                    "Location", "Location City", "Location State", "Location Country",
                    "Date Posted", "Job URL", "External Apply URL", "Is Remote",
                    "Is Easy Apply", "Job Type", "Job Level", "Industry",
                    "Domain", "Matched Keyword Count", "Matched Keywords",
                    "Salary Min", "Salary Max", "Salary Text", "Experience Required",
                    "Skills / Requirements", "Sponsorship H1B", "Source", "Emails",
                    "Description Preview",
                ])

            loc_disp = job.location.display_location() if job.location else ""
            city = job.location.city if job.location else ""
            state = job.location.state if job.location else ""
            country = job.location.country if job.location else ""
            job_types = ", ".join(jt.value for jt in job.job_type) if job.job_type else ""

            writer.writerow([
                job.job_id,
                job.title,
                job.company_name,
                job.company_logo or "",
                getattr(job, "company_url", "") or "",
                loc_disp,
                city,
                state,
                country,
                str(job.date_posted) if job.date_posted else "",
                job.job_url or "",
                job.apply_url or "",
                job.is_remote,
                job.is_easy_apply,
                job_types,
                job.job_level or "",
                job.company_industry or "",
                domain,
                match_count,
                ", ".join(matched_keywords),
                job.compensation.min_amount if job.compensation else "",
                job.compensation.max_amount if job.compensation else "",
                getattr(job, "salary_text", "") or "",
                getattr(job, "experience", "") or "",
                getattr(job, "skills", "") or "",
                getattr(job, "sponsorship_h1b", "") or "",
                getattr(job, "source", "l_i") or "l_i",
                ", ".join(job.emails) if job.emails else "",
                (job.description or "")[:500] if job.description else "",
            ])


# -----------------------------------------------------------------------------
# Main Round 2 Orchestrator
# -----------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("🚀 LINKEDIN SCRAPER - ROUND 2 (KEYWORD-DRIVEN PIPELINE)")
    print("   Requirement: ≥ 5 Keywords Matched in Job Description to Save")
    print("   Deduplication: Unique (domain, country) scraped only once")
    print("=" * 70)

    # 1. Scraper Settings
    location_default = os.getenv("LOCATION", "United States")
    max_workers = int(os.getenv("MAX_WORKERS", "5"))
    proxies = os.getenv("PROXIES")
    keyword_delay = int(os.getenv("KEYWORD_DELAY", "15"))
    min_keyword_matches = int(os.getenv("MIN_KEYWORD_MATCHES", "5"))
    max_jobs_per_target_env = os.getenv("MAX_JOBS_PER_TARGET") or os.getenv("MAX_JOBS_PER_KEYWORD")
    max_jobs_per_target = int(max_jobs_per_target_env) if max_jobs_per_target_env and max_jobs_per_target_env.strip().isdigit() and int(max_jobs_per_target_env) > 0 else None

    # 2. Scraper & Database Initialization
    scraper = LinkedInScraper(proxies=proxies, use_database=True)
    if not scraper.db or not scraper.db.initialized:
        print("⚠️ Warning: Neon PostgreSQL not initialized. Check your credentials in .env")

    # 3. Load Round 2 Deduplicated Domain Targets
    domain_filter = os.getenv("DOMAIN_FILTER") or os.getenv("CRM_DOMAIN_FILTER")
    print("\n📡 Fetching active clients with keywords from ApplyUS CRM...")
    domain_targets = scraper.db.get_round2_search_targets(domain_filter=domain_filter) if scraper.db else []

    if not domain_targets:
        print("❌ No active clients found from CRM. Falling back to default keywords.")
        domain_targets = [{
            "domain": "Software Engineer",
            "country": location_default,
            "keywords": ["Python", "JavaScript", "React", "SQL", "Docker", "AWS", "Git", "REST APIs", "PostgreSQL", "CI/CD"],
            "desired_job_titles": ["Software Engineer", "Full Stack Developer", "Backend Developer"],
            "client_names": ["Default Fallback"]
        }]

    # 4. Checkpoint & Resume
    start_index = scraper.db.get_progress() if scraper.db else 0
    if start_index >= len(domain_targets):
        print(f"🔄 Checkpoint index ({start_index}) is >= total targets ({len(domain_targets)}). Resetting to 0.")
        start_index = 0
        if scraper.db:
            scraper.db.update_progress(0)

    # 5. Display Target Summary
    print(f"\n📋 Loaded {len(domain_targets)} unique (domain, country) search target(s):")
    for idx, dt in enumerate(domain_targets):
        marker = "▶" if idx == start_index else " "
        clients_str = ", ".join(dt.get("client_names", [])) or "Active Client"
        kw_preview = ", ".join(dt.get("keywords", [])[:5])
        total_kws = len(dt.get("keywords", []))
        print(f"  {marker} {idx+1}. Domain: '{dt['domain']}' | Country: '{dt['country']}'")
        print(f"     • Clients: {clients_str}")
        print(f"     • Keywords ({total_kws}): {kw_preview}...")

    print(f"\n⚡ Worker threads: {max_workers}")
    print(f"🎯 Threshold rule: Must match ≥ {min_keyword_matches} keywords in Job Description")
    if proxies:
        clean_p = proxies.split("@")[-1] if "@" in proxies else proxies
        print(f"🛡️ Proxy rotation: ENABLED ({clean_p})")
    print(f"💾 Storage target: Neon DB ('{scraper.db.table_name}' table) + Real-time CSV buffer")

    # Real-time CSV setup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"scraped_jobs_round2_{timestamp}.csv"
    csv_lock = threading.Lock()
    print(f"📄 Local CSV buffer: {csv_filename}")

    start_time = time.time()
    total_candidates_examined = 0
    total_qualified_saved = 0
    total_disqualified_skipped = 0

    try:
        for i in range(start_index, len(domain_targets)):
            target = domain_targets[i]
            domain = target["domain"]
            target_country = target.get("country") or location_default
            target_keywords = target.get("keywords", [])
            client_names = target.get("client_names", [])

            print("\n" + "=" * 70)
            print(f"🔍 [Target {i+1}/{len(domain_targets)}] Domain: '{domain}' | Country: '{target_country}'")
            print(f"   Clients: {', '.join(client_names)} | Keywords Pool: {len(target_keywords)} skills")
            print("=" * 70)

            # Determine search queries: search domain title and top role titles
            search_queries = [domain]
            for title in target.get("desired_job_titles", []):
                if title and title.lower() != domain.lower() and title not in search_queries:
                    search_queries.append(title)
                if len(search_queries) >= 3:
                    break

            # If top keywords exist, build keyword-augmented query
            if target_keywords:
                top_kw_combo = f"{domain} {' '.join(target_keywords[:3])}"
                search_queries.append(top_kw_combo)

            # 1. Search candidate jobs across queries
            candidate_jobs = []
            seen_job_ids = set()

            for sq in search_queries:
                print(f"   📍 Searching LinkedIn for: '{sq}' in '{target_country}' (last 24h)...")
                try:
                    raw_jobs = scraper.search_all_jobs(
                        keyword=sq,
                        location=target_country,
                        hours_old=24,
                        max_results=50 if max_jobs_per_target else 100
                    )
                    for j in raw_jobs:
                        jid = j.get("job_id")
                        if jid and jid not in seen_job_ids:
                            # Skip if job already exists in Neon DB
                            if scraper.db and scraper.db.job_exists(jid):
                                continue
                            seen_job_ids.add(jid)
                            j["search_keyword"] = domain
                            j["search_location"] = target_country
                            candidate_jobs.append(j)
                except Exception as e:
                    print(f"   ⚠️ Search error for query '{sq}': {e}")

            print(f"   📋 Found {len(candidate_jobs)} new candidate job(s) to inspect for '{domain}'")

            if not candidate_jobs:
                print(f"   ℹ️ No new un-scraped jobs found for target. Moving to next.")
                if scraper.db:
                    scraper.db.update_progress(i + 1)
                continue

            # 2. Multi-threaded detail extraction and 5-keyword verification
            print(f"   🔗 Fetching details and verifying ≥ {min_keyword_matches} keywords in description ({max_workers} workers)...")

            target_qualified_jobs: List[JobPost] = []
            target_inspected = 0

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_job = {
                    executor.submit(scraper.get_job_details, j["job_id"], j): j
                    for j in candidate_jobs
                }

                for future in as_completed(future_to_job):
                    src_job = future_to_job[future]
                    target_inspected += 1
                    total_candidates_examined += 1

                    try:
                        job_post: JobPost = future.result(timeout=20)
                        if not job_post or not job_post.description:
                            total_disqualified_skipped += 1
                            continue

                        # Core Round 2 Check: Scan description for >= 5 keywords
                        match_count, matched_kws = count_matching_keywords(job_post.description, target_keywords)

                        if match_count >= min_keyword_matches:
                            # QUALIFIED: Meets 5-keyword threshold
                            job_post.search_keyword = f"{domain} (Round 2)"
                            matched_str = ", ".join(matched_kws)
                            job_post.skills = f"Matched ({match_count}): {matched_str}"

                            # Append to real-time CSV
                            append_round2_job_to_csv(
                                filename=csv_filename,
                                job=job_post,
                                domain=domain,
                                match_count=match_count,
                                matched_keywords=matched_kws,
                                lock=csv_lock
                            )

                            target_qualified_jobs.append(job_post)
                            total_qualified_saved += 1

                            kw_snippet = ", ".join(matched_kws[:5])
                            if len(matched_kws) > 5:
                                kw_snippet += f" (+{len(matched_kws) - 5} more)"
                            print(f"   ✅ [MATCH {match_count} kws] Job {job_post.job_id} '{job_post.title}' at '{job_post.company_name}' -> SAVED ({kw_snippet})")

                            if max_jobs_per_target and len(target_qualified_jobs) >= max_jobs_per_target:
                                print(f"   🎯 Reached target limit ({len(target_qualified_jobs)}/{max_jobs_per_target} jobs) for '{domain}'!")
                                for f in future_to_job:
                                    f.cancel()
                                break
                        else:
                            # DISQUALIFIED: Fewer than 5 keywords
                            total_disqualified_skipped += 1
                            matched_info = f"({', '.join(matched_kws)})" if matched_kws else "(none)"
                            print(f"   ⏭️ [SKIP {match_count}/{min_keyword_matches} kws] Job {src_job['job_id']} '{src_job.get('title')}' -> {matched_info}")

                    except Exception as e:
                        print(f"   ✗ Error parsing job {src_job['job_id']}: {e}")
                        total_disqualified_skipped += 1

            # 3. Batch save all qualified jobs from this domain to Neon DB
            if target_qualified_jobs and scraper.db and scraper.db.initialized:
                print(f"\n💾 [DATABASE SYNC] Storing {len(target_qualified_jobs)} qualified jobs from '{domain}' to Neon DB '{scraper.db.table_name}' table...")
                job_dicts = [j.to_supabase_dict() for j in target_qualified_jobs]
                db_results = scraper.db.save_jobs_batch(job_dicts)
                print(f"   ✓ DB Insert: {db_results.get('success', 0)} new jobs inserted, {db_results.get('duplicate', 0)} duplicates skipped")

            # 4. Update checkpoint
            if scraper.db:
                scraper.db.update_progress(i + 1)

            if i < len(domain_targets) - 1:
                print(f"\n⏱️ Domain target '{domain}' ({target_country}) complete. Waiting {keyword_delay}s before next domain...")
                time.sleep(keyword_delay)

        # Reset checkpoint after completing all domain targets
        if scraper.db:
            scraper.db.update_progress(0)

    except KeyboardInterrupt:
        print("\n🛑 Scraper Round 2 stopped by user. Progress checkpoint saved.")
    except Exception as e:
        print(f"\n❌ Fatal error in Round 2: {e}")
    finally:
        elapsed = time.time() - start_time
        print("\n" + "=" * 70)
        print("✅ SCRAPER ROUND 2 RUN SUMMARY")
        print("=" * 70)
        print(f"Total candidate jobs inspected : {total_candidates_examined}")
        print(f"Passed ≥ 5 keywords rule (Saved): {total_qualified_saved}")
        print(f"Skipped (< 5 keywords matched) : {total_disqualified_skipped}")
        print(f"Local CSV file saved to         : {csv_filename}")
        print(f"Total execution runtime         : {elapsed / 60:.1f} minutes")
        print("=" * 70)


if __name__ == "__main__":
    main()
