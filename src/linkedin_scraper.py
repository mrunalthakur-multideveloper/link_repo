# """Main LinkedIn scraper class - optimized for external link extraction with Supabase"""

# import time
# import random
# import re
# from datetime import datetime, date
# from typing import Optional, List, Dict, Any, Tuple
# from urllib.parse import urlparse, unquote, parse_qs
# from concurrent.futures import ThreadPoolExecutor, as_completed
# import threading

# import requests
# from bs4 import BeautifulSoup
# from bs4.element import Tag

# from .models import JobPost, Location, Compensation, Country, JobType
# from .constant import headers
# from .util import (
#     job_type_code,
#     parse_job_type,
#     parse_job_level,
#     parse_company_industry,
#     is_job_remote,
#     extract_external_url_from_html,
#     extract_emails_from_text,
#     currency_parser,
#     parse_relative_date,
#     create_session,
#     remove_attributes,
# )
# from .database import SupabaseManager


# class LinkedInScraper:
#     """High-performance LinkedIn scraper focused on external links with Supabase storage"""
    
#     def __init__(self, proxies=None, ca_cert=None, user_agent=None, use_database=True):
#         self.base_url = "https://www.linkedin.com"
#         self.session = create_session(proxies=proxies, ca_cert=ca_cert)
#         self.session.headers.update(headers)
        
#         # Rate limiting
#         self.min_delay = 1.0
#         self.max_delay = 3.0
#         self.current_delay = self.min_delay
#         self.consecutive_errors = 0
#         self.max_consecutive_errors = 3
#         self.error_backoff = 1.5
        
#         # Thread safety
#         self._lock = threading.Lock()
#         self._extracted_links = set()
        
#         # Database
#         self.use_database = use_database
#         self.db = SupabaseManager() if use_database else None
#         if use_database:
#             self.db.initialize()
        
#     def _throttle(self):
#         """Apply throttling based on current delay"""
#         with self._lock:
#             time.sleep(self.current_delay + random.uniform(0, 0.5))
    
#     def _handle_error(self):
#         """Increase delay on errors"""
#         with self._lock:
#             self.consecutive_errors += 1
#             if self.consecutive_errors >= self.max_consecutive_errors:
#                 self.current_delay = min(self.current_delay * self.error_backoff, self.max_delay)
#                 self.consecutive_errors = 0
#                 print(f"⚠️ Increasing delay to {self.current_delay:.1f}s due to errors")
    
#     def _handle_success(self):
#         """Gradually decrease delay on success"""
#         with self._lock:
#             self.consecutive_errors = 0
#             if self.current_delay > self.min_delay:
#                 self.current_delay = max(self.current_delay / self.error_backoff, self.min_delay)
    
#     def search_jobs(self, keyword: str, location: str = "United States", 
#                    hours_old: int = 24, limit: int = 25) -> List[Dict]:
#         """
#         Search for jobs and return basic info
        
#         Returns list of dicts with keys: job_id, title, company, location, link
#         """
#         jobs = []
#         start = 0
        
#         while len(jobs) < limit:
#             # Build search URL
#             params = {
#                 "keywords": keyword,
#                 "location": location,
#                 "distance": "100",
#                 "f_TPR": f"r{hours_old * 3600}",
#                 "start": start,
#                 "refresh": True,
#             }
            
#             url = f"{self.base_url}/jobs-guest/jobs/api/seeMoreJobPostings/search"
            
#             try:
#                 self._throttle()
#                 response = self.session.get(url, params=params, timeout=10)
                
#                 if response.status_code == 429:
#                     print(f"⚠️ Rate limited, waiting...")
#                     time.sleep(5)
#                     continue
                    
#                 if response.status_code != 200:
#                     print(f"❌ Search failed: {response.status_code}")
#                     break
                
#                 # Parse HTML response
#                 soup = BeautifulSoup(response.text, "html.parser")
#                 job_cards = soup.find_all("div", class_="base-card")
                
#                 if not job_cards:
#                     print(f"No more jobs found")
#                     break
                
#                 # Extract basic info from each card
#                 for card in job_cards:
#                     try:
#                         # Get job ID from link
#                         link_tag = card.find("a", class_="base-card__full-link")
#                         if not link_tag or not link_tag.get("href"):
#                             continue
                            
#                         href = link_tag["href"]
#                         job_id = href.split("?")[0].split("-")[-1]
                        
#                         # Get title
#                         title_tag = card.find("h3", class_="base-search-card__title")
#                         title = title_tag.get_text(strip=True) if title_tag else "Unknown"
                        
#                         # Get company
#                         company_tag = card.find("h4", class_="base-search-card__subtitle")
#                         company = company_tag.get_text(strip=True) if company_tag else "Unknown"
                        
#                         # Get location
#                         location_tag = card.find("span", class_="job-search-card__location")
#                         location_str = location_tag.get_text(strip=True) if location_tag else ""
                        
#                         jobs.append({
#                             "job_id": job_id,
#                             "title": title,
#                             "company": company,
#                             "location": location_str,
#                             "link": f"{self.base_url}/jobs/view/{job_id}",
#                         })
                        
#                         if len(jobs) >= limit:
#                             break
                            
#                     except Exception as e:
#                         print(f"⚠️ Error parsing job card: {e}")
#                         continue
                
#                 start += 25
#                 self._handle_success()
                
#             except Exception as e:
#                 print(f"❌ Search error: {e}")
#                 self._handle_error()
#                 break
        
#         return jobs[:limit]
    
#     def get_job_details(self, job_id: str, job_data: Dict = None) -> Optional[JobPost]:
#         """
#         Fetch detailed job information including external apply link
        
#         This is the KEY function that extracts external URLs
#         """
#         url = f"{self.base_url}/jobs/view/{job_id}"
        
#         try:
#             self._throttle()
#             response = self.session.get(url, timeout=10)
            
#             if response.status_code == 429:
#                 print(f"⚠️ Rate limited for job {job_id}")
#                 return None
                
#             if response.status_code != 200:
#                 print(f"❌ Failed to fetch job {job_id}: {response.status_code}")
#                 return None
            
#             html = response.text
#             soup = BeautifulSoup(html, "html.parser")
            
#             # Extract external apply URL - THIS IS CRITICAL
#             external_url = self._extract_external_url(soup, html, job_id)
            
#             # Skip if it's a LinkedIn internal page (signup, etc.)
#             if external_url and self._is_linkedin_internal(external_url):
#                 external_url = None
            
#             # Extract job title
#             title = job_data.get("title") if job_data else ""
#             if not title:
#                 title_tag = soup.find("h1", class_="top-card-layout__title")
#                 title = title_tag.get_text(strip=True) if title_tag else "Unknown"
            
#             # Extract company
#             company = job_data.get("company") if job_data else ""
#             if not company:
#                 company_tag = soup.find("a", class_="topcard__org-name-link")
#                 company = company_tag.get_text(strip=True) if company_tag else "Unknown"
            
#             # Extract description
#             description = ""
#             desc_selectors = [
#                 "div.show-more-less-html__markup",
#                 "div.description__text",
#                 "div.jobs-description__content",
#             ]
#             for selector in desc_selectors:
#                 desc_tag = soup.select_one(selector)
#                 if desc_tag:
#                     description = desc_tag.get_text(strip=True)
#                     break
            
#             # Extract location
#             location_str = job_data.get("location") if job_data else ""
#             if not location_str:
#                 location_tag = soup.find("span", class_="topcard__flavor--bullet")
#                 if location_tag:
#                     location_str = location_tag.get_text(strip=True)
            
#             location = Location.from_string(location_str) if location_str else Location()
            
#             # Extract date posted
#             date_posted = None
#             time_tag = soup.find("span", class_="posted-time-ago__text")
#             if time_tag:
#                 date_posted = parse_relative_date(time_tag.get_text(strip=True))
            
#             # Extract job type, level, industry
#             job_type = parse_job_type(soup)
#             job_level = parse_job_level(soup)
#             company_industry = parse_company_industry(soup)
            
#             # Check if remote
#             is_remote = is_job_remote(title, description, location)
            
#             # Check if easy apply (no external URL)
#             is_easy_apply = not external_url
            
#             # Extract compensation if available
#             compensation = None
#             salary_tag = soup.find("span", class_="salary")
#             if salary_tag:
#                 salary_text = salary_tag.get_text(strip=True)
#                 if "-" in salary_text:
#                     parts = salary_text.split("-")
#                     min_amount = currency_parser(parts[0])
#                     max_amount = currency_parser(parts[1])
#                     compensation = Compensation(
#                         min_amount=min_amount,
#                         max_amount=max_amount,
#                         currency="USD"
#                     )
            
#             # Get search keyword from job_data if available
#             search_keyword = job_data.get("keyword") if job_data else None
            
#             # Create JobPost object
#             job = JobPost(
#                 job_id=job_id,
#                 title=title,
#                 company_name=company,
#                 location=location,
#                 description=description[:10000] if description else None,  # Limit description
#                 date_posted=date_posted,
#                 job_url=url,
#                 apply_url=external_url,  # This is the external link we want!
#                 job_url_direct=external_url,  # For backward compatibility
#                 job_type=job_type,
#                 job_level=job_level,
#                 company_industry=company_industry,
#                 is_remote=is_remote,
#                 is_easy_apply=is_easy_apply,
#                 compensation=compensation,
#                 emails=extract_emails_from_text(description or ""),
#                 search_keyword=search_keyword,
#             )
            
#             self._handle_success()
#             return job
            
#         except Exception as e:
#             print(f"❌ Error fetching job {job_id}: {e}")
#             self._handle_error()
#             return None
    
#     def _extract_external_url(self, soup: BeautifulSoup, html: str, job_id: str) -> Optional[str]:
#         """
#         Extract external apply URL using multiple methods
#         This is the core function that gets the actual external links
#         """
        
#         # METHOD 1: Look for code#applyUrl (MOST RELIABLE)
#         apply_code = soup.find("code", id="applyUrl")
#         if apply_code:
#             code_html = str(apply_code)
            
#             # Look for URL in HTML comments
#             comment_match = re.search(r'<!--\s*"([^"]+)"\s*-->', code_html)
#             if comment_match:
#                 url_candidate = comment_match.group(1)
                
#                 # Extract url parameter
#                 url_match = re.search(r'url=([^&\s]+)', url_candidate)
#                 if url_match:
#                     encoded = url_match.group(1)
#                     decoded = unquote(encoded)
                    
#                     # Filter out LinkedIn internal pages
#                     if not self._is_linkedin_internal(decoded):
#                         return decoded.split('&urlHash=')[0]
        
#         # METHOD 2: Look for externalApply pattern in HTML
#         pattern = rf'externalApply/{job_id}\?url=([^"&\s>]+)'
#         match = re.search(pattern, html, re.IGNORECASE)
#         if match:
#             encoded = match.group(1)
#             decoded = unquote(encoded)
#             if not self._is_linkedin_internal(decoded):
#                 return decoded.split('&urlHash=')[0]
        
#         # METHOD 3: Look for any external apply links
#         apply_selectors = [
#             'a[href*="apply"]',
#             'a[href*="lever"]',
#             'a[href*="greenhouse"]',
#             'a[href*="workable"]',
#             'a[href*="ashby"]',
#             'a[href*="bamboo"]',
#             'a[href*="icims"]',
#             'a.jobs-apply-button',
#         ]
        
#         for selector in apply_selectors:
#             links = soup.select(selector)
#             for link in links:
#                 href = link.get("href")
#                 if href and not self._is_linkedin_internal(href):
#                     return href
        
#         # METHOD 4: Try to fetch externalApply endpoint
#         try:
#             ext_url = f"{self.base_url}/jobs/view/externalApply/{job_id}"
#             ext_response = self.session.get(ext_url, timeout=5, allow_redirects=True)
            
#             final_url = ext_response.url
#             if final_url and not self._is_linkedin_internal(final_url):
#                 return final_url
                
#         except:
#             pass
        
#         return None
    
#     def _is_linkedin_internal(self, url: str) -> bool:
#         """Check if URL is a LinkedIn internal page (signup, login, etc.)"""
#         if not url:
#             return True
        
#         url_lower = url.lower()
        
#         # Check if it's a LinkedIn domain
#         if 'linkedin.com' in url_lower:
#             return True
        
#         # Check for signup/login patterns
#         internal_patterns = ['signup', 'login', 'auth', 'checkpoint', 'cold-join', 'registration']
#         for pattern in internal_patterns:
#             if pattern in url_lower:
#                 return True
        
#         return False
    
#     def scrape_batch(self, keywords: List[str], location: str = "United States", 
#                     jobs_per_keyword: int = 10, max_workers: int = 5, 
#                     save_to_db: bool = True) -> List[JobPost]:
#         """
#         Scrape jobs for multiple keywords in parallel and save to Supabase
        
#         This is the main method to call
#         """
#         all_jobs = []
#         all_job_dicts = []  # For database storage
        
#         # Phase 1: Search for jobs
#         all_search_results = []
#         for keyword in keywords:
#             print(f"\n🔍 Searching: {keyword}")
#             jobs = self.search_jobs(keyword, location, limit=jobs_per_keyword)
#             print(f"   Found {len(jobs)} jobs")
            
#             for job in jobs:
#                 job["keyword"] = keyword
#                 all_search_results.append(job)
            
#             # Small delay between keywords
#             time.sleep(2)
        
#         print(f"\n📊 Total jobs found: {len(all_search_results)}")
        
#         # Phase 2: Fetch details in parallel (this gets external links)
#         print(f"\n🔗 Fetching job details with external links...")
        
#         with ThreadPoolExecutor(max_workers=max_workers) as executor:
#             future_to_job = {
#                 executor.submit(self.get_job_details, job["job_id"], job): job
#                 for job in all_search_results
#             }
            
#             completed = 0
#             for future in as_completed(future_to_job):
#                 completed += 1
#                 job = future_to_job[future]
                
#                 try:
#                     job_post = future.result(timeout=15)
#                     if job_post:
#                         all_jobs.append(job_post)
                        
#                         # Convert to dict for database
#                         job_dict = job_post.to_supabase_dict()
#                         all_job_dicts.append(job_dict)
                        
#                         # Show progress with external link status
#                         if job_post.apply_url:
#                             print(f"  ✓ [{completed}/{len(all_search_results)}] {job['title'][:30]}... → EXTERNAL LINK FOUND")
#                         else:
#                             print(f"  ○ [{completed}/{len(all_search_results)}] {job['title'][:30]}... (internal apply)")
#                     else:
#                         print(f"  ✗ [{completed}/{len(all_search_results)}] Failed to fetch {job['title'][:30]}...")
                        
#                 except Exception as e:
#                     print(f"  ✗ [{completed}/{len(all_search_results)}] Error: {e}")
        
#         # Phase 3: Save to Supabase
#         if save_to_db and self.db and self.db.initialized and all_job_dicts:
#             db_results = self.db.save_jobs_batch(all_job_dicts)
#         elif save_to_db:
#             print("\n⚠️ Supabase not initialized, skipping database save")
        
#         # Summary
#         external_count = sum(1 for j in all_jobs if j.apply_url)
#         print(f"\n✅ Complete! Found {external_count} external links out of {len(all_jobs)} jobs")
        
#         return all_jobs
    
#     def save_to_csv(self, jobs: List[JobPost], filename: str = None):
#         """Save jobs to CSV file"""
#         if not filename:
#             filename = f"linkedin_jobs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
#         import csv
#         with open(filename, 'w', newline='', encoding='utf-8') as f:
#             writer = csv.writer(f)
#             writer.writerow([
#                 'Job ID', 'Title', 'Company', 'Location', 'Date Posted',
#                 'Job URL', 'External Apply URL', 'Is Remote', 'Is Easy Apply',
#                 'Job Type', 'Job Level', 'Industry', 'Search Keyword'
#             ])
            
#             for job in jobs:
#                 writer.writerow([
#                     job.job_id,
#                     job.title,
#                     job.company_name,
#                     job.location.display_location(),
#                     job.date_posted,
#                     job.job_url,
#                     job.apply_url or '',
#                     job.is_remote,
#                     job.is_easy_apply,
#                     ', '.join([jt.value for jt in job.job_type]) if job.job_type else '',
#                     job.job_level or '',
#                     job.company_industry or '',
#                     job.search_keyword or ''
#                 ])
        
#         print(f"💾 Saved {len(jobs)} jobs to {filename}")































# """Main LinkedIn scraper class - optimized for external link extraction with Supabase"""

# import time
# import random
# import re
# from datetime import datetime, date
# from typing import Optional, List, Dict, Any, Tuple
# from urllib.parse import urlparse, unquote, parse_qs
# from concurrent.futures import ThreadPoolExecutor, as_completed
# import threading

# import requests
# from bs4 import BeautifulSoup
# from bs4.element import Tag

# from .models import JobPost, Location, Compensation, Country, JobType
# from .constant import headers
# from .util import (
#     job_type_code,
#     parse_job_type,
#     parse_job_level,
#     parse_company_industry,
#     is_job_remote,
#     extract_external_url_from_html,
#     extract_emails_from_text,
#     currency_parser,
#     parse_relative_date,
#     create_session,
#     remove_attributes,
#     parse_salary_from_text,
#     parse_experience_from_text,
#     extract_company_logo,
# )
# from .database import SupabaseManager


# class LinkedInScraper:
#     """High-performance LinkedIn scraper focused on external links with Supabase storage"""
    
#     def __init__(self, proxies=None, ca_cert=None, user_agent=None, use_database=True):
#         self.base_url = "https://www.linkedin.com"
#         self.session = create_session(proxies=proxies, ca_cert=ca_cert)
#         self.session.headers.update(headers)
        
#         # Rate limiting
#         self.min_delay = 1.0
#         self.max_delay = 3.0
#         self.current_delay = self.min_delay
#         self.consecutive_errors = 0
#         self.max_consecutive_errors = 3
#         self.error_backoff = 1.5
        
#         # Thread safety
#         self._lock = threading.Lock()
#         self._extracted_links = set()
        
#         # Database
#         self.use_database = use_database
#         self.db = SupabaseManager() if use_database else None
#         if use_database:
#             self.db.initialize()
        
#     def _throttle(self):
#         """Apply throttling based on current delay"""
#         with self._lock:
#             time.sleep(self.current_delay + random.uniform(0, 0.5))
    
#     def _handle_error(self):
#         """Increase delay on errors"""
#         with self._lock:
#             self.consecutive_errors += 1
#             if self.consecutive_errors >= self.max_consecutive_errors:
#                 self.current_delay = min(self.current_delay * self.error_backoff, self.max_delay)
#                 self.consecutive_errors = 0
#                 print(f"⚠️ Increasing delay to {self.current_delay:.1f}s due to errors")
    
#     def _handle_success(self):
#         """Gradually decrease delay on success"""
#         with self._lock:
#             self.consecutive_errors = 0
#             if self.current_delay > self.min_delay:
#                 self.current_delay = max(self.current_delay / self.error_backoff, self.min_delay)
    
#     def search_jobs(self, keyword: str, location: str = "United States", 
#                    hours_old: int = 24, limit: int = 25) -> List[Dict]:
#         """
#         Search for jobs and return basic info
        
#         Returns list of dicts with keys: job_id, title, company, location, link
#         """
#         jobs = []
#         start = 0
        
#         while len(jobs) < limit:
#             # Build search URL
#             params = {
#                 "keywords": keyword,
#                 "location": location,
#                 "distance": "100",
#                 "f_TPR": f"r{hours_old * 3600}",
#                 "start": start,
#                 "refresh": True,
#             }
            
#             url = f"{self.base_url}/jobs-guest/jobs/api/seeMoreJobPostings/search"
            
#             try:
#                 self._throttle()
#                 response = self.session.get(url, params=params, timeout=10)
                
#                 if response.status_code == 429:
#                     print(f"⚠️ Rate limited, waiting...")
#                     time.sleep(5)
#                     continue
                    
#                 if response.status_code != 200:
#                     print(f"❌ Search failed: {response.status_code}")
#                     break
                
#                 # Parse HTML response
#                 soup = BeautifulSoup(response.text, "html.parser")
#                 job_cards = soup.find_all("div", class_="base-card")
                
#                 if not job_cards:
#                     print(f"No more jobs found")
#                     break
                
#                 # Extract basic info from each card
#                 for card in job_cards:
#                     try:
#                         # Get job ID from link
#                         link_tag = card.find("a", class_="base-card__full-link")
#                         if not link_tag or not link_tag.get("href"):
#                             continue
                            
#                         href = link_tag["href"]
#                         job_id = href.split("?")[0].split("-")[-1]
                        
#                         # Get title
#                         title_tag = card.find("h3", class_="base-search-card__title")
#                         title = title_tag.get_text(strip=True) if title_tag else "Unknown"
                        
#                         # Get company
#                         company_tag = card.find("h4", class_="base-search-card__subtitle")
#                         company = company_tag.get_text(strip=True) if company_tag else "Unknown"
                        
#                         # Get location
#                         location_tag = card.find("span", class_="job-search-card__location")
#                         location_str = location_tag.get_text(strip=True) if location_tag else ""
                        
#                         jobs.append({
#                             "job_id": job_id,
#                             "title": title,
#                             "company": company,
#                             "location": location_str,
#                             "link": f"{self.base_url}/jobs/view/{job_id}",
#                         })
                        
#                         if len(jobs) >= limit:
#                             break
                            
#                     except Exception as e:
#                         print(f"⚠️ Error parsing job card: {e}")
#                         continue
                
#                 start += 25
#                 self._handle_success()
                
#             except Exception as e:
#                 print(f"❌ Search error: {e}")
#                 self._handle_error()
#                 break
        
#         return jobs[:limit]
    
#     def get_job_details(self, job_id: str, job_data: Dict = None) -> Optional[JobPost]:
#         """
#         Fetch detailed job information including external apply link
        
#         This is the KEY function that extracts external URLs
#         """
#         url = f"{self.base_url}/jobs/view/{job_id}"
        
#         try:
#             self._throttle()
#             response = self.session.get(url, timeout=10)
            
#             if response.status_code == 429:
#                 print(f"⚠️ Rate limited for job {job_id}")
#                 return None
                
#             if response.status_code != 200:
#                 print(f"❌ Failed to fetch job {job_id}: {response.status_code}")
#                 return None
            
#             html = response.text
#             soup = BeautifulSoup(html, "html.parser")
            
#             # Extract external apply URL - THIS IS CRITICAL
#             external_url = self._extract_external_url(soup, html, job_id)
            
#             # Skip if it's a LinkedIn internal page (signup, etc.)
#             if external_url and self._is_linkedin_internal(external_url):
#                 external_url = None
            
#             # Extract job title
#             title = job_data.get("title") if job_data else ""
#             if not title:
#                 title_tag = soup.find("h1", class_="top-card-layout__title")
#                 title = title_tag.get_text(strip=True) if title_tag else "Unknown"
            
#             # Extract company
#             company = job_data.get("company") if job_data else ""
#             if not company:
#                 company_tag = soup.find("a", class_="topcard__org-name-link")
#                 company = company_tag.get_text(strip=True) if company_tag else "Unknown"
            
#             # Extract company logo
#             company_logo = extract_company_logo(soup)
            
#             # Extract description
#             description = ""
#             desc_selectors = [
#                 "div.show-more-less-html__markup",
#                 "div.description__text",
#                 "div.jobs-description__content",
#             ]
#             for selector in desc_selectors:
#                 desc_tag = soup.select_one(selector)
#                 if desc_tag:
#                     description = desc_tag.get_text(strip=True)
#                     break
            
#             # Extract location
#             location_str = job_data.get("location") if job_data else ""
#             if not location_str:
#                 location_tag = soup.find("span", class_="topcard__flavor--bullet")
#                 if location_tag:
#                     location_str = location_tag.get_text(strip=True)
            
#             location = Location.from_string(location_str) if location_str else Location()
            
#             # Extract date posted
#             date_posted = None
#             time_tag = soup.find("span", class_="posted-time-ago__text")
#             if time_tag:
#                 date_posted = parse_relative_date(time_tag.get_text(strip=True))
            
#             # Extract job type, level, industry
#             job_type = parse_job_type(soup)
#             job_level = parse_job_level(soup)
#             company_industry = parse_company_industry(soup)
            
#             # Extract salary information
#             salary_min, salary_max, salary_text = parse_salary_from_text(description, html)
            
#             # Extract experience requirements
#             experience = parse_experience_from_text(description, html)
            
#             # Check if remote
#             is_remote = is_job_remote(title, description, location)
            
#             # Check if easy apply (no external URL)
#             is_easy_apply = not external_url
            
#             # Create compensation object if salary found
#             compensation = None
#             if salary_min or salary_max:
#                 compensation = Compensation(
#                     min_amount=salary_min,
#                     max_amount=salary_max,
#                     currency="USD",
#                     interval="yearly"
#                 )
            
#             # Get search keyword from job_data if available
#             search_keyword = job_data.get("keyword") if job_data else None
            
#             # Create JobPost object
#             job = JobPost(
#                 job_id=job_id,
#                 title=title,
#                 company_name=company,
#                 company_logo=company_logo,
#                 location=location,
#                 description=description[:10000] if description else None,
#                 date_posted=date_posted,
#                 job_url=url,
#                 apply_url=external_url,
#                 job_url_direct=external_url,
#                 job_type=job_type,
#                 job_level=job_level,
#                 company_industry=company_industry,
#                 is_remote=is_remote,
#                 is_easy_apply=is_easy_apply,
#                 compensation=compensation,
#                 emails=extract_emails_from_text(description or ""),
#                 search_keyword=search_keyword,
#                 experience=experience,
#                 salary_text=salary_text,
#             )
            
#             self._handle_success()
#             return job
            
#         except Exception as e:
#             print(f"❌ Error fetching job {job_id}: {e}")
#             self._handle_error()
#             return None
    
#     def _extract_external_url(self, soup: BeautifulSoup, html: str, job_id: str) -> Optional[str]:
#         """
#         Extract external apply URL using multiple methods
#         This is the core function that gets the actual external links
#         """
        
#         # METHOD 1: Look for code#applyUrl (MOST RELIABLE)
#         apply_code = soup.find("code", id="applyUrl")
#         if apply_code:
#             code_html = str(apply_code)
            
#             # Look for URL in HTML comments
#             comment_match = re.search(r'<!--\s*"([^"]+)"\s*-->', code_html)
#             if comment_match:
#                 url_candidate = comment_match.group(1)
                
#                 # Extract url parameter
#                 url_match = re.search(r'url=([^&\s]+)', url_candidate)
#                 if url_match:
#                     encoded = url_match.group(1)
#                     decoded = unquote(encoded)
                    
#                     # Filter out LinkedIn internal pages
#                     if not self._is_linkedin_internal(decoded):
#                         return decoded.split('&urlHash=')[0]
        
#         # METHOD 2: Look for externalApply pattern in HTML
#         pattern = rf'externalApply/{job_id}\?url=([^"&\s>]+)'
#         match = re.search(pattern, html, re.IGNORECASE)
#         if match:
#             encoded = match.group(1)
#             decoded = unquote(encoded)
#             if not self._is_linkedin_internal(decoded):
#                 return decoded.split('&urlHash=')[0]
        
#         # METHOD 3: Look for any external apply links
#         apply_selectors = [
#             'a[href*="apply"]',
#             'a[href*="lever"]',
#             'a[href*="greenhouse"]',
#             'a[href*="workable"]',
#             'a[href*="ashby"]',
#             'a[href*="bamboo"]',
#             'a[href*="icims"]',
#             'a.jobs-apply-button',
#         ]
        
#         for selector in apply_selectors:
#             links = soup.select(selector)
#             for link in links:
#                 href = link.get("href")
#                 if href and not self._is_linkedin_internal(href):
#                     return href
        
#         # METHOD 4: Try to fetch externalApply endpoint
#         try:
#             ext_url = f"{self.base_url}/jobs/view/externalApply/{job_id}"
#             ext_response = self.session.get(ext_url, timeout=5, allow_redirects=True)
            
#             final_url = ext_response.url
#             if final_url and not self._is_linkedin_internal(final_url):
#                 return final_url
                
#         except:
#             pass
        
#         return None
    
#     def _is_linkedin_internal(self, url: str) -> bool:
#         """Check if URL is a LinkedIn internal page (signup, login, etc.)"""
#         if not url:
#             return True
        
#         url_lower = url.lower()
        
#         # Check if it's a LinkedIn domain
#         if 'linkedin.com' in url_lower:
#             return True
        
#         # Check for signup/login patterns
#         internal_patterns = ['signup', 'login', 'auth', 'checkpoint', 'cold-join', 'registration']
#         for pattern in internal_patterns:
#             if pattern in url_lower:
#                 return True
        
#         return False
    
#     def scrape_batch(self, keywords: List[str], location: str = "United States", 
#                     jobs_per_keyword: int = 10, max_workers: int = 5, 
#                     save_to_db: bool = True) -> List[JobPost]:
#         """
#         Scrape jobs for multiple keywords in parallel and save to Supabase
        
#         This is the main method to call
#         """
#         all_jobs = []
#         all_job_dicts = []  # For database storage
        
#         # Phase 1: Search for jobs
#         all_search_results = []
#         for keyword in keywords:
#             print(f"\n🔍 Searching: {keyword}")
#             jobs = self.search_jobs(keyword, location, limit=jobs_per_keyword)
#             print(f"   Found {len(jobs)} jobs")
            
#             for job in jobs:
#                 job["keyword"] = keyword
#                 all_search_results.append(job)
            
#             # Small delay between keywords
#             time.sleep(2)
        
#         print(f"\n📊 Total jobs found: {len(all_search_results)}")
        
#         # Phase 2: Fetch details in parallel (this gets external links)
#         print(f"\n🔗 Fetching job details with external links...")
        
#         with ThreadPoolExecutor(max_workers=max_workers) as executor:
#             future_to_job = {
#                 executor.submit(self.get_job_details, job["job_id"], job): job
#                 for job in all_search_results
#             }
            
#             completed = 0
#             for future in as_completed(future_to_job):
#                 completed += 1
#                 job = future_to_job[future]
                
#                 try:
#                     job_post = future.result(timeout=15)
#                     if job_post:
#                         all_jobs.append(job_post)
                        
#                         # Convert to dict for database
#                         job_dict = job_post.to_supabase_dict()
#                         all_job_dicts.append(job_dict)
                        
#                         # Show progress with external link status
#                         if job_post.apply_url:
#                             salary_info = f" ${job_post.compensation.min_amount}-{job_post.compensation.max_amount}" if job_post.compensation and job_post.compensation.min_amount else ""
#                             exp_info = f" Exp:{job_post.experience}" if job_post.experience else ""
#                             print(f"  ✓ [{completed}/{len(all_search_results)}] {job['title'][:30]}... → EXTERNAL LINK{salary_info}{exp_info}")
#                         else:
#                             print(f"  ○ [{completed}/{len(all_search_results)}] {job['title'][:30]}... (internal apply)")
#                     else:
#                         print(f"  ✗ [{completed}/{len(all_search_results)}] Failed to fetch {job['title'][:30]}...")
                        
#                 except Exception as e:
#                     print(f"  ✗ [{completed}/{len(all_search_results)}] Error: {e}")
        
#         # Phase 3: Save to Supabase
#         if save_to_db and self.db and self.db.initialized and all_job_dicts:
#             db_results = self.db.save_jobs_batch(all_job_dicts)
#         elif save_to_db:
#             print("\n⚠️ Supabase not initialized, skipping database save")
        
#         # Summary
#         external_count = sum(1 for j in all_jobs if j.apply_url)
#         salary_count = sum(1 for j in all_jobs if j.compensation and j.compensation.min_amount)
#         exp_count = sum(1 for j in all_jobs if j.experience)
#         logo_count = sum(1 for j in all_jobs if j.company_logo)
        
#         print(f"\n✅ Complete! Found:")
#         print(f"   📊 Total jobs: {len(all_jobs)}")
#         print(f"   🔗 External links: {external_count}")
#         print(f"   💰 Jobs with salary: {salary_count}")
#         print(f"   📝 Jobs with experience: {exp_count}")
#         print(f"   🖼️  Jobs with logo: {logo_count}")
        
#         return all_jobs
    
#     def save_to_csv(self, jobs: List[JobPost], filename: str = None):
#         """Save jobs to CSV file with enhanced fields"""
#         if not filename:
#             filename = f"linkedin_jobs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
#         import csv
#         with open(filename, 'w', newline='', encoding='utf-8') as f:
#             writer = csv.writer(f)
#             writer.writerow([
#                 'Job ID', 'Title', 'Company', 'Company Logo', 'Location', 'Date Posted',
#                 'Job URL', 'External Apply URL', 'Is Remote', 'Is Easy Apply',
#                 'Job Type', 'Job Level', 'Industry', 'Search Keyword',
#                 'Salary Min', 'Salary Max', 'Salary Text', 'Experience Required',
#                 'Description Preview'
#             ])
            
#             for job in jobs:
#                 writer.writerow([
#                     job.job_id,
#                     job.title,
#                     job.company_name,
#                     job.company_logo or '',
#                     job.location.display_location(),
#                     job.date_posted,
#                     job.job_url,
#                     job.apply_url or '',
#                     job.is_remote,
#                     job.is_easy_apply,
#                     ', '.join([jt.value for jt in job.job_type]) if job.job_type else '',
#                     job.job_level or '',
#                     job.company_industry or '',
#                     job.search_keyword or '',
#                     job.compensation.min_amount if job.compensation else '',
#                     job.compensation.max_amount if job.compensation else '',
#                     getattr(job, 'salary_text', ''),
#                     getattr(job, 'experience', ''),
#                     job.description[:200] + '...' if job.description and len(job.description) > 200 else (job.description or '')
#                 ])






























































































# """Main LinkedIn scraper class - optimized for external link extraction with Supabase"""

# import time
# import random
# import re
# from datetime import datetime, date
# from typing import Optional, List, Dict, Any, Tuple
# from urllib.parse import urlparse, unquote, parse_qs
# from concurrent.futures import ThreadPoolExecutor, as_completed
# import threading
# import json

# import requests
# from bs4 import BeautifulSoup
# from bs4.element import Tag

# from .models import JobPost, Location, Compensation, Country, JobType
# from .constant import headers
# from .util import (
#     job_type_code,
#     parse_job_type,
#     parse_job_level,
#     parse_company_industry,
#     is_job_remote,
#     extract_external_url_from_html,
#     extract_emails_from_text,
#     currency_parser,
#     parse_relative_date,
#     create_session,
#     remove_attributes,
#     parse_salary_from_text,
#     parse_experience_from_text,
#     extract_company_logo,
# )
# from .database import SupabaseManager


# class LinkedInScraper:
#     """High-performance LinkedIn scraper focused on external links with Supabase storage"""

#     def __init__(self, proxies=None, ca_cert=None, user_agent=None, use_database=True):
#         self.base_url = "https://www.linkedin.com"
#         self.session = create_session(proxies=proxies, ca_cert=ca_cert)
#         self.session.headers.update(headers)

#         # Rate limiting
#         self.min_delay = 1.0
#         self.max_delay = 3.0
#         self.current_delay = self.min_delay
#         self.consecutive_errors = 0
#         self.max_consecutive_errors = 3
#         self.error_backoff = 1.5

#         # Thread safety
#         self._lock = threading.Lock()
#         self._extracted_links = set()

#         # Database
#         self.use_database = use_database
#         self.db = SupabaseManager() if use_database else None
#         if use_database:
#             self.db.initialize()

#     def _throttle(self):
#         """Apply throttling based on current delay"""
#         with self._lock:
#             time.sleep(self.current_delay + random.uniform(0, 0.5))

#     def _handle_error(self):
#         """Increase delay on errors"""
#         with self._lock:
#             self.consecutive_errors += 1
#             if self.consecutive_errors >= self.max_consecutive_errors:
#                 self.current_delay = min(self.current_delay * self.error_backoff, self.max_delay)
#                 self.consecutive_errors = 0
#                 print(f"⚠️ Increasing delay to {self.current_delay:.1f}s due to errors")

#     def _handle_success(self):
#         """Gradually decrease delay on success"""
#         with self._lock:
#             self.consecutive_errors = 0
#             if self.current_delay > self.min_delay:
#                 self.current_delay = max(self.current_delay / self.error_backoff, self.min_delay)

#     def search_all_jobs(self, keyword: str, location: str = "United States", hours_old: int = 24) -> List[Dict]:
#         """
#         Search for ALL jobs posted in the last N hours for a keyword.
#         Continues pagination until LinkedIn returns an empty page.

#         LinkedIn returns up to 25 jobs per page. We keep fetching pages
#         (start=0, 25, 50, ...) until we get an empty response, which signals
#         that we've exhausted all results for this keyword/time window.
#         """
#         jobs = []
#         seen_job_ids = set()  # Dedup guard
#         start = 0
#         page = 1
#         max_pages = 200        # Safety cap: 200 pages × 25 = up to 5,000 jobs per keyword
#         empty_page_retries = 2  # Retry an empty page before giving up (handles transient gaps)
#         consecutive_empty = 0

#         print(f"\n   📍 Searching all pages for: {keyword}")

#         while page <= max_pages:
#             params = {
#                 "keywords": keyword,
#                 "location": location,
#                 "distance": "100",
#                 "f_TPR": f"r{hours_old * 3600}",  # e.g. r86400 = last 24 hours
#                 "start": start,
#                 "refresh": True,
#             }

#             url = f"{self.base_url}/jobs-guest/jobs/api/seeMoreJobPostings/search"

#             try:
#                 self._throttle()
#                 response = self.session.get(url, params=params, timeout=15)

#                 if response.status_code == 429:
#                     wait = random.uniform(10, 20)
#                     print(f"   ⚠️ Rate limited (429). Waiting {wait:.0f}s before retry...")
#                     time.sleep(wait)
#                     # Don't advance the page — retry the same offset
#                     continue

#                 if response.status_code != 200:
#                     print(f"   ❌ Search failed: HTTP {response.status_code}")
#                     self._handle_error()
#                     break

#                 soup = BeautifulSoup(response.text, "html.parser")
#                 job_cards = soup.find_all("div", class_="base-card")

#                 # ---- Empty page handling ----------------------------------------
#                 if not job_cards:
#                     consecutive_empty += 1
#                     if consecutive_empty <= empty_page_retries:
#                         print(f"   ⚠️ Empty page at start={start} (attempt {consecutive_empty}/{empty_page_retries}), retrying...")
#                         time.sleep(random.uniform(3, 6))
#                         continue
#                     else:
#                         print(f"   ✅ Confirmed end of results after {len(jobs)} jobs (empty response at start={start})")
#                         break
#                 # ---- Non-empty page: reset the empty counter --------------------
#                 consecutive_empty = 0

#                 page_jobs = 0
#                 for card in job_cards:
#                     try:
#                         link_tag = card.find("a", class_="base-card__full-link")
#                         if not link_tag or not link_tag.get("href"):
#                             continue

#                         href = link_tag["href"]
#                         job_id = href.split("?")[0].split("-")[-1]

#                         # Skip duplicates (can happen across pages near boundaries)
#                         if job_id in seen_job_ids:
#                             continue
#                         seen_job_ids.add(job_id)

#                         title_tag = card.find("h3", class_="base-search-card__title")
#                         title = title_tag.get_text(strip=True) if title_tag else "Unknown"

#                         company_tag = card.find("h4", class_="base-search-card__subtitle")
#                         company = company_tag.get_text(strip=True) if company_tag else "Unknown"

#                         location_tag = card.find("span", class_="job-search-card__location")
#                         location_str = location_tag.get_text(strip=True) if location_tag else ""

#                         jobs.append({
#                             "job_id": job_id,
#                             "title": title,
#                             "company": company,
#                             "location": location_str,
#                             "link": f"{self.base_url}/jobs/view/{job_id}",
#                         })

#                         page_jobs += 1

#                     except Exception as e:
#                         print(f"   ⚠️ Error parsing job card: {e}")
#                         continue

#                 print(f"   📄 Page {page} (start={start}): {page_jobs} new jobs | Running total: {len(jobs)}")

#                 # Advance to next page unconditionally — stop only when page is empty
#                 start += 25
#                 page += 1
#                 self._handle_success()

#                 # Brief pause between pages to be polite
#                 time.sleep(random.uniform(1.0, 2.5))

#             except Exception as e:
#                 print(f"   ❌ Search error on page {page}: {e}")
#                 self._handle_error()
#                 # Give it one more shot after a backoff, then bail
#                 time.sleep(5)
#                 break

#         if page > max_pages:
#             print(f"   ⚠️ Reached safety limit of {max_pages} pages for '{keyword}'")

#         print(f"   📊 Total unique jobs found for '{keyword}': {len(jobs)}")
#         return jobs

#     def get_job_details(self, job_id: str, job_data: Dict = None) -> Optional[JobPost]:
#         """
#         Fetch detailed job information including external apply link.
#         This is the KEY function that extracts external URLs.
#         """
#         url = f"{self.base_url}/jobs/view/{job_id}"

#         try:
#             self._throttle()
#             response = self.session.get(url, timeout=10)

#             if response.status_code == 429:
#                 print(f"⚠️ Rate limited for job {job_id}")
#                 return None

#             if response.status_code != 200:
#                 print(f"❌ Failed to fetch job {job_id}: {response.status_code}")
#                 return None

#             html = response.text
#             soup = BeautifulSoup(html, "html.parser")

#             # ===== ULTIMATE EXTERNAL LINK EXTRACTION =====
#             external_url = self._extract_external_url_ultimate(soup, html, job_id)
#             # =============================================

#             # Skip if it's a LinkedIn internal page
#             if external_url and self._is_linkedin_internal(external_url):
#                 external_url = None

#             # Extract job title
#             title = job_data.get("title") if job_data else ""
#             if not title:
#                 title_tag = soup.find("h1", class_="top-card-layout__title")
#                 title = title_tag.get_text(strip=True) if title_tag else "Unknown"

#             # Extract company
#             company = job_data.get("company") if job_data else ""
#             if not company:
#                 company_tag = soup.find("a", class_="topcard__org-name-link")
#                 company = company_tag.get_text(strip=True) if company_tag else "Unknown"

#             # Extract company logo
#             company_logo = extract_company_logo(soup)

#             # Extract description
#             description = ""
#             desc_selectors = [
#                 "div.show-more-less-html__markup",
#                 "div.description__text",
#                 "div.jobs-description__content",
#             ]
#             for selector in desc_selectors:
#                 desc_tag = soup.select_one(selector)
#                 if desc_tag:
#                     description = desc_tag.get_text(strip=True)
#                     break

#             # Extract location
#             location_str = job_data.get("location") if job_data else ""
#             if not location_str:
#                 location_tag = soup.find("span", class_="topcard__flavor--bullet")
#                 if location_tag:
#                     location_str = location_tag.get_text(strip=True)

#             location = Location.from_string(location_str) if location_str else Location()

#             # Extract date posted
#             date_posted = None
#             time_tag = soup.find("span", class_="posted-time-ago__text")
#             if time_tag:
#                 date_posted = parse_relative_date(time_tag.get_text(strip=True))

#             # Extract job type, level, industry
#             job_type = parse_job_type(soup)
#             job_level = parse_job_level(soup)
#             company_industry = parse_company_industry(soup)

#             # Extract salary information
#             salary_min, salary_max, salary_text = parse_salary_from_text(description, html)

#             # Extract experience requirements
#             experience = parse_experience_from_text(description, html)

#             # Check if remote
#             is_remote = is_job_remote(title, description, location)

#             # Check if easy apply (no external URL)
#             is_easy_apply = not external_url

#             # Create compensation object if salary found
#             compensation = None
#             if salary_min or salary_max:
#                 compensation = Compensation(
#                     min_amount=salary_min,
#                     max_amount=salary_max,
#                     currency="USD",
#                     interval="yearly"
#                 )

#             # Get search keyword from job_data if available
#             search_keyword = job_data.get("keyword") if job_data else None

#             # Create JobPost object
#             job = JobPost(
#                 job_id=job_id,
#                 title=title,
#                 company_name=company,
#                 company_logo=company_logo,
#                 location=location,
#                 description=description[:10000] if description else None,
#                 date_posted=date_posted,
#                 job_url=url,
#                 apply_url=external_url,
#                 job_url_direct=external_url,
#                 job_type=job_type,
#                 job_level=job_level,
#                 company_industry=company_industry,
#                 is_remote=is_remote,
#                 is_easy_apply=is_easy_apply,
#                 compensation=compensation,
#                 emails=extract_emails_from_text(description or ""),
#                 search_keyword=search_keyword,
#                 experience=experience,
#                 salary_text=salary_text,
#             )

#             self._handle_success()
#             return job

#         except Exception as e:
#             print(f"❌ Error fetching job {job_id}: {e}")
#             self._handle_error()
#             return None

#     # ===== ULTIMATE EXTERNAL LINK EXTRACTION =====
#     def _extract_external_url_ultimate(self, soup: BeautifulSoup, html: str, job_id: str) -> Optional[str]:
#         """
#         ULTIMATE extraction method - tries EVERY possible way to find external links
#         """

#         print(f"      🔍 Searching for external link...")

#         # METHOD 1: Find ALL script tags and search for applyUrl patterns
#         script_tags = soup.find_all('script')
#         for script in script_tags:
#             if script.string:
#                 script_text = script.string

#                 patterns = [
#                     r'"applyUrl"\s*:\s*"([^"]+)"',
#                     r'"externalApplyUrl"\s*:\s*"([^"]+)"',
#                     r'applyUrl["\']?\s*:\s*["\']([^"\']+)["\']',
#                     r'applyUrl\\":\\"([^\\]+)\\"',
#                 ]

#                 for pattern in patterns:
#                     matches = re.findall(pattern, script_text, re.IGNORECASE)
#                     for match in matches:
#                         url = match.replace('\\/', '/').replace('\\\\', '\\')
#                         if url and 'linkedin.com' not in url and url.startswith('http'):
#                             print(f"      ✅ FOUND external link in script: {url[:60]}...")
#                             return url

#         # METHOD 2: Look for applyUrl in the entire HTML
#         patterns = [
#             r'applyUrl["\']?\s*[:=]\s*["\']([^"\']+)["\']',
#             r'externalApplyUrl["\']?\s*[:=]\s*["\']([^"\']+)["\']',
#             r'<code[^>]*id="applyUrl"[^>]*>(.*?)</code>',
#         ]

#         for pattern in patterns:
#             matches = re.findall(pattern, html, re.IGNORECASE | re.DOTALL)
#             for match in matches:
#                 if isinstance(match, tuple):
#                     match = match[0]
#                 url = str(match).replace('\\/', '/').replace('\\\\', '\\')

#                 comment_match = re.search(r'<!--.*?url=([^&\s]+).*?-->', url)
#                 if comment_match:
#                     url = unquote(comment_match.group(1))

#                 if url and 'linkedin.com' not in url and url.startswith('http'):
#                     print(f"      ✅ FOUND external link in HTML: {url[:60]}...")
#                     return url

#         # METHOD 3: Look for externalApply endpoint pattern
#         ext_pattern = rf'(?:externalApply|jobs/view/externalApply)/{job_id}\?url=([^"&\s>]+)'
#         match = re.search(ext_pattern, html, re.IGNORECASE)
#         if match:
#             url = unquote(match.group(1))
#             if url and 'linkedin.com' not in url:
#                 print(f"      ✅ FOUND external link via endpoint pattern: {url[:60]}...")
#                 return url

#         # METHOD 4: Look for any external links that might be apply buttons
#         apply_links = soup.find_all('a', href=True)
#         for link in apply_links:
#             href = link.get('href', '')
#             if href and 'linkedin.com' not in href and href.startswith('http'):
#                 link_text = link.get_text(strip=True).lower()
#                 link_classes = str(link.get('class', '')).lower()

#                 apply_indicators = ['apply', 'application', 'submit', 'external', 'careers']
#                 if any(ind in link_text for ind in apply_indicators) or any(ind in link_classes for ind in apply_indicators):
#                     print(f"      ✅ FOUND external link via button: {href[:60]}...")
#                     return href

#         # METHOD 5: Try the externalApply endpoint directly
#         try:
#             ext_url = f"{self.base_url}/jobs/view/externalApply/{job_id}"
#             ext_response = self.session.get(ext_url, timeout=5, allow_redirects=True)

#             final_url = ext_response.url
#             if final_url and 'linkedin.com' not in final_url:
#                 print(f"      ✅ FOUND external link via endpoint: {final_url[:60]}...")
#                 return final_url
#         except Exception:
#             pass

#         print(f"      ❌ No external link found (Easy Apply job)")
#         return None

#     def _is_linkedin_internal(self, url: str) -> bool:
#         """Check if URL is a LinkedIn internal page"""
#         if not url:
#             return True

#         url_lower = url.lower()

#         if 'linkedin.com' in url_lower:
#             return True

#         internal_patterns = ['signup', 'login', 'auth', 'checkpoint', 'cold-join', 'registration', 'sign-in']
#         for pattern in internal_patterns:
#             if pattern in url_lower:
#                 return True

#         return False

#     def scrape_all_jobs_batch(self, keywords: List[str], location: str = "United States",
#                               max_workers: int = 5, save_to_db: bool = True) -> List[JobPost]:
#         """
#         Scrape ALL jobs posted in last 24 hours for multiple keywords in parallel.
#         No per-keyword job limit — fetches every page until LinkedIn returns empty.
#         """
#         all_jobs = []
#         all_job_dicts = []

#         # ── Phase 1: collect job IDs for every keyword ──────────────────────
#         all_search_results = []
#         seen_global_ids = set()   # Global dedup across keywords
#         total_keywords = len(keywords)

#         for idx, keyword in enumerate(keywords):
#             print(f"\n{'='*60}")
#             print(f"🔍 [{idx+1}/{total_keywords}] Searching ALL jobs for: {keyword}")
#             print(f"{'='*60}")

#             jobs = self.search_all_jobs(keyword, location, hours_old=24)

#             added = 0
#             for job in jobs:
#                 if job["job_id"] not in seen_global_ids:
#                     seen_global_ids.add(job["job_id"])
#                     job["keyword"] = keyword
#                     all_search_results.append(job)
#                     added += 1

#             print(f"   ✅ {idx+1}/{total_keywords} done  |  +{added} new unique jobs  |  running total: {len(all_search_results)}")

#             if idx < len(keywords) - 1:
#                 delay = random.uniform(3, 6)
#                 print(f"   ⏱️  Waiting {delay:.1f}s before next keyword...")
#                 time.sleep(delay)

#         print(f"\n{'='*60}")
#         print(f"📊 TOTAL UNIQUE JOBS FOUND: {len(all_search_results)}")
#         print(f"{'='*60}")

#         if not all_search_results:
#             print("❌ No jobs found for any keyword")
#             return []

#         # ── Phase 2: fetch details in parallel (extracts external links) ────
#         print(f"\n🔗 Fetching details for {len(all_search_results)} jobs ({max_workers} parallel workers)...")

#         actual_workers = min(max_workers, 10)

#         with ThreadPoolExecutor(max_workers=actual_workers) as executor:
#             future_to_job = {
#                 executor.submit(self.get_job_details, job["job_id"], job): job
#                 for job in all_search_results
#             }

#             completed = 0
#             external_count = 0
#             salary_count = 0
#             exp_count = 0
#             total = len(all_search_results)

#             for future in as_completed(future_to_job):
#                 completed += 1
#                 job = future_to_job[future]

#                 if completed % 25 == 0 or completed == 1 or completed == total:
#                     pct = completed / total * 100
#                     print(f"   Progress: {completed}/{total} ({pct:.1f}%) | "
#                           f"external={external_count} salary={salary_count}")

#                 try:
#                     job_post = future.result(timeout=15)
#                     if job_post:
#                         all_jobs.append(job_post)

#                         if job_post.apply_url:
#                             external_count += 1
#                         if job_post.compensation and job_post.compensation.min_amount:
#                             salary_count += 1
#                         if job_post.experience:
#                             exp_count += 1

#                         job_dict = job_post.to_supabase_dict()
#                         all_job_dicts.append(job_dict)

#                 except Exception as e:
#                     print(f"   ✗ Error processing job {job['job_id']}: {e}")

#         # ── Phase 3: save to Supabase ────────────────────────────────────────
#         if save_to_db and self.db and self.db.initialized and all_job_dicts:
#             self.db.save_jobs_batch(all_job_dicts)
#         elif save_to_db:
#             print("\n⚠️ Supabase not initialised — skipping database save")

#         # ── Final summary ────────────────────────────────────────────────────
#         print(f"\n{'='*60}")
#         print("✅ SCRAPE COMPLETE")
#         print(f"{'='*60}")
#         if all_jobs:
#             print(f"📊 Total jobs processed : {len(all_jobs)}")
#             print(f"🔗 External links found : {external_count} ({external_count/len(all_jobs)*100:.1f}%)")
#             print(f"💰 Jobs with salary info: {salary_count} ({salary_count/len(all_jobs)*100:.1f}%)")
#             print(f"📝 Jobs with experience : {exp_count} ({exp_count/len(all_jobs)*100:.1f}%)")

#         return all_jobs

#     def save_to_csv(self, jobs: List[JobPost], filename: str = None):
#         """Save jobs to CSV file with enhanced fields"""
#         if not filename:
#             filename = f"linkedin_jobs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

#         import csv
#         with open(filename, 'w', newline='', encoding='utf-8') as f:
#             writer = csv.writer(f)
#             writer.writerow([
#                 'Job ID', 'Title', 'Company', 'Company Logo', 'Location', 'Date Posted',
#                 'Job URL', 'External Apply URL', 'Is Remote', 'Is Easy Apply',
#                 'Job Type', 'Job Level', 'Industry', 'Search Keyword',
#                 'Salary Min', 'Salary Max', 'Salary Text', 'Experience Required',
#                 'Description Preview'
#             ])

#             for job in jobs:
#                 writer.writerow([
#                     job.job_id,
#                     job.title,
#                     job.company_name,
#                     job.company_logo or '',
#                     job.location.display_location(),
#                     job.date_posted,
#                     job.job_url,
#                     job.apply_url or '',
#                     job.is_remote,
#                     job.is_easy_apply,
#                     ', '.join([jt.value for jt in job.job_type]) if job.job_type else '',
#                     job.job_level or '',
#                     job.company_industry or '',
#                     job.search_keyword or '',
#                     job.compensation.min_amount if job.compensation else '',
#                     job.compensation.max_amount if job.compensation else '',
#                     getattr(job, 'salary_text', ''),
#                     getattr(job, 'experience', ''),
#                     job.description[:200] + '...' if job.description and len(job.description) > 200 else (job.description or '')
#                 ])

#         print(f"💾 Saved {len(jobs)} jobs to {filename}")
        
# #         print(f"💾 Saved {len(jobs)} jobs to {filename}")



























# """Main LinkedIn scraper class - optimized for external link extraction with Supabase"""

# import os
# import time
# import random
# import re
# import json
# import threading
# import urllib.parse
# from datetime import datetime, date
# from typing import Optional, List, Dict, Any, Tuple
# from urllib.parse import urlparse, unquote, parse_qs, urljoin
# from concurrent.futures import ThreadPoolExecutor, as_completed

# import requests
# from bs4 import BeautifulSoup

# from .models import JobPost, Location, Compensation, Country, JobType
# from .constant import headers
# from .util import (
#     job_type_code,
#     parse_job_type,
#     parse_job_level,
#     parse_company_industry,
#     is_job_remote,
#     extract_external_url_from_html,
#     extract_emails_from_text,
#     currency_parser,
#     parse_relative_date,
#     create_session,
#     remove_attributes,
#     parse_salary_from_text,
#     parse_experience_from_text,
#     extract_company_logo,
# )
# from .database import SupabaseManager


# def _is_external(url: str) -> bool:
#     """True only for real third-party URLs that are not LinkedIn."""
#     if not url or not url.startswith("http"):
#         return False
#     try:
#         host = urlparse(url).netloc.lower()
#     except Exception:
#         return False
#     return (
#         "linkedin.com" not in host
#         and "lnkd.in" not in host
#         and host != ""
#     )


# class LinkedInScraper:
#     """High-performance LinkedIn scraper focused on external links with Supabase storage"""

#     def __init__(self, proxies=None, ca_cert=None, user_agent=None, use_database=True):
#         self.base_url = "https://www.linkedin.com"
#         cookie = os.getenv("LINKEDIN_COOKIE")
#         self.session = create_session(proxies=proxies, ca_cert=ca_cert, cookie=cookie)
#         self.session.headers.update(headers)

#         self.min_delay = 1.0
#         self.max_delay = 3.0
#         self.current_delay = self.min_delay
#         self.consecutive_errors = 0
#         self.max_consecutive_errors = 3
#         self.error_backoff = 1.5

#         self._lock = threading.Lock()
#         self._extracted_links = set()

#         self.use_database = use_database
#         self.db = SupabaseManager() if use_database else None
#         if use_database:
#             self.db.initialize()

#     def _throttle(self):
#         with self._lock:
#             time.sleep(self.current_delay + random.uniform(0, 0.5))

#     def _handle_error(self):
#         with self._lock:
#             self.consecutive_errors += 1
#             if self.consecutive_errors >= self.max_consecutive_errors:
#                 self.current_delay = min(self.current_delay * self.error_backoff, self.max_delay)
#                 self.consecutive_errors = 0
#                 print(f"⚠️ Increasing delay to {self.current_delay:.1f}s due to errors")

#     def _handle_success(self):
#         with self._lock:
#             self.consecutive_errors = 0
#             if self.current_delay > self.min_delay:
#                 self.current_delay = max(self.current_delay / self.error_backoff, self.min_delay)

#     def _is_linkedin_internal(self, url: str) -> bool:
#         """Check if URL is a LinkedIn internal page"""
#         if not url:
#             return True
#         url_lower = url.lower()
#         if 'linkedin.com' in url_lower:
#             return True
#         internal_patterns = ['signup', 'login', 'auth', 'checkpoint', 'cold-join', 'registration', 'sign-in']
#         for pattern in internal_patterns:
#             if pattern in url_lower:
#                 return True
#         return False

#     # ─────────────────────────────────────────────────────────────────────────
#     # SEARCH
#     # ─────────────────────────────────────────────────────────────────────────

#     def search_all_jobs(self, keyword: str, location: str = "United States",
#                         hours_old: int = 24) -> List[Dict]:
#         jobs = []
#         seen_job_ids = set()
#         start = 0
#         page = 1
#         max_pages = 200
#         empty_page_retries = 2
#         consecutive_empty = 0

#         print(f"\n   📍 Searching all pages for: {keyword}")

#         while page <= max_pages:
#             params = {
#                 "keywords": keyword,
#                 "location": location,
#                 "distance": "100",
#                 "f_TPR": f"r{hours_old * 3600}",
#                 "start": start,
#                 "refresh": True,
#             }
#             url = f"{self.base_url}/jobs-guest/jobs/api/seeMoreJobPostings/search"

#             try:
#                 self._throttle()
#                 response = self.session.get(url, params=params, timeout=15)

#                 if response.status_code == 429:
#                     wait = random.uniform(10, 20)
#                     print(f"   ⚠️ Rate limited. Waiting {wait:.0f}s...")
#                     time.sleep(wait)
#                     continue

#                 if response.status_code != 200:
#                     print(f"   ❌ Search failed: HTTP {response.status_code}")
#                     self._handle_error()
#                     break

#                 soup = BeautifulSoup(response.text, "html.parser")
#                 job_cards = soup.find_all("div", class_="base-card")

#                 if not job_cards:
#                     consecutive_empty += 1
#                     if consecutive_empty <= empty_page_retries:
#                         print(f"   ⚠️ Empty page at start={start} ({consecutive_empty}/{empty_page_retries}), retrying...")
#                         time.sleep(random.uniform(3, 6))
#                         continue
#                     else:
#                         print(f"   ✅ End of results after {len(jobs)} jobs")
#                         break
#                 consecutive_empty = 0

#                 page_jobs = 0
#                 for card in job_cards:
#                     try:
#                         link_tag = card.find("a", class_="base-card__full-link")
#                         if not link_tag or not link_tag.get("href"):
#                             continue
#                         href = link_tag["href"]
#                         job_id = href.split("?")[0].split("-")[-1]
#                         if job_id in seen_job_ids:
#                             continue
#                         seen_job_ids.add(job_id)

#                         title_tag = card.find("h3", class_="base-search-card__title")
#                         title = title_tag.get_text(strip=True) if title_tag else "Unknown"
#                         company_tag = card.find("h4", class_="base-search-card__subtitle")
#                         company = company_tag.get_text(strip=True) if company_tag else "Unknown"
#                         location_tag = card.find("span", class_="job-search-card__location")
#                         location_str = location_tag.get_text(strip=True) if location_tag else ""

#                         jobs.append({
#                             "job_id": job_id,
#                             "title": title,
#                             "company": company,
#                             "location": location_str,
#                             "link": f"{self.base_url}/jobs/view/{job_id}",
#                         })
#                         page_jobs += 1
#                     except Exception as e:
#                         print(f"   ⚠️ Card parse error: {e}")
#                         continue

#                 print(f"   📄 Page {page} (start={start}): {page_jobs} jobs | total={len(jobs)}")
#                 start += 25
#                 page += 1
#                 self._handle_success()
#                 time.sleep(random.uniform(1.0, 2.5))

#             except Exception as e:
#                 print(f"   ❌ Search error page {page}: {e}")
#                 self._handle_error()
#                 time.sleep(5)
#                 break

#         print(f"   📊 Total unique jobs for '{keyword}': {len(jobs)}")
#         return jobs

#     # ─────────────────────────────────────────────────────────────────────────
#     # JOB DETAILS + EXTERNAL URL EXTRACTION
#     # ─────────────────────────────────────────────────────────────────────────

#     def _fetch_external_url(self, job_id: str, api_html: str, view_html: str) -> Optional[str]:
#         """
#         Extract external apply URL using multiple methods
#         """
        
#         # METHOD 0: Ultra-robust catch-all regex for offsiteApplyUrl
#         for label, html in [("view", view_html), ("api", api_html)]:
#             if not html:
#                 continue
            
#             # This regex captures any `https://...` closely following `offsiteApplyUrl` regardless of quotes or backslashes
#             pattern = r'(?i)offsiteApplyUrl.*?[:=].*?(https?://[^"\'\\,&\s>]+)'
#             matches = re.findall(pattern, html)
#             for url in matches:
#                 try:
#                     url = unquote(url)
#                     url = url.replace('\\/', '/')
#                     is_internal = self._is_linkedin_internal(url)
#                     if url and not is_internal:
#                         print(f"      ✅ [catchall-{label}] {url[:80]}")
#                         return url
#                 except Exception:
#                     pass
        
#         # METHOD 1: Direct regex search for offsiteApplyUrl in raw HTML
#         for label, html in [("view", view_html), ("api", api_html)]:
#             if not html:
#                 continue
            
#             # Look for offsiteApplyUrl directly in the HTML
#             pattern = r'"offsiteApplyUrl"\s*:\s*"(https?://[^"]+)"'
#             matches = re.findall(pattern, html)
#             for url in matches:
#                 if url and not self._is_linkedin_internal(url):
#                     print(f"      ✅ [direct-{label}] {url[:80]}")
#                     return url
            
#             # Also try the escaped version
#             pattern = r'\\?"offsiteApplyUrl\\?"\s*:\s*\\?"(https?://[^"\\]+)\\"'
#             matches = re.findall(pattern, html)
#             for url in matches:
#                 url = url.replace('\\/', '/')
#                 if url and not self._is_linkedin_internal(url):
#                     print(f"      ✅ [direct-escaped-{label}] {url[:80]}")
#                     return url

#         # METHOD 2: Look for applyUrl in script tags
#         for label, html in [("view", view_html), ("api", api_html)]:
#             if not html:
#                 continue
            
#             soup = BeautifulSoup(html, 'html.parser')
#             for script in soup.find_all('script'):
#                 if script.string:
#                     patterns = [
#                         r'"offsiteApplyUrl"\s*:\s*"([^"]+)"',
#                         r'"applyUrl"\s*:\s*"([^"]+)"',
#                         r'"externalApplyUrl"\s*:\s*"([^"]+)"',
#                     ]
#                     for pattern in patterns:
#                         matches = re.findall(pattern, script.string)
#                         for url in matches:
#                             url = url.replace('\\/', '/')
#                             if url and not self._is_linkedin_internal(url):
#                                 print(f"      ✅ [script-{label}] {url[:80]}")
#                                 return url

#         # METHOD 3: Try the externalApply endpoint directly
#         try:
#             ext_url = f"{self.base_url}/jobs/view/externalApply/{job_id}"
#             ext_response = self.session.get(ext_url, timeout=5, allow_redirects=True)
#             final_url = ext_response.url
#             if final_url and not self._is_linkedin_internal(final_url):
#                 print(f"      ✅ [endpoint] {final_url[:80]}")
#                 return final_url
#         except Exception:
#             pass

#         # METHOD 4: Look for apply buttons
#         for label, html in [("view", view_html), ("api", api_html)]:
#             if not html:
#                 continue
#             soup = BeautifulSoup(html, 'html.parser')
            
#             for a in soup.find_all('a', href=True):
#                 href = a.get('href', '')
#                 if not href or self._is_linkedin_internal(href):
#                     continue
                
#                 link_text = a.get_text(strip=True).lower()
#                 link_classes = str(a.get('class', '')).lower()
#                 link_id = str(a.get('id', '')).lower()
                
#                 apply_indicators = ['apply', 'application', 'submit', 'external', 'offsite']
#                 context = link_text + ' ' + link_classes + ' ' + link_id
                
#                 if any(ind in context for ind in apply_indicators):
#                     print(f"      ✅ [button-{label}] {href[:80]}")
#                     return href

#         # METHOD 5: Look for redirect URLs in query parameters
#         for label, html in [("view", view_html), ("api", api_html)]:
#             if not html:
#                 continue
            
#             redirect_patterns = [
#                 r'[?&]url=([^&"\'\s>]+)',
#                 r'[?&]redirectUrl=([^&"\'\s>]+)',
#                 r'[?&]applyUrl=([^&"\'\s>]+)',
#             ]
            
#             for pattern in redirect_patterns:
#                 matches = re.findall(pattern, html)
#                 for match in matches:
#                     try:
#                         url = unquote(match)
#                         if url and not self._is_linkedin_internal(url):
#                             print(f"      ✅ [redirect-{label}] {url[:80]}")
#                             return url
#                     except:
#                         pass

#         print(f"      ℹ️  No external URL found for {job_id} — Easy Apply")
#         return None

#     def get_job_details(self, job_id: str, job_data: Dict = None) -> Optional[JobPost]:
#         job_view_url = f"{self.base_url}/jobs/view/{job_id}"
#         api_url = f"{self.base_url}/jobs-guest/jobs/api/jobPosting/{job_id}"

#         try:
#             # Fetch API page
#             self._throttle()
#             api_resp = self.session.get(api_url, timeout=10)
#             if api_resp.status_code == 429:
#                 print(f"      ℹ️ Guest API rate limited for {job_id}, falling back to view page...")
#                 api_html = ""
#             elif api_resp.status_code != 200:
#                 print(f"      ℹ️ Guest API fetch failed {job_id}: {api_resp.status_code}, falling back...")
#                 api_html = ""
#             else:
#                 api_html = api_resp.text

#             # Fetch view page
#             self._throttle()
#             view_resp = self.session.get(job_view_url, timeout=10)
#             view_html = view_resp.text if view_resp.status_code == 200 else ""
            
#             soup = BeautifulSoup(view_html or api_html, "html.parser")

#             # Extract external URL
#             external_url = self._fetch_external_url(job_id, api_html, view_html)

#             # Metadata extraction
#             title = (job_data or {}).get("title", "")
#             if not title:
#                 t = soup.find("h1", class_="top-card-layout__title")
#                 title = t.get_text(strip=True) if t else "Unknown"

#             company = (job_data or {}).get("company", "")
#             if not company:
#                 c = soup.find("a", class_="topcard__org-name-link")
#                 company = c.get_text(strip=True) if c else "Unknown"

#             company_logo = extract_company_logo(soup)

#             description = ""
#             for sel in ["div.show-more-less-html__markup",
#                         "div.description__text",
#                         "div.jobs-description__content"]:
#                 d = soup.select_one(sel)
#                 if d:
#                     description = d.get_text(strip=True)
#                     break

#             location_str = (job_data or {}).get("location", "")
#             if not location_str:
#                 lt = soup.find("span", class_="topcard__flavor--bullet")
#                 location_str = lt.get_text(strip=True) if lt else ""
#             location = Location.from_string(location_str) if location_str else Location()

#             date_posted = None
#             tt = soup.find("span", class_="posted-time-ago__text")
#             if tt:
#                 date_posted = parse_relative_date(tt.get_text(strip=True))

#             job_type = parse_job_type(soup)
#             job_level = parse_job_level(soup)
#             company_industry = parse_company_industry(soup)

#             salary_min, salary_max, salary_text = parse_salary_from_text(
#                 description, view_html or api_html)
#             experience = parse_experience_from_text(description, view_html or api_html)
#             is_remote = is_job_remote(title, description, location)

#             compensation = None
#             if salary_min or salary_max:
#                 compensation = Compensation(
#                     min_amount=salary_min,
#                     max_amount=salary_max,
#                     currency="USD",
#                     interval="yearly",
#                 )

#             job = JobPost(
#                 job_id=job_id,
#                 title=title,
#                 company_name=company,
#                 company_logo=company_logo,
#                 location=location,
#                 description=description[:10000] if description else None,
#                 date_posted=date_posted,
#                 job_url=job_view_url,
#                 apply_url=external_url,
#                 job_url_direct=external_url,
#                 job_type=job_type,
#                 job_level=job_level,
#                 company_industry=company_industry,
#                 is_remote=is_remote,
#                 is_easy_apply=not external_url,
#                 compensation=compensation,
#                 emails=extract_emails_from_text(description or ""),
#                 search_keyword=(job_data or {}).get("keyword"),
#                 experience=experience,
#                 salary_text=salary_text,
#             )

#             self._handle_success()
#             return job

#         except Exception as e:
#             print(f"❌ Error fetching job {job_id}: {e}")
#             self._handle_error()
#             return None

#     # ─────────────────────────────────────────────────────────────────────────
#     # BATCH SCRAPE - THIS IS THE METHOD YOUR run.py IS CALLING
#     # ─────────────────────────────────────────────────────────────────────────

#     def scrape_all_jobs_batch(self, keywords: List[str],
#                               location: str = "United States",
#                               max_workers: int = 5,
#                               save_to_db: bool = True) -> List[JobPost]:
#         """
#         Scrape ALL jobs posted in last 24 hours for multiple keywords in parallel.
#         No per-keyword job limit — fetches every page until LinkedIn returns empty.
#         """
#         all_jobs = []
#         all_job_dicts = []
#         seen_global_ids = set()
#         total_keywords = len(keywords)
#         actual_workers = min(max_workers, 5)
#         total_saved_to_db = 0
#         grand_external = 0
#         grand_salary = 0
#         grand_exp = 0

#         def _flush_to_db(batch: list, keyword: str):
#             nonlocal total_saved_to_db
#             if not (save_to_db and self.db and self.db.initialized and batch):
#                 return
#             try:
#                 self.db.save_jobs_batch(batch)
#                 total_saved_to_db += len(batch)
#                 print(f"   💾 [{keyword}] Saved {len(batch)} jobs (total={total_saved_to_db})")
#             except Exception as e:
#                 print(f"   ⚠️ DB save error [{keyword}]: {e}")

#         if save_to_db and not (self.db and self.db.initialized):
#             print("\n⚠️ Supabase not initialised — DB saves skipped")

#         for idx, keyword in enumerate(keywords):
#             print(f"\n{'='*60}")
#             print(f"🔍 [{idx+1}/{total_keywords}] Keyword: {keyword}")
#             print(f"{'='*60}")

#             raw_jobs = self.search_all_jobs(keyword, location, hours_old=24)

#             keyword_results = []
#             for job in raw_jobs:
#                 if job["job_id"] not in seen_global_ids:
#                     seen_global_ids.add(job["job_id"])
#                     job["keyword"] = keyword
#                     keyword_results.append(job)

#             print(f"   📋 {len(keyword_results)} unique new jobs for '{keyword}'")

#             if not keyword_results:
#                 if idx < total_keywords - 1:
#                     delay = random.uniform(3, 6)
#                     print(f"   ⏱️  Waiting {delay:.1f}s...")
#                     time.sleep(delay)
#                 continue

#             print(f"   🔗 Fetching details ({actual_workers} workers)...")

#             keyword_jobs = []
#             keyword_dicts = []
#             external_count = salary_count = exp_count = completed = 0
#             kw_total = len(keyword_results)

#             with ThreadPoolExecutor(max_workers=actual_workers) as executor:
#                 future_to_job = {
#                     executor.submit(self.get_job_details, j["job_id"], j): j
#                     for j in keyword_results
#                 }
#                 for future in as_completed(future_to_job):
#                     completed += 1
#                     src_job = future_to_job[future]

#                     if completed % 25 == 0 or completed == 1 or completed == kw_total:
#                         print(f"   Progress: {completed}/{kw_total} ({completed/kw_total*100:.0f}%) | external={external_count}")

#                     try:
#                         job_post = future.result(timeout=15)
#                         if job_post:
#                             keyword_jobs.append(job_post)
#                             all_jobs.append(job_post)
#                             if job_post.apply_url:
#                                 external_count += 1
#                             if job_post.compensation and job_post.compensation.min_amount:
#                                 salary_count += 1
#                             if job_post.experience:
#                                 exp_count += 1
#                             d = job_post.to_supabase_dict()
#                             keyword_dicts.append(d)
#                             all_job_dicts.append(d)
#                     except Exception as e:
#                         print(f"   ✗ {src_job['job_id']}: {e}")

#             _flush_to_db(keyword_dicts, keyword)
#             grand_external += external_count
#             grand_salary += salary_count
#             grand_exp += exp_count

#             print(f"   ✅ '{keyword}': {len(keyword_jobs)} jobs, {external_count} external links")

#             if idx < total_keywords - 1:
#                 delay = random.uniform(3, 6)
#                 print(f"   ⏱️  Waiting {delay:.1f}s before next keyword...")
#                 time.sleep(delay)

#         print(f"\n{'='*60}")
#         print("✅ SCRAPE COMPLETE")
#         print(f"{'='*60}")
#         if all_jobs:
#             pct = grand_external / len(all_jobs) * 100
#             print(f"📊 Total jobs      : {len(all_jobs)}")
#             print(f"🔗 External links  : {grand_external} ({pct:.1f}%)")
#             print(f"💰 With salary     : {grand_salary}")
#             print(f"📝 With experience : {grand_exp}")
#             print(f"💾 Saved to DB     : {total_saved_to_db}")

#         return all_jobs

#     def save_to_csv(self, jobs: List[JobPost], filename: str = None):
#         if not filename:
#             filename = f"linkedin_jobs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
#         import csv
#         with open(filename, "w", newline="", encoding="utf-8") as f:
#             writer = csv.writer(f)
#             writer.writerow([
#                 "Job ID", "Title", "Company", "Company Logo", "Location",
#                 "Date Posted", "Job URL", "External Apply URL", "Is Remote",
#                 "Is Easy Apply", "Job Type", "Job Level", "Industry",
#                 "Search Keyword", "Salary Min", "Salary Max", "Salary Text",
#                 "Experience Required", "Description Preview",
#             ])
#             for job in jobs:
#                 writer.writerow([
#                     job.job_id, job.title, job.company_name,
#                     job.company_logo or "",
#                     job.location.display_location(),
#                     job.date_posted, job.job_url, job.apply_url or "",
#                     job.is_remote, job.is_easy_apply,
#                     ", ".join(jt.value for jt in job.job_type) if job.job_type else "",
#                     job.job_level or "", job.company_industry or "",
#                     job.search_keyword or "",
#                     job.compensation.min_amount if job.compensation else "",
#                     job.compensation.max_amount if job.compensation else "",
#                     getattr(job, "salary_text", "") or "",
#                     getattr(job, "experience", "") or "",
#                     (job.description or "")[:200],
#                 ])
#         print(f"💾 Saved {len(jobs)} jobs to {filename}")



















































































































# """Main LinkedIn scraper class - optimized for external link extraction with Supabase"""

# import os
# import time
# import random
# import re
# import json
# import threading
# import urllib.parse
# from datetime import datetime, date
# from typing import Optional, List, Dict, Any, Tuple
# from urllib.parse import urlparse, unquote, parse_qs, urljoin
# from concurrent.futures import ThreadPoolExecutor, as_completed

# import requests
# from bs4 import BeautifulSoup

# from .models import JobPost, Location, Compensation, Country, JobType
# from .constant import headers
# from .util import (
#     job_type_code,
#     parse_job_type,
#     parse_job_level,
#     parse_company_industry,
#     is_job_remote,
#     extract_external_url_from_html,
#     extract_emails_from_text,
#     currency_parser,
#     parse_relative_date,
#     create_session,
#     remove_attributes,
#     parse_salary_from_text,
#     parse_experience_from_text,
#     extract_company_logo,
# )
# from .database import SupabaseManager


# def _is_external(url: str) -> bool:
#     """True only for real third-party URLs that are not LinkedIn."""
#     if not url or not url.startswith("http"):
#         return False
#     try:
#         host = urlparse(url).netloc.lower()
#     except Exception:
#         return False
#     return (
#         "linkedin.com" not in host
#         and "lnkd.in" not in host
#         and host != ""
#     )


# class LinkedInScraper:
#     """High-performance LinkedIn scraper focused on external links with Supabase storage"""

#     def __init__(self, proxies=None, ca_cert=None, user_agent=None, use_database=True):
#         self.base_url = "https://www.linkedin.com"
#         cookie = os.getenv("LINKEDIN_COOKIE")
#         self.session = create_session(proxies=proxies, ca_cert=ca_cert, cookie=cookie)
#         self.session.headers.update(headers)

#         self.min_delay = 1.0
#         self.max_delay = 3.0
#         self.current_delay = self.min_delay
#         self.consecutive_errors = 0
#         self.max_consecutive_errors = 3
#         self.error_backoff = 1.5

#         self._lock = threading.Lock()
#         self._extracted_links = set()

#         self.use_database = use_database
#         self.db = SupabaseManager() if use_database else None
#         if use_database:
#             self.db.initialize()
        
#         # Track saved jobs count
#         self.saved_jobs_count = 0

#     def _throttle(self):
#         with self._lock:
#             time.sleep(self.current_delay + random.uniform(0, 0.5))

#     def _handle_error(self):
#         with self._lock:
#             self.consecutive_errors += 1
#             if self.consecutive_errors >= self.max_consecutive_errors:
#                 self.current_delay = min(self.current_delay * self.error_backoff, self.max_delay)
#                 self.consecutive_errors = 0
#                 print(f"⚠️ Increasing delay to {self.current_delay:.1f}s due to errors")

#     def _handle_success(self):
#         with self._lock:
#             self.consecutive_errors = 0
#             if self.current_delay > self.min_delay:
#                 self.current_delay = max(self.current_delay / self.error_backoff, self.min_delay)

#     def _is_linkedin_internal(self, url: str) -> bool:
#         """Check if URL is a LinkedIn internal page"""
#         if not url:
#             return True
#         url_lower = url.lower()
#         if 'linkedin.com' in url_lower:
#             return True
#         internal_patterns = ['signup', 'login', 'auth', 'checkpoint', 'cold-join', 'registration', 'sign-in']
#         for pattern in internal_patterns:
#             if pattern in url_lower:
#                 return True
#         return False

#     # ─────────────────────────────────────────────────────────────────────────
#     # SEARCH
#     # ─────────────────────────────────────────────────────────────────────────

#     def search_all_jobs(self, keyword: str, location: str = "United States",
#                         hours_old: int = 24) -> List[Dict]:
#         jobs = []
#         seen_job_ids = set()
#         start = 0
#         page = 1
#         max_pages = 200
#         empty_page_retries = 2
#         consecutive_empty = 0

#         print(f"\n   📍 Searching all pages for: {keyword}")

#         while page <= max_pages:
#             params = {
#                 "keywords": keyword,
#                 "location": location,
#                 "distance": "100",
#                 "f_TPR": f"r{hours_old * 3600}",
#                 "start": start,
#                 "refresh": True,
#             }
#             url = f"{self.base_url}/jobs-guest/jobs/api/seeMoreJobPostings/search"

#             try:
#                 self._throttle()
#                 response = self.session.get(url, params=params, timeout=15)

#                 if response.status_code == 429:
#                     wait = random.uniform(10, 20)
#                     print(f"   ⚠️ Rate limited. Waiting {wait:.0f}s...")
#                     time.sleep(wait)
#                     continue

#                 if response.status_code != 200:
#                     print(f"   ❌ Search failed: HTTP {response.status_code}")
#                     self._handle_error()
#                     break

#                 soup = BeautifulSoup(response.text, "html.parser")
#                 job_cards = soup.find_all("div", class_="base-card")

#                 if not job_cards:
#                     consecutive_empty += 1
#                     if consecutive_empty <= empty_page_retries:
#                         print(f"   ⚠️ Empty page at start={start} ({consecutive_empty}/{empty_page_retries}), retrying...")
#                         time.sleep(random.uniform(3, 6))
#                         continue
#                     else:
#                         print(f"   ✅ End of results after {len(jobs)} jobs")
#                         break
#                 consecutive_empty = 0

#                 page_jobs = 0
#                 for card in job_cards:
#                     try:
#                         link_tag = card.find("a", class_="base-card__full-link")
#                         if not link_tag or not link_tag.get("href"):
#                             continue
#                         href = link_tag["href"]
#                         job_id = href.split("?")[0].split("-")[-1]
#                         if job_id in seen_job_ids:
#                             continue
#                         seen_job_ids.add(job_id)

#                         title_tag = card.find("h3", class_="base-search-card__title")
#                         title = title_tag.get_text(strip=True) if title_tag else "Unknown"
#                         company_tag = card.find("h4", class_="base-search-card__subtitle")
#                         company = company_tag.get_text(strip=True) if company_tag else "Unknown"
#                         location_tag = card.find("span", class_="job-search-card__location")
#                         location_str = location_tag.get_text(strip=True) if location_tag else ""

#                         jobs.append({
#                             "job_id": job_id,
#                             "title": title,
#                             "company": company,
#                             "location": location_str,
#                             "link": f"{self.base_url}/jobs/view/{job_id}",
#                         })
#                         page_jobs += 1
#                     except Exception as e:
#                         print(f"   ⚠️ Card parse error: {e}")
#                         continue

#                 print(f"   📄 Page {page} (start={start}): {page_jobs} jobs | total={len(jobs)}")
#                 start += 25
#                 page += 1
#                 self._handle_success()
#                 time.sleep(random.uniform(1.0, 2.5))

#             except Exception as e:
#                 print(f"   ❌ Search error page {page}: {e}")
#                 self._handle_error()
#                 time.sleep(5)
#                 break

#         print(f"   📊 Total unique jobs for '{keyword}': {len(jobs)}")
#         return jobs

#     # ─────────────────────────────────────────────────────────────────────────
#     # JOB DETAILS + EXTERNAL URL EXTRACTION
#     # ─────────────────────────────────────────────────────────────────────────

#     def _fetch_external_url(self, job_id: str, api_html: str, view_html: str) -> Optional[str]:
#         """
#         Extract external apply URL using multiple methods
#         """
        
#         # METHOD 0: Ultra-robust catch-all regex for offsiteApplyUrl
#         for label, html in [("view", view_html), ("api", api_html)]:
#             if not html:
#                 continue
            
#             # This regex captures any `https://...` closely following `offsiteApplyUrl` regardless of quotes or backslashes
#             pattern = r'(?i)offsiteApplyUrl.*?[:=].*?(https?://[^"\'\\,&\s>]+)'
#             matches = re.findall(pattern, html)
#             for url in matches:
#                 try:
#                     url = unquote(url)
#                     url = url.replace('\\/', '/')
#                     is_internal = self._is_linkedin_internal(url)
#                     if url and not is_internal:
#                         print(f"      ✅ [catchall-{label}] {url[:80]}")
#                         return url
#                 except Exception:
#                     pass
        
#         # METHOD 1: Direct regex search for offsiteApplyUrl in raw HTML
#         for label, html in [("view", view_html), ("api", api_html)]:
#             if not html:
#                 continue
            
#             # Look for offsiteApplyUrl directly in the HTML
#             pattern = r'"offsiteApplyUrl"\s*:\s*"(https?://[^"]+)"'
#             matches = re.findall(pattern, html)
#             for url in matches:
#                 if url and not self._is_linkedin_internal(url):
#                     print(f"      ✅ [direct-{label}] {url[:80]}")
#                     return url
            
#             # Also try the escaped version
#             pattern = r'\\?"offsiteApplyUrl\\?"\s*:\s*\\?"(https?://[^"\\]+)\\"'
#             matches = re.findall(pattern, html)
#             for url in matches:
#                 url = url.replace('\\/', '/')
#                 if url and not self._is_linkedin_internal(url):
#                     print(f"      ✅ [direct-escaped-{label}] {url[:80]}")
#                     return url

#         # METHOD 2: Look for applyUrl in script tags
#         for label, html in [("view", view_html), ("api", api_html)]:
#             if not html:
#                 continue
            
#             soup = BeautifulSoup(html, 'html.parser')
#             for script in soup.find_all('script'):
#                 if script.string:
#                     patterns = [
#                         r'"offsiteApplyUrl"\s*:\s*"([^"]+)"',
#                         r'"applyUrl"\s*:\s*"([^"]+)"',
#                         r'"externalApplyUrl"\s*:\s*"([^"]+)"',
#                     ]
#                     for pattern in patterns:
#                         matches = re.findall(pattern, script.string)
#                         for url in matches:
#                             url = url.replace('\\/', '/')
#                             if url and not self._is_linkedin_internal(url):
#                                 print(f"      ✅ [script-{label}] {url[:80]}")
#                                 return url

#         # METHOD 3: Try the externalApply endpoint directly
#         try:
#             ext_url = f"{self.base_url}/jobs/view/externalApply/{job_id}"
#             ext_response = self.session.get(ext_url, timeout=5, allow_redirects=True)
#             final_url = ext_response.url
#             if final_url and not self._is_linkedin_internal(final_url):
#                 print(f"      ✅ [endpoint] {final_url[:80]}")
#                 return final_url
#         except Exception:
#             pass

#         # METHOD 4: Look for apply buttons
#         for label, html in [("view", view_html), ("api", api_html)]:
#             if not html:
#                 continue
#             soup = BeautifulSoup(html, 'html.parser')
            
#             for a in soup.find_all('a', href=True):
#                 href = a.get('href', '')
#                 if not href or self._is_linkedin_internal(href):
#                     continue
                
#                 link_text = a.get_text(strip=True).lower()
#                 link_classes = str(a.get('class', '')).lower()
#                 link_id = str(a.get('id', '')).lower()
                
#                 apply_indicators = ['apply', 'application', 'submit', 'external', 'offsite']
#                 context = link_text + ' ' + link_classes + ' ' + link_id
                
#                 if any(ind in context for ind in apply_indicators):
#                     print(f"      ✅ [button-{label}] {href[:80]}")
#                     return href

#         # METHOD 5: Look for redirect URLs in query parameters
#         for label, html in [("view", view_html), ("api", api_html)]:
#             if not html:
#                 continue
            
#             redirect_patterns = [
#                 r'[?&]url=([^&"\'\s>]+)',
#                 r'[?&]redirectUrl=([^&"\'\s>]+)',
#                 r'[?&]applyUrl=([^&"\'\s>]+)',
#             ]
            
#             for pattern in redirect_patterns:
#                 matches = re.findall(pattern, html)
#                 for match in matches:
#                     try:
#                         url = unquote(match)
#                         if url and not self._is_linkedin_internal(url):
#                             print(f"      ✅ [redirect-{label}] {url[:80]}")
#                             return url
#                     except:
#                         pass

#         print(f"      ℹ️  No external URL found for {job_id} — Easy Apply")
#         return None

#     def _save_job_to_db(self, job: JobPost, keyword: str) -> bool:
#         """
#         Save a single job to database immediately after it's fetched.
#         Returns True if saved successfully, False otherwise.
#         """
#         if not self.use_database or not self.db or not self.db.initialized:
#             return False
        
#         try:
#             job_dict = job.to_supabase_dict()
#             result = self.db.save_job(job_dict)
            
#             if result:
#                 self.saved_jobs_count += 1
#                 # Show progress every 10 jobs or if it has external link
#                 if self.saved_jobs_count % 10 == 0 or job.apply_url:
#                     print(f"      💾 [{keyword}] Job {job.job_id} saved to DB (total saved: {self.saved_jobs_count})")
#                 return True
#             else:
#                 # Job already exists or save failed
#                 return False
                
#         except Exception as e:
#             print(f"      ⚠️ Failed to save job {job.job_id}: {e}")
#             return False

#     def get_job_details(self, job_id: str, job_data: Dict = None) -> Optional[JobPost]:
#         job_view_url = f"{self.base_url}/jobs/view/{job_id}"
#         api_url = f"{self.base_url}/jobs-guest/jobs/api/jobPosting/{job_id}"

#         try:
#             # Fetch API page
#             self._throttle()
#             api_resp = self.session.get(api_url, timeout=10)
#             if api_resp.status_code == 429:
#                 print(f"      ℹ️ Guest API rate limited for {job_id}, falling back to view page...")
#                 api_html = ""
#             elif api_resp.status_code != 200:
#                 print(f"      ℹ️ Guest API fetch failed {job_id}: {api_resp.status_code}, falling back...")
#                 api_html = ""
#             else:
#                 api_html = api_resp.text

#             # Fetch view page
#             self._throttle()
#             view_resp = self.session.get(job_view_url, timeout=10)
#             view_html = view_resp.text if view_resp.status_code == 200 else ""
            
#             soup = BeautifulSoup(view_html or api_html, "html.parser")

#             # Extract external URL
#             external_url = self._fetch_external_url(job_id, api_html, view_html)

#             # Metadata extraction
#             title = (job_data or {}).get("title", "")
#             if not title:
#                 t = soup.find("h1", class_="top-card-layout__title")
#                 title = t.get_text(strip=True) if t else "Unknown"

#             company = (job_data or {}).get("company", "")
#             if not company:
#                 c = soup.find("a", class_="topcard__org-name-link")
#                 company = c.get_text(strip=True) if c else "Unknown"

#             company_logo = extract_company_logo(soup)

#             description = ""
#             for sel in ["div.show-more-less-html__markup",
#                         "div.description__text",
#                         "div.jobs-description__content"]:
#                 d = soup.select_one(sel)
#                 if d:
#                     description = d.get_text(strip=True)
#                     break

#             location_str = (job_data or {}).get("location", "")
#             if not location_str:
#                 lt = soup.find("span", class_="topcard__flavor--bullet")
#                 location_str = lt.get_text(strip=True) if lt else ""
#             location = Location.from_string(location_str) if location_str else Location()

#             date_posted = None
#             tt = soup.find("span", class_="posted-time-ago__text")
#             if tt:
#                 date_posted = parse_relative_date(tt.get_text(strip=True))

#             job_type = parse_job_type(soup)
#             job_level = parse_job_level(soup)
#             company_industry = parse_company_industry(soup)

#             salary_min, salary_max, salary_text = parse_salary_from_text(
#                 description, view_html or api_html)
#             experience = parse_experience_from_text(description, view_html or api_html)
#             is_remote = is_job_remote(title, description, location)

#             compensation = None
#             if salary_min or salary_max:
#                 compensation = Compensation(
#                     min_amount=salary_min,
#                     max_amount=salary_max,
#                     currency="USD",
#                     interval="yearly",
#                 )

#             job = JobPost(
#                 job_id=job_id,
#                 title=title,
#                 company_name=company,
#                 company_logo=company_logo,
#                 location=location,
#                 description=description[:10000] if description else None,
#                 date_posted=date_posted,
#                 job_url=job_view_url,
#                 apply_url=external_url,
#                 job_url_direct=external_url,
#                 job_type=job_type,
#                 job_level=job_level,
#                 company_industry=company_industry,
#                 is_remote=is_remote,
#                 is_easy_apply=not external_url,
#                 compensation=compensation,
#                 emails=extract_emails_from_text(description or ""),
#                 search_keyword=(job_data or {}).get("keyword"),
#                 experience=experience,
#                 salary_text=salary_text,
#             )

#             self._handle_success()
#             return job

#         except Exception as e:
#             print(f"❌ Error fetching job {job_id}: {e}")
#             self._handle_error()
#             return None

#     # ─────────────────────────────────────────────────────────────────────────
#     # BATCH SCRAPE - MODIFIED FOR REAL-TIME STORAGE
#     # ─────────────────────────────────────────────────────────────────────────

#     def scrape_all_jobs_batch(self, keywords: List[str],
#                               location: str = "United States",
#                               max_workers: int = 5,
#                               save_to_db: bool = True) -> List[JobPost]:
#         """
#         Scrape ALL jobs posted in last 24 hours for multiple keywords in parallel.
#         Saves each job to database IMMEDIATELY after it's fetched (real-time storage).
#         """
#         all_jobs = []
#         seen_global_ids = set()
#         total_keywords = len(keywords)
#         actual_workers = min(max_workers, 5)
        
#         # Statistics
#         grand_external = 0
#         grand_salary = 0
#         grand_exp = 0
#         saved_count = 0
#         duplicate_count = 0

#         if save_to_db and not (self.db and self.db.initialized):
#             print("\n⚠️ Supabase not initialised — DB saves will be skipped")
#             save_to_db = False

#         for idx, keyword in enumerate(keywords):
#             print(f"\n{'='*60}")
#             print(f"🔍 [{idx+1}/{total_keywords}] Keyword: {keyword}")
#             print(f"{'='*60}")

#             # Phase 1: Search for jobs
#             raw_jobs = self.search_all_jobs(keyword, location, hours_old=24)

#             keyword_results = []
#             for job in raw_jobs:
#                 if job["job_id"] not in seen_global_ids:
#                     seen_global_ids.add(job["job_id"])
#                     job["keyword"] = keyword
#                     keyword_results.append(job)

#             print(f"   📋 {len(keyword_results)} unique new jobs to fetch for '{keyword}'")

#             if not keyword_results:
#                 if idx < total_keywords - 1:
#                     delay = random.uniform(3, 6)
#                     print(f"   ⏱️  Waiting {delay:.1f}s...")
#                     time.sleep(delay)
#                 continue

#             print(f"   🔗 Fetching details and saving in real-time ({actual_workers} workers)...")

#             keyword_jobs = []
#             external_count = 0
#             salary_count = 0
#             exp_count = 0
#             completed = 0
#             kw_total = len(keyword_results)
#             keyword_saved = 0

#             with ThreadPoolExecutor(max_workers=actual_workers) as executor:
#                 future_to_job = {
#                     executor.submit(self.get_job_details, j["job_id"], j): j
#                     for j in keyword_results
#                 }
                
#                 for future in as_completed(future_to_job):
#                     completed += 1
#                     src_job = future_to_job[future]

#                     if completed % 25 == 0 or completed == 1 or completed == kw_total:
#                         print(f"   Progress: {completed}/{kw_total} ({completed/kw_total*100:.0f}%) | "
#                               f"external={external_count} | saved={saved_count}")

#                     try:
#                         job_post = future.result(timeout=15)
#                         if job_post:
#                             keyword_jobs.append(job_post)
#                             all_jobs.append(job_post)
                            
#                             # Update statistics
#                             if job_post.apply_url:
#                                 external_count += 1
#                             if job_post.compensation and job_post.compensation.min_amount:
#                                 salary_count += 1
#                             if job_post.experience:
#                                 exp_count += 1
                            
#                             # ─── REAL-TIME DATABASE SAVE ───
#                             # Save each job immediately after it's fetched
#                             if save_to_db and self.db and self.db.initialized:
#                                 job_dict = job_post.to_supabase_dict()
#                                 result = self.db.save_job(job_dict)
#                                 if result:
#                                     saved_count += 1
#                                     keyword_saved += 1
#                                 else:
#                                     duplicate_count += 1
                            
#                     except Exception as e:
#                         print(f"   ✗ {src_job['job_id']}: {e}")

#             # Accumulate grand totals
#             grand_external += external_count
#             grand_salary += salary_count
#             grand_exp += exp_count

#             print(f"   ✅ '{keyword}': {len(keyword_jobs)} jobs, {external_count} external links, "
#                   f"{keyword_saved} saved to DB")

#             if idx < total_keywords - 1:
#                 delay = random.uniform(3, 6)
#                 print(f"   ⏱️  Waiting {delay:.1f}s before next keyword...")
#                 time.sleep(delay)

#         # ── Final summary ────────────────────────────────────────────────────
#         print(f"\n{'='*60}")
#         print("✅ SCRAPE COMPLETE")
#         print(f"{'='*60}")
#         if all_jobs:
#             pct = grand_external / len(all_jobs) * 100 if len(all_jobs) > 0 else 0
#             print(f"📊 Total jobs processed : {len(all_jobs)}")
#             print(f"🔗 External links found : {grand_external} ({pct:.1f}%)")
#             print(f"💰 Jobs with salary info: {grand_salary}")
#             print(f"📝 Jobs with experience : {grand_exp}")
#             if save_to_db:
#                 print(f"💾 Saved to DB          : {saved_count} (new) / {duplicate_count} (duplicates skipped)")

#         return all_jobs

#     def save_to_csv(self, jobs: List[JobPost], filename: str = None):
#         if not filename:
#             filename = f"linkedin_jobs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
#         import csv
#         with open(filename, "w", newline="", encoding="utf-8") as f:
#             writer = csv.writer(f)
#             writer.writerow([
#                 "Job ID", "Title", "Company", "Company Logo", "Location",
#                 "Date Posted", "Job URL", "External Apply URL", "Is Remote",
#                 "Is Easy Apply", "Job Type", "Job Level", "Industry",
#                 "Search Keyword", "Salary Min", "Salary Max", "Salary Text",
#                 "Experience Required", "Description Preview",
#             ])
#             for job in jobs:
#                 writer.writerow([
#                     job.job_id, job.title, job.company_name,
#                     job.company_logo or "",
#                     job.location.display_location(),
#                     job.date_posted, job.job_url, job.apply_url or "",
#                     job.is_remote, job.is_easy_apply,
#                     ", ".join(jt.value for jt in job.job_type) if job.job_type else "",
#                     job.job_level or "", job.company_industry or "",
#                     job.search_keyword or "",
#                     job.compensation.min_amount if job.compensation else "",
#                     job.compensation.max_amount if job.compensation else "",
#                     getattr(job, "salary_text", "") or "",
#                     getattr(job, "experience", "") or "",
#                     (job.description or "")[:200],
#                 ])
#         print(f"💾 Saved {len(jobs)} jobs to {filename}")



























































































# """Main LinkedIn scraper class - optimized for external link extraction with Supabase"""

# import os
# import time
# import random
# import re
# import json
# import threading
# import urllib.parse
# from datetime import datetime, date
# from typing import Optional, List, Dict, Any, Tuple
# from urllib.parse import urlparse, unquote, parse_qs, urljoin
# from concurrent.futures import ThreadPoolExecutor, as_completed

# import requests
# from bs4 import BeautifulSoup

# from .models import JobPost, Location, Compensation, Country, JobType
# from .constant import headers
# from .util import (
#     job_type_code,
#     parse_job_type,
#     parse_job_level,
#     parse_company_industry,
#     is_job_remote,
#     extract_external_url_from_html,
#     extract_emails_from_text,
#     currency_parser,
#     parse_relative_date,
#     create_session,
#     remove_attributes,
#     parse_salary_from_text,
#     parse_experience_from_text,
#     extract_company_logo,
# )
# from .database import SupabaseManager


# def _is_external(url: str) -> bool:
#     """True only for real third-party URLs that are not LinkedIn."""
#     if not url or not url.startswith("http"):
#         return False
#     try:
#         host = urlparse(url).netloc.lower()
#     except Exception:
#         return False
#     return (
#         "linkedin.com" not in host
#         and "lnkd.in" not in host
#         and host != ""
#     )


# class LinkedInScraper:
#     """High-performance LinkedIn scraper focused on external links with Supabase storage"""

#     def __init__(self, proxies=None, ca_cert=None, user_agent=None, use_database=True):
#         self.base_url = "https://www.linkedin.com"
#         cookie = os.getenv("LINKEDIN_COOKIE")
#         self.session = create_session(proxies=proxies, ca_cert=ca_cert, cookie=cookie)
#         self.session.headers.update(headers)

#         self.min_delay = 1.0
#         self.max_delay = 3.0
#         self.current_delay = self.min_delay
#         self.consecutive_errors = 0
#         self.max_consecutive_errors = 3
#         self.error_backoff = 1.5

#         self._lock = threading.Lock()
#         self._extracted_links = set()

#         self.use_database = use_database
#         self.db = SupabaseManager() if use_database else None
#         if use_database:
#             self.db.initialize()
        
#         # Track saved jobs count
#         self.saved_jobs_count = 0

#     def _throttle(self):
#         with self._lock:
#             time.sleep(self.current_delay + random.uniform(0, 0.5))

#     def _handle_error(self):
#         with self._lock:
#             self.consecutive_errors += 1
#             if self.consecutive_errors >= self.max_consecutive_errors:
#                 self.current_delay = min(self.current_delay * self.error_backoff, self.max_delay)
#                 self.consecutive_errors = 0
#                 print(f"⚠️ Increasing delay to {self.current_delay:.1f}s due to errors")

#     def _handle_success(self):
#         with self._lock:
#             self.consecutive_errors = 0
#             if self.current_delay > self.min_delay:
#                 self.current_delay = max(self.current_delay / self.error_backoff, self.min_delay)

#     def _is_linkedin_internal(self, url: str) -> bool:
#         """Check if URL is a LinkedIn internal page"""
#         if not url:
#             return True
#         url_lower = url.lower()
#         if 'linkedin.com' in url_lower:
#             return True
#         internal_patterns = ['signup', 'login', 'auth', 'checkpoint', 'cold-join', 'registration', 'sign-in']
#         for pattern in internal_patterns:
#             if pattern in url_lower:
#                 return True
#         return False

#     # ─────────────────────────────────────────────────────────────────────────
#     # SEARCH
#     # ─────────────────────────────────────────────────────────────────────────

#     def search_all_jobs(self, keyword: str, location: str = "United States",
#                         hours_old: int = 24) -> List[Dict]:
#         jobs = []
#         seen_job_ids = set()
#         start = 0
#         page = 1
#         max_pages = 200
#         empty_page_retries = 2
#         consecutive_empty = 0

#         print(f"\n   📍 Searching all pages for: {keyword}")

#         while page <= max_pages:
#             params = {
#                 "keywords": keyword,
#                 "location": location,
#                 "distance": "100",
#                 "f_TPR": f"r{hours_old * 3600}",
#                 "start": start,
#                 "refresh": True,
#             }
#             url = f"{self.base_url}/jobs-guest/jobs/api/seeMoreJobPostings/search"

#             try:
#                 self._throttle()
#                 response = self.session.get(url, params=params, timeout=15)

#                 if response.status_code == 429:
#                     wait = random.uniform(10, 20)
#                     print(f"   ⚠️ Rate limited. Waiting {wait:.0f}s...")
#                     time.sleep(wait)
#                     continue

#                 if response.status_code != 200:
#                     print(f"   ❌ Search failed: HTTP {response.status_code}")
#                     self._handle_error()
#                     break

#                 soup = BeautifulSoup(response.text, "html.parser")
#                 job_cards = soup.find_all("div", class_="base-card")

#                 if not job_cards:
#                     consecutive_empty += 1
#                     if consecutive_empty <= empty_page_retries:
#                         print(f"   ⚠️ Empty page at start={start} ({consecutive_empty}/{empty_page_retries}), retrying...")
#                         time.sleep(random.uniform(3, 6))
#                         continue
#                     else:
#                         print(f"   ✅ End of results after {len(jobs)} jobs")
#                         break
#                 consecutive_empty = 0

#                 page_jobs = 0
#                 for card in job_cards:
#                     try:
#                         link_tag = card.find("a", class_="base-card__full-link")
#                         if not link_tag or not link_tag.get("href"):
#                             continue
#                         href = link_tag["href"]
#                         job_id = href.split("?")[0].split("-")[-1]
#                         if job_id in seen_job_ids:
#                             continue
#                         seen_job_ids.add(job_id)

#                         title_tag = card.find("h3", class_="base-search-card__title")
#                         title = title_tag.get_text(strip=True) if title_tag else "Unknown"
#                         company_tag = card.find("h4", class_="base-search-card__subtitle")
#                         company = company_tag.get_text(strip=True) if company_tag else "Unknown"
#                         location_tag = card.find("span", class_="job-search-card__location")
#                         location_str = location_tag.get_text(strip=True) if location_tag else ""

#                         jobs.append({
#                             "job_id": job_id,
#                             "title": title,
#                             "company": company,
#                             "location": location_str,
#                             "link": f"{self.base_url}/jobs/view/{job_id}",
#                         })
#                         page_jobs += 1
#                     except Exception as e:
#                         print(f"   ⚠️ Card parse error: {e}")
#                         continue

#                 print(f"   📄 Page {page} (start={start}): {page_jobs} jobs | total={len(jobs)}")
#                 start += 25
#                 page += 1
#                 self._handle_success()
#                 time.sleep(random.uniform(1.0, 2.5))

#             except Exception as e:
#                 print(f"   ❌ Search error page {page}: {e}")
#                 self._handle_error()
#                 time.sleep(5)
#                 break

#         print(f"   📊 Total unique jobs for '{keyword}': {len(jobs)}")
#         return jobs

#     # ─────────────────────────────────────────────────────────────────────────
#     # JOB DETAILS + EXTERNAL URL EXTRACTION
#     # ─────────────────────────────────────────────────────────────────────────

#     def _fetch_external_url(self, job_id: str, api_html: str, view_html: str) -> Optional[str]:
#         """
#         Extract external apply URL using multiple methods
#         """
        
#         # METHOD 0: Ultra-robust catch-all regex for offsiteApplyUrl
#         for label, html in [("view", view_html), ("api", api_html)]:
#             if not html:
#                 continue
            
#             # This regex captures any `https://...` closely following `offsiteApplyUrl` regardless of quotes or backslashes
#             pattern = r'(?i)offsiteApplyUrl.*?[:=].*?(https?://[^"\'\\,&\s>]+)'
#             matches = re.findall(pattern, html)
#             for url in matches:
#                 try:
#                     url = unquote(url)
#                     url = url.replace('\\/', '/')
#                     is_internal = self._is_linkedin_internal(url)
#                     if url and not is_internal:
#                         print(f"      ✅ [catchall-{label}] {url[:80]}")
#                         return url
#                 except Exception:
#                     pass
        
#         # METHOD 1: Direct regex search for offsiteApplyUrl in raw HTML
#         for label, html in [("view", view_html), ("api", api_html)]:
#             if not html:
#                 continue
            
#             # Look for offsiteApplyUrl directly in the HTML
#             pattern = r'"offsiteApplyUrl"\s*:\s*"(https?://[^"]+)"'
#             matches = re.findall(pattern, html)
#             for url in matches:
#                 if url and not self._is_linkedin_internal(url):
#                     print(f"      ✅ [direct-{label}] {url[:80]}")
#                     return url
            
#             # Also try the escaped version
#             pattern = r'\\?"offsiteApplyUrl\\?"\s*:\s*\\?"(https?://[^"\\]+)\\"'
#             matches = re.findall(pattern, html)
#             for url in matches:
#                 url = url.replace('\\/', '/')
#                 if url and not self._is_linkedin_internal(url):
#                     print(f"      ✅ [direct-escaped-{label}] {url[:80]}")
#                     return url

#         # METHOD 2: Look for applyUrl in script tags
#         for label, html in [("view", view_html), ("api", api_html)]:
#             if not html:
#                 continue
            
#             soup = BeautifulSoup(html, 'html.parser')
#             for script in soup.find_all('script'):
#                 if script.string:
#                     patterns = [
#                         r'"offsiteApplyUrl"\s*:\s*"([^"]+)"',
#                         r'"applyUrl"\s*:\s*"([^"]+)"',
#                         r'"externalApplyUrl"\s*:\s*"([^"]+)"',
#                     ]
#                     for pattern in patterns:
#                         matches = re.findall(pattern, script.string)
#                         for url in matches:
#                             url = url.replace('\\/', '/')
#                             if url and not self._is_linkedin_internal(url):
#                                 print(f"      ✅ [script-{label}] {url[:80]}")
#                                 return url

#         # METHOD 3: Try the externalApply endpoint directly
#         try:
#             ext_url = f"{self.base_url}/jobs/view/externalApply/{job_id}"
#             ext_response = self.session.get(ext_url, timeout=5, allow_redirects=True)
#             final_url = ext_response.url
#             if final_url and not self._is_linkedin_internal(final_url):
#                 print(f"      ✅ [endpoint] {final_url[:80]}")
#                 return final_url
#         except Exception:
#             pass

#         # METHOD 4: Look for apply buttons
#         for label, html in [("view", view_html), ("api", api_html)]:
#             if not html:
#                 continue
#             soup = BeautifulSoup(html, 'html.parser')
            
#             for a in soup.find_all('a', href=True):
#                 href = a.get('href', '')
#                 if not href or self._is_linkedin_internal(href):
#                     continue
                
#                 link_text = a.get_text(strip=True).lower()
#                 link_classes = str(a.get('class', '')).lower()
#                 link_id = str(a.get('id', '')).lower()
                
#                 apply_indicators = ['apply', 'application', 'submit', 'external', 'offsite']
#                 context = link_text + ' ' + link_classes + ' ' + link_id
                
#                 if any(ind in context for ind in apply_indicators):
#                     print(f"      ✅ [button-{label}] {href[:80]}")
#                     return href

#         # METHOD 5: Look for redirect URLs in query parameters
#         for label, html in [("view", view_html), ("api", api_html)]:
#             if not html:
#                 continue
            
#             redirect_patterns = [
#                 r'[?&]url=([^&"\'\s>]+)',
#                 r'[?&]redirectUrl=([^&"\'\s>]+)',
#                 r'[?&]applyUrl=([^&"\'\s>]+)',
#             ]
            
#             for pattern in redirect_patterns:
#                 matches = re.findall(pattern, html)
#                 for match in matches:
#                     try:
#                         url = unquote(match)
#                         if url and not self._is_linkedin_internal(url):
#                             print(f"      ✅ [redirect-{label}] {url[:80]}")
#                             return url
#                     except:
#                         pass

#         print(f"      ℹ️  No external URL found for {job_id} — Easy Apply")
#         return None

#     def get_job_details(self, job_id: str, job_data: Dict = None) -> Optional[JobPost]:
#         job_view_url = f"{self.base_url}/jobs/view/{job_id}"
#         api_url = f"{self.base_url}/jobs-guest/jobs/api/jobPosting/{job_id}"

#         try:
#             # Fetch API page
#             self._throttle()
#             api_resp = self.session.get(api_url, timeout=10)
#             if api_resp.status_code == 429:
#                 print(f"      ℹ️ Guest API rate limited for {job_id}, falling back to view page...")
#                 api_html = ""
#             elif api_resp.status_code != 200:
#                 print(f"      ℹ️ Guest API fetch failed {job_id}: {api_resp.status_code}, falling back...")
#                 api_html = ""
#             else:
#                 api_html = api_resp.text

#             # Fetch view page
#             self._throttle()
#             view_resp = self.session.get(job_view_url, timeout=10)
#             view_html = view_resp.text if view_resp.status_code == 200 else ""
            
#             soup = BeautifulSoup(view_html or api_html, "html.parser")

#             # Extract external URL
#             external_url = self._fetch_external_url(job_id, api_html, view_html)

#             # Extract job title
#             title = (job_data or {}).get("title", "")
#             if not title:
#                 title_tag = soup.find("h1", class_="top-card-layout__title")
#                 if title_tag:
#                     title = title_tag.get_text(strip=True)
#                 else:
#                     title_tag = soup.find("h1", class_="jobs-top-card__job-title")
#                     if title_tag:
#                         title = title_tag.get_text(strip=True)
#                     else:
#                         title = "Unknown"

#             # Extract company
#             company = (job_data or {}).get("company", "")
#             if not company:
#                 company_tag = soup.find("a", class_="topcard__org-name-link")
#                 if company_tag:
#                     company = company_tag.get_text(strip=True)
#                 else:
#                     company_tag = soup.find("span", class_="jobs-top-card__company-name")
#                     if company_tag:
#                         company = company_tag.get_text(strip=True)
#                     else:
#                         company = "Unknown"

#             # Extract company logo
#             company_logo = None
#             try:
#                 logo_selectors = [
#                     'img.artdeco-entity-image',
#                     'img.presence-entity__image',
#                     'img[data-delayed-url]',
#                     'img.ivm-view-attr__img--centered',
#                     'img.top-card-layout__entity-image',
#                     'img.jobs-top-card__company-logo'
#                 ]
                
#                 for selector in logo_selectors:
#                     logo_img = soup.select_one(selector)
#                     if logo_img:
#                         for attr in ['src', 'data-delayed-url', 'data-src', 'data-source']:
#                             if logo_img.get(attr):
#                                 url = logo_img[attr]
#                                 if url and url.startswith('http') and 'ghost' not in url.lower():
#                                     company_logo = url
#                                     break
#                         if company_logo:
#                             break
                
#                 if not company_logo:
#                     logo_meta = soup.find('meta', {'property': 'og:image'})
#                     if logo_meta and logo_meta.get('content'):
#                         company_logo = logo_meta.get('content')
#             except:
#                 pass

#             # Extract description
#             description = ""
#             desc_selectors = [
#                 "div.show-more-less-html__markup",
#                 "div.description__text",
#                 "div.jobs-description__content",
#                 "div.job-description__content",
#                 "div.jobs-description",
#                 "div.job-description"
#             ]
#             for selector in desc_selectors:
#                 desc_tag = soup.select_one(selector)
#                 if desc_tag:
#                     description = desc_tag.get_text(strip=True)
#                     break

#             # Extract location
#             location_str = (job_data or {}).get("location", "")
#             if not location_str:
#                 location_tag = soup.find("span", class_="topcard__flavor--bullet")
#                 if location_tag:
#                     location_str = location_tag.get_text(strip=True)
#                 else:
#                     location_tag = soup.find("span", class_="jobs-top-card__location")
#                     if location_tag:
#                         location_str = location_tag.get_text(strip=True)
            
#             location = Location.from_string(location_str) if location_str else Location()

#             # Extract date posted
#             date_posted = None
#             time_tag = soup.find("span", class_="posted-time-ago__text")
#             if not time_tag:
#                 time_tag = soup.find("span", class_="jobs-details-top-card__posted-date")
#             if not time_tag:
#                 time_tag = soup.find("time", class_="jobs-details-top-card__posted-date")
            
#             if time_tag:
#                 date_text = time_tag.get_text(strip=True)
#                 if date_text:
#                     date_posted = parse_relative_date(date_text)

#             # Extract job type
#             job_type = None
#             try:
#                 h3_tag = soup.find(
#                     "h3",
#                     class_="description__job-criteria-subheader",
#                     string=lambda text: text and "Employment type" in text if text else False,
#                 )
                
#                 if h3_tag:
#                     employment_type_span = h3_tag.find_next_sibling(
#                         "span",
#                         class_="description__job-criteria-text description__job-criteria-text--criteria",
#                     )
#                     if employment_type_span:
#                         employment_type = employment_type_span.get_text(strip=True).lower().replace("-", "")
#                         type_map = {
#                             "fulltime": JobType.FULL_TIME,
#                             "full time": JobType.FULL_TIME,
#                             "parttime": JobType.PART_TIME,
#                             "part time": JobType.PART_TIME,
#                             "contract": JobType.CONTRACT,
#                             "internship": JobType.INTERNSHIP,
#                             "temporary": JobType.TEMPORARY,
#                         }
#                         for key, value in type_map.items():
#                             if key in employment_type:
#                                 job_type = [value]
#                                 break
                
#                 if not job_type and description:
#                     desc_lower = description.lower()
#                     if "full-time" in desc_lower or "full time" in desc_lower:
#                         job_type = [JobType.FULL_TIME]
#                     elif "part-time" in desc_lower or "part time" in desc_lower:
#                         job_type = [JobType.PART_TIME]
#                     elif "contract" in desc_lower:
#                         job_type = [JobType.CONTRACT]
#                     elif "internship" in desc_lower:
#                         job_type = [JobType.INTERNSHIP]
#             except:
#                 pass

#             # Extract job level
#             job_level = None
#             try:
#                 h3_tag = soup.find(
#                     "h3",
#                     class_="description__job-criteria-subheader",
#                     string=lambda text: text and "Seniority level" in text if text else False,
#                 )
                
#                 if h3_tag:
#                     job_level_span = h3_tag.find_next_sibling(
#                         "span",
#                         class_="description__job-criteria-text description__job-criteria-text--criteria",
#                     )
#                     if job_level_span:
#                         job_level = job_level_span.get_text(strip=True)
                
#                 if not job_level and description:
#                     desc_lower = description.lower()
#                     if "entry level" in desc_lower or "junior" in desc_lower:
#                         job_level = "Entry Level"
#                     elif "senior" in desc_lower or "lead" in desc_lower:
#                         job_level = "Senior Level"
#                     elif "director" in desc_lower or "vp" in desc_lower:
#                         job_level = "Executive Level"
#             except:
#                 pass

#             # Extract company industry
#             company_industry = None
#             try:
#                 h3_tag = soup.find(
#                     "h3",
#                     class_="description__job-criteria-subheader",
#                     string=lambda text: text and "Industries" in text if text else False,
#                 )
                
#                 if h3_tag:
#                     industry_span = h3_tag.find_next_sibling(
#                         "span",
#                         class_="description__job-criteria-text description__job-criteria-text--criteria",
#                     )
#                     if industry_span:
#                         company_industry = industry_span.get_text(strip=True)
#             except:
#                 pass

#             # Extract salary information
#             salary_min, salary_max, salary_text = None, None, None
#             try:
#                 salary_selectors = [
#                     "span.job-details-salary-meta__salary",
#                     "span.jobs-details-salary-meta__salary",
#                     "div.job-details-salary-meta__salary",
#                     "div.jobs-details-salary-meta__salary"
#                 ]
                
#                 for selector in salary_selectors:
#                     salary_tag = soup.select_one(selector)
#                     if salary_tag:
#                         salary_text = salary_tag.get_text(strip=True)
#                         if salary_text:
#                             salary_range = re.findall(r'\$(\d+(?:,\d+)?(?:\.\d+)?)\s*[-–]\s*\$(\d+(?:,\d+)?(?:\.\d+)?)', salary_text)
#                             if salary_range:
#                                 try:
#                                     salary_min = float(salary_range[0][0].replace(',', ''))
#                                     salary_max = float(salary_range[0][1].replace(',', ''))
#                                     break
#                                 except:
#                                     pass
                            
#                             salary_single = re.findall(r'\$(\d+(?:,\d+)?(?:\.\d+)?)', salary_text)
#                             if salary_single and not salary_min:
#                                 try:
#                                     salary_min = float(salary_single[0].replace(',', ''))
#                                     salary_max = salary_min
#                                     break
#                                 except:
#                                     pass
                
#                 if not salary_text and description:
#                     salary_min, salary_max, salary_text = parse_salary_from_text(description, view_html or api_html)
#             except:
#                 pass

#             # Extract experience requirements
#             experience = None
#             try:
#                 exp_selectors = [
#                     "span.job-details-salary-meta__experience",
#                     "span.jobs-details-salary-meta__experience"
#                 ]
                
#                 for selector in exp_selectors:
#                     exp_tag = soup.select_one(selector)
#                     if exp_tag:
#                         experience = exp_tag.get_text(strip=True)
#                         break
                
#                 if not experience and description:
#                     experience = parse_experience_from_text(description, view_html or api_html)
#             except:
#                 pass

#             # Check if remote
#             is_remote = is_job_remote(title, description, location)

#             # Check if easy apply (no external URL)
#             is_easy_apply = not external_url

#             # Create compensation object if salary found
#             compensation = None
#             if salary_min or salary_max:
#                 compensation = Compensation(
#                     min_amount=salary_min,
#                     max_amount=salary_max,
#                     currency="USD",
#                     interval="yearly",
#                 )

#             # Get search keyword from job_data if available
#             search_keyword = (job_data or {}).get("keyword")

#             # Create JobPost object
#             job = JobPost(
#                 job_id=job_id,
#                 title=title,
#                 company_name=company,
#                 company_logo=company_logo,
#                 location=location,
#                 description=description[:10000] if description else None,
#                 date_posted=date_posted,
#                 job_url=job_view_url,
#                 apply_url=external_url,
#                 job_url_direct=external_url,
#                 job_type=job_type,
#                 job_level=job_level,
#                 company_industry=company_industry,
#                 is_remote=is_remote,
#                 is_easy_apply=is_easy_apply,
#                 compensation=compensation,
#                 emails=extract_emails_from_text(description or ""),
#                 search_keyword=search_keyword,
#                 experience=experience,
#                 salary_text=salary_text,
#             )

#             self._handle_success()
            
#             # Print extracted details for debugging
#             if job.apply_url:
#                 print(f"      📊 Extracted: Company Logo={bool(company_logo)}, Salary={salary_text}, Job Type={job_type}, Level={job_level}, Industry={company_industry}")
            
#             return job

#         except Exception as e:
#             print(f"❌ Error fetching job {job_id}: {e}")
#             self._handle_error()
#             return None

#     # ─────────────────────────────────────────────────────────────────────────
#     # BATCH SCRAPE - MODIFIED FOR REAL-TIME STORAGE
#     # ─────────────────────────────────────────────────────────────────────────

#     def scrape_all_jobs_batch(self, keywords: List[str],
#                               location: str = "United States",
#                               max_workers: int = 5,
#                               save_to_db: bool = True) -> List[JobPost]:
#         """
#         Scrape ALL jobs posted in last 24 hours for multiple keywords in parallel.
#         Saves each job to database IMMEDIATELY after it's fetched (real-time storage).
#         """
#         all_jobs = []
#         seen_global_ids = set()
#         total_keywords = len(keywords)
#         actual_workers = min(max_workers, 5)
        
#         # Statistics
#         grand_external = 0
#         grand_salary = 0
#         grand_exp = 0
#         saved_count = 0
#         duplicate_count = 0

#         if save_to_db and not (self.db and self.db.initialized):
#             print("\n⚠️ Supabase not initialised — DB saves will be skipped")
#             save_to_db = False

#         for idx, keyword in enumerate(keywords):
#             print(f"\n{'='*60}")
#             print(f"🔍 [{idx+1}/{total_keywords}] Keyword: {keyword}")
#             print(f"{'='*60}")

#             # Phase 1: Search for jobs
#             raw_jobs = self.search_all_jobs(keyword, location, hours_old=24)

#             keyword_results = []
#             for job in raw_jobs:
#                 if job["job_id"] not in seen_global_ids:
#                     seen_global_ids.add(job["job_id"])
#                     job["keyword"] = keyword
#                     keyword_results.append(job)

#             print(f"   📋 {len(keyword_results)} unique new jobs to fetch for '{keyword}'")

#             if not keyword_results:
#                 if idx < total_keywords - 1:
#                     delay = random.uniform(3, 6)
#                     print(f"   ⏱️  Waiting {delay:.1f}s...")
#                     time.sleep(delay)
#                 continue

#             print(f"   🔗 Fetching details and saving in REAL-TIME ({actual_workers} workers)...")

#             keyword_jobs = []
#             external_count = 0
#             salary_count = 0
#             exp_count = 0
#             completed = 0
#             kw_total = len(keyword_results)
#             keyword_saved = 0

#             with ThreadPoolExecutor(max_workers=actual_workers) as executor:
#                 future_to_job = {
#                     executor.submit(self.get_job_details, j["job_id"], j): j
#                     for j in keyword_results
#                 }
                
#                 for future in as_completed(future_to_job):
#                     completed += 1
#                     src_job = future_to_job[future]

#                     if completed % 25 == 0 or completed == 1 or completed == kw_total:
#                         print(f"   Progress: {completed}/{kw_total} ({completed/kw_total*100:.0f}%) | "
#                               f"external={external_count} | saved={saved_count}")

#                     try:
#                         job_post = future.result(timeout=15)
#                         if job_post:
#                             keyword_jobs.append(job_post)
#                             all_jobs.append(job_post)
                            
#                             # Update statistics
#                             if job_post.apply_url:
#                                 external_count += 1
#                             if job_post.compensation and job_post.compensation.min_amount:
#                                 salary_count += 1
#                             if job_post.experience:
#                                 exp_count += 1
                            
#                             # ─── IMMEDIATE DATABASE SAVE ───
#                             # Save each job to database RIGHT NOW as it's fetched
#                             if save_to_db and self.db and self.db.initialized:
#                                 job_dict = job_post.to_supabase_dict()
#                                 result = self.db.save_job(job_dict)
#                                 if result:
#                                     saved_count += 1
#                                     keyword_saved += 1
#                                     # Show immediate confirmation for external link jobs
#                                     if job_post.apply_url:
#                                         print(f"      🚀 JOB {job_post.job_id} SAVED TO DB (external link found!)")
#                                 else:
#                                     duplicate_count += 1
#                             elif save_to_db and not self.db.initialized:
#                                 print(f"      ⚠️ Database not initialized, skipping save for {job_post.job_id}")
                                
#                     except Exception as e:
#                         print(f"   ✗ {src_job['job_id']}: {e}")

#             # Accumulate grand totals
#             grand_external += external_count
#             grand_salary += salary_count
#             grand_exp += exp_count

#             print(f"   ✅ '{keyword}': {len(keyword_jobs)} jobs, {external_count} external links, "
#                   f"{keyword_saved} saved to DB (real-time)")

#             if idx < total_keywords - 1:
#                 delay = random.uniform(3, 6)
#                 print(f"   ⏱️  Waiting {delay:.1f}s before next keyword...")
#                 time.sleep(delay)

#         # ── Final summary ────────────────────────────────────────────────────
#         print(f"\n{'='*60}")
#         print("✅ SCRAPE COMPLETE")
#         print(f"{'='*60}")
#         if all_jobs:
#             pct = grand_external / len(all_jobs) * 100 if len(all_jobs) > 0 else 0
#             print(f"📊 Total jobs processed : {len(all_jobs)}")
#             print(f"🔗 External links found : {grand_external} ({pct:.1f}%)")
#             print(f"💰 Jobs with salary info: {grand_salary}")
#             print(f"📝 Jobs with experience : {grand_exp}")
#             if save_to_db:
#                 print(f"💾 IMMEDIATE SAVES      : {saved_count} new jobs saved")
#                 print(f"🔄 Duplicates skipped   : {duplicate_count}")

#         return all_jobs

#     def save_to_csv(self, jobs: List[JobPost], filename: str = None):
#         if not filename:
#             filename = f"linkedin_jobs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
#         import csv
#         with open(filename, "w", newline="", encoding="utf-8") as f:
#             writer = csv.writer(f)
#             writer.writerow([
#                 "Job ID", "Title", "Company", "Company Logo", "Location",
#                 "Date Posted", "Job URL", "External Apply URL", "Is Remote",
#                 "Is Easy Apply", "Job Type", "Job Level", "Industry",
#                 "Search Keyword", "Salary Min", "Salary Max", "Salary Text",
#                 "Experience Required", "Description Preview",
#             ])
#             for job in jobs:
#                 writer.writerow([
#                     job.job_id, job.title, job.company_name,
#                     job.company_logo or "",
#                     job.location.display_location(),
#                     job.date_posted, job.job_url, job.apply_url or "",
#                     job.is_remote, job.is_easy_apply,
#                     ", ".join(jt.value for jt in job.job_type) if job.job_type else "",
#                     job.job_level or "", job.company_industry or "",
#                     job.search_keyword or "",
#                     job.compensation.min_amount if job.compensation else "",
#                     job.compensation.max_amount if job.compensation else "",
#                     getattr(job, "salary_text", "") or "",
#                     getattr(job, "experience", "") or "",
#                     (job.description or "")[:200],
#                 ])
#         print(f"💾 Saved {len(jobs)} jobs to {filename}")












































# """Main LinkedIn scraper class - Complete unified extraction for all job fields"""

# import os
# import time
# import random
# import re
# import json
# import threading
# import urllib.parse
# from datetime import datetime, date
# from typing import Optional, List, Dict, Any, Tuple
# from urllib.parse import urlparse, unquote, parse_qs, urljoin
# from concurrent.futures import ThreadPoolExecutor, as_completed

# import requests
# from bs4 import BeautifulSoup

# from .models import JobPost, Location, Compensation, Country, JobType
# from .constant import headers
# from .util import (
#     job_type_code,
#     parse_job_type,
#     parse_job_level,
#     parse_company_industry,
#     is_job_remote,
#     extract_external_url_from_html,
#     extract_emails_from_text,
#     currency_parser,
#     parse_relative_date,
#     create_session,
#     remove_attributes,
#     parse_salary_from_text,
#     parse_experience_from_text,
#     extract_company_logo,
# )
# from .database import SupabaseManager


# def _is_external(url: str) -> bool:
#     """True only for real third-party URLs that are not LinkedIn."""
#     if not url or not url.startswith("http"):
#         return False
#     try:
#         host = urlparse(url).netloc.lower()
#     except Exception:
#         return False
#     return (
#         "linkedin.com" not in host
#         and "lnkd.in" not in host
#         and host != ""
#     )


# class LinkedInScraper:
#     """Complete unified LinkedIn scraper - Extracts all job fields including external links"""

#     def __init__(self, proxies=None, ca_cert=None, user_agent=None, use_database=True):
#         self.base_url = "https://www.linkedin.com"
#         cookie = os.getenv("LINKEDIN_COOKIE")
#         self.session = create_session(proxies=proxies, ca_cert=ca_cert, cookie=cookie)
#         self.session.headers.update(headers)

#         self.min_delay = 1.0
#         self.max_delay = 3.0
#         self.current_delay = self.min_delay
#         self.consecutive_errors = 0
#         self.max_consecutive_errors = 3
#         self.error_backoff = 1.5

#         self._lock = threading.Lock()
#         self._extracted_links = set()

#         self.use_database = use_database
#         self.db = SupabaseManager() if use_database else None
#         if use_database:
#             self.db.initialize()
        
#         self.saved_jobs_count = 0

#     def _throttle(self):
#         with self._lock:
#             time.sleep(self.current_delay + random.uniform(0, 0.5))

#     def _handle_error(self):
#         with self._lock:
#             self.consecutive_errors += 1
#             if self.consecutive_errors >= self.max_consecutive_errors:
#                 self.current_delay = min(self.current_delay * self.error_backoff, self.max_delay)
#                 self.consecutive_errors = 0
#                 print(f"⚠️ Increasing delay to {self.current_delay:.1f}s due to errors")

#     def _handle_success(self):
#         with self._lock:
#             self.consecutive_errors = 0
#             if self.current_delay > self.min_delay:
#                 self.current_delay = max(self.current_delay / self.error_backoff, self.min_delay)

#     def _is_linkedin_internal(self, url: str) -> bool:
#         """Check if URL is a LinkedIn internal page"""
#         if not url:
#             return True
#         url_lower = url.lower()
#         if 'linkedin.com' in url_lower:
#             return True
#         internal_patterns = ['signup', 'login', 'auth', 'checkpoint', 'cold-join', 'registration', 'sign-in']
#         for pattern in internal_patterns:
#             if pattern in url_lower:
#                 return True
#         return False

#     # ─────────────────────────────────────────────────────────────────────────
#     # EXTERNAL LINK EXTRACTION - COMBINED BEST METHODS
#     # ─────────────────────────────────────────────────────────────────────────

#     def _extract_external_url_complete(self, api_soup: BeautifulSoup, api_html: str,
#                                         job_id: str,
#                                         view_soup: BeautifulSoup = None,
#                                         view_html: str = None) -> Optional[str]:
#         """
#         Extract external apply URL using ALL available methods.
#         Combines the best of both Code A and Code B.
#         """
        
#         # METHOD 0: Ultra-robust catch-all regex for offsiteApplyUrl (from Code B)
#         for label, html in [("view", view_html), ("api", api_html)]:
#             if not html:
#                 continue
            
#             pattern = r'(?i)offsiteApplyUrl.*?[:=].*?(https?://[^"\'\\,&\s>]+)'
#             matches = re.findall(pattern, html)
#             for url in matches:
#                 try:
#                     url = unquote(url)
#                     url = url.replace('\\/', '/')
#                     if url and not self._is_linkedin_internal(url):
#                         print(f"      ✅ [catchall-{label}] {url[:80]}")
#                         return url
#                 except Exception:
#                     pass
        
#         # METHOD 1: Direct regex for offsiteApplyUrl (from Code B)
#         for label, html in [("view", view_html), ("api", api_html)]:
#             if not html:
#                 continue
            
#             pattern = r'"offsiteApplyUrl"\s*:\s*"(https?://[^"]+)"'
#             matches = re.findall(pattern, html)
#             for url in matches:
#                 if url and not self._is_linkedin_internal(url):
#                     print(f"      ✅ [offsiteApplyUrl-{label}] {url[:80]}")
#                     return url
            
#             # Escaped version
#             pattern = r'\\?"offsiteApplyUrl\\?"\s*:\s*\\?"(https?://[^"\\]+)\\"'
#             matches = re.findall(pattern, html)
#             for url in matches:
#                 url = url.replace('\\/', '/')
#                 if url and not self._is_linkedin_internal(url):
#                     print(f"      ✅ [offsiteApplyUrl-escaped-{label}] {url[:80]}")
#                     return url

#         # METHOD 2: util.py's extract_external_url_from_html (from Code A)
#         url = extract_external_url_from_html(api_html, job_id)
#         if url:
#             print(f"      ✅ [code#applyUrl-API] {url[:80]}")
#             return url

#         if view_html:
#             url = extract_external_url_from_html(view_html, job_id)
#             if url:
#                 print(f"      ✅ [code#applyUrl-view] {url[:80]}")
#                 return url

#         # METHOD 3: JSON-LD (from Code A)
#         for script in api_soup.find_all("script", {"type": "application/ld+json"}):
#             try:
#                 data = json.loads(script.string or "")
#                 for key in ("applyUrl", "applicationContact", "sameAs"):
#                     val = data.get(key)
#                     if val and isinstance(val, str) and val.startswith("http"):
#                         clean = unquote(val.replace("\\/", "/").replace("\\u002F", "/"))
#                         if not self._is_linkedin_internal(clean):
#                             print(f"      ✅ [JSON-LD] {clean[:80]}")
#                             return clean
#             except Exception:
#                 pass

#         # METHOD 4: Voyager OffsiteApply (from Code A)
#         voyager_pat = r'"companyApplyUrl"\s*:\s*"((?:[^"\\]|\\.)*)"'
#         for m in re.finditer(voyager_pat, api_html, re.IGNORECASE):
#             clean = unquote(m.group(1).replace("\\/", "/").replace("\\u002F", "/"))
#             if clean.startswith("http") and not self._is_linkedin_internal(clean):
#                 print(f"      ✅ [Voyager-companyApplyUrl] {clean[:80]}")
#                 return clean

#         # METHOD 5: applyUrl regex (from Code A)
#         apply_url_pat = r'"applyUrl"\s*:\s*"((?:[^"\\]|\\.)*)"'
#         for m in re.finditer(apply_url_pat, api_html, re.IGNORECASE):
#             clean = unquote(m.group(1).replace("\\/", "/").replace("\\u002F", "/"))
#             if clean.startswith("http") and not self._is_linkedin_internal(clean):
#                 print(f"      ✅ [applyUrl-API] {clean[:80]}")
#                 return clean

#         if view_html:
#             for m in re.finditer(apply_url_pat, view_html, re.IGNORECASE):
#                 clean = unquote(m.group(1).replace("\\/", "/").replace("\\u002F", "/"))
#                 if clean.startswith("http") and not self._is_linkedin_internal(clean):
#                     print(f"      ✅ [applyUrl-view] {clean[:80]}")
#                     return clean

#         # METHOD 6: externalApply endpoint (from Code B)
#         try:
#             ext_url = f"{self.base_url}/jobs/view/externalApply/{job_id}"
#             ext_response = self.session.get(ext_url, timeout=5, allow_redirects=True)
#             final_url = ext_response.url
#             if final_url and not self._is_linkedin_internal(final_url):
#                 print(f"      ✅ [externalApply-endpoint] {final_url[:80]}")
#                 return final_url
#         except Exception:
#             pass

#         # METHOD 7: Apply buttons (from Code B)
#         for label, html in [("view", view_html), ("api", api_html)]:
#             if not html:
#                 continue
#             soup = BeautifulSoup(html, 'html.parser')
#             for a in soup.find_all('a', href=True):
#                 href = a.get('href', '')
#                 if not href or self._is_linkedin_internal(href):
#                     continue
                
#                 link_text = a.get_text(strip=True).lower()
#                 link_classes = str(a.get('class', '')).lower()
#                 apply_indicators = ['apply', 'application', 'submit', 'external', 'offsite']
#                 context = link_text + ' ' + link_classes
                
#                 if any(ind in context for ind in apply_indicators):
#                     print(f"      ✅ [apply-button-{label}] {href[:80]}")
#                     return href

#         # METHOD 8: Redirect URLs (from Code B)
#         for label, html in [("view", view_html), ("api", api_html)]:
#             if not html:
#                 continue
#             redirect_patterns = [
#                 r'[?&]url=([^&"\'\s>]+)',
#                 r'[?&]redirectUrl=([^&"\'\s>]+)',
#                 r'[?&]applyUrl=([^&"\'\s>]+)',
#             ]
#             for pattern in redirect_patterns:
#                 matches = re.findall(pattern, html)
#                 for match in matches:
#                     try:
#                         url = unquote(match)
#                         if url and not self._is_linkedin_internal(url):
#                             print(f"      ✅ [redirect-{label}] {url[:80]}")
#                             return url
#                     except:
#                         pass

#         print(f"      ℹ️  No external link found for {job_id} — Easy Apply")
#         return None

#     # ─────────────────────────────────────────────────────────────────────────
#     # SKILLS AND REQUIREMENTS EXTRACTION FROM DESCRIPTION
#     # ─────────────────────────────────────────────────────────────────────────

#     def _extract_skills_from_description(self, description: str) -> List[str]:
#         """Extract skills from job description"""
#         if not description:
#             return []
        
#         skills = []
#         description_lower = description.lower()
        
#         # Common tech skills patterns
#         skill_patterns = [
#             r'\b(Python|Java|JavaScript|TypeScript|React|Angular|Vue|Node\.js|Django|Flask)\b',
#             r'\b(SQL|MongoDB|PostgreSQL|MySQL|Oracle|Redis|Elasticsearch)\b',
#             r'\b(AWS|Azure|GCP|Docker|Kubernetes|Terraform|Jenkins|CI/CD)\b',
#             r'\b(Machine Learning|AI|Deep Learning|NLP|Computer Vision|TensorFlow|PyTorch)\b',
#             r'\b(Agile|Scrum|Kanban|JIRA|Confluence|Git|GitHub|GitLab)\b',
#             r'\b(Leadership|Management|Communication|Teamwork|Problem Solving)\b',
#         ]
        
#         for pattern in skill_patterns:
#             matches = re.findall(pattern, description, re.IGNORECASE)
#             for match in matches:
#                 if match not in skills:
#                     skills.append(match)
        
#         return skills[:20]  # Limit to 20 skills

#     def _extract_requirements_from_description(self, description: str) -> List[str]:
#         """Extract requirements from job description"""
#         if not description:
#             return []
        
#         requirements = []
        
#         # Look for sections that indicate requirements
#         requirement_sections = re.findall(
#             r'(?:requirements|qualifications|what you\'ll need|we\'re looking for)[:\s]+(.*?)(?:\n\n|\n[A-Z]|$)',
#             description,
#             re.IGNORECASE | re.DOTALL
#         )
        
#         for section in requirement_sections:
#             # Extract bullet points
#             bullets = re.findall(r'[•\-*]\s*([^•\-*\n]+)', section)
#             if bullets:
#                 requirements.extend([b.strip() for b in bullets[:10]])
#             else:
#                 # Extract sentences as requirements
#                 sentences = re.findall(r'[A-Z][^.!?]*[.!?]', section)
#                 requirements.extend([s.strip() for s in sentences[:10]])
        
#         return requirements[:15]  # Limit to 15 requirements

#     # ─────────────────────────────────────────────────────────────────────────
#     # JOB DETAILS - COMPLETE EXTRACTION
#     # ─────────────────────────────────────────────────────────────────────────

#     def get_job_details(self, job_id: str, job_data: Dict = None) -> Optional[JobPost]:
#         job_view_url = f"{self.base_url}/jobs/view/{job_id}"
#         api_url = f"{self.base_url}/jobs-guest/jobs/api/jobPosting/{job_id}"

#         try:
#             # Fetch API page
#             self._throttle()
#             api_response = self.session.get(api_url, timeout=10)

#             if api_response.status_code == 429:
#                 print(f"Rate limited for job {job_id}")
#                 return None

#             if api_response.status_code != 200:
#                 print(f"Failed to fetch job API {job_id}: {api_response.status_code}")
#                 return None

#             api_html = api_response.text
#             api_soup = BeautifulSoup(api_html, "html.parser")

#             # Fetch view page
#             self._throttle()
#             view_response = self.session.get(job_view_url, timeout=10)
#             if view_response.status_code == 200:
#                 html = view_response.text
#                 soup = BeautifulSoup(html, "html.parser")
#             else:
#                 html = api_html
#                 soup = api_soup

#             # ─── EXTERNAL LINK EXTRACTION ───
#             external_url = self._extract_external_url_complete(
#                 api_soup, api_html, job_id, soup, html
#             )

#             if external_url and self._is_linkedin_internal(external_url):
#                 external_url = None

#             # ─── TITLE EXTRACTION ───
#             title = job_data.get("title") if job_data else ""
#             if not title:
#                 title_tag = soup.find("h1", class_="top-card-layout__title")
#                 if title_tag:
#                     title = title_tag.get_text(strip=True)
#                 else:
#                     title_tag = soup.find("h1", class_="jobs-top-card__job-title")
#                     if title_tag:
#                         title = title_tag.get_text(strip=True)
#                     else:
#                         title = "Unknown"

#             # ─── COMPANY EXTRACTION ───
#             company = job_data.get("company") if job_data else ""
#             if not company:
#                 company_tag = soup.find("a", class_="topcard__org-name-link")
#                 if company_tag:
#                     company = company_tag.get_text(strip=True)
#                 else:
#                     company_tag = soup.find("span", class_="jobs-top-card__company-name")
#                     if company_tag:
#                         company = company_tag.get_text(strip=True)
#                     else:
#                         company = "Unknown"

#             # ─── COMPANY LOGO EXTRACTION (COMPREHENSIVE) ───
#             company_logo = None
#             try:
#                 logo_selectors = [
#                     'img.artdeco-entity-image',
#                     'img.presence-entity__image',
#                     'img[data-delayed-url]',
#                     'img.ivm-view-attr__img--centered',
#                     'img.top-card-layout__entity-image',
#                     'img.jobs-top-card__company-logo',
#                     'img.job-details-jobs-unified-top-card__company-logo',
#                     'img[class*="company-logo"]',
#                     'img[class*="entity-image"]'
#                 ]
                
#                 for selector in logo_selectors:
#                     logo_img = soup.select_one(selector)
#                     if logo_img:
#                         for attr in ['src', 'data-delayed-url', 'data-src', 'data-source', 'content']:
#                             if logo_img.get(attr):
#                                 url = logo_img[attr]
#                                 if url and url.startswith('http') and 'ghost' not in url.lower() and 'blank' not in url.lower():
#                                     company_logo = url
#                                     break
#                         if company_logo:
#                             break
                
#                 if not company_logo:
#                     logo_meta = soup.find('meta', {'property': 'og:image'})
#                     if logo_meta and logo_meta.get('content'):
#                         company_logo = logo_meta.get('content')
                
#                 if not company_logo:
#                     for script in soup.find_all('script'):
#                         if script.string:
#                             logo_match = re.search(r'"logoUrl"\s*:\s*"(https?://[^"]+)"', script.string)
#                             if logo_match:
#                                 company_logo = logo_match.group(1)
#                                 break
#             except Exception:
#                 pass

#             # ─── DESCRIPTION EXTRACTION ───
#             description = ""
#             desc_selectors = [
#                 "div.show-more-less-html__markup",
#                 "div.description__text",
#                 "div.jobs-description__content",
#                 "div.job-description__content",
#                 "div.jobs-description",
#                 "div.job-description"
#             ]
#             for selector in desc_selectors:
#                 desc_tag = soup.select_one(selector)
#                 if desc_tag:
#                     description = desc_tag.get_text(strip=True)
#                     break

#             # ─── LOCATION EXTRACTION ───
#             location_str = job_data.get("location") if job_data else ""
#             if not location_str:
#                 location_tag = soup.find("span", class_="topcard__flavor--bullet")
#                 if location_tag:
#                     location_str = location_tag.get_text(strip=True)
#                 else:
#                     location_tag = soup.find("span", class_="jobs-top-card__location")
#                     if location_tag:
#                         location_str = location_tag.get_text(strip=True)
            
#             location = Location.from_string(location_str) if location_str else Location()

#             # ─── DATE POSTED EXTRACTION ───
#             date_posted = None
#             time_tag = soup.find("span", class_="posted-time-ago__text")
#             if not time_tag:
#                 time_tag = soup.find("span", class_="jobs-details-top-card__posted-date")
#             if not time_tag:
#                 time_tag = soup.find("time", class_="jobs-details-top-card__posted-date")
            
#             if time_tag:
#                 date_text = time_tag.get_text(strip=True)
#                 if date_text:
#                     date_posted = parse_relative_date(date_text)

#             # ─── JOB TYPE EXTRACTION (using util function) ───
#             job_type = parse_job_type(soup)

#             # ─── JOB LEVEL EXTRACTION (using util function) ───
#             job_level = parse_job_level(soup)

#             # ─── COMPANY INDUSTRY EXTRACTION (using util function) ───
#             company_industry = parse_company_industry(soup)

#             # ─── SALARY EXTRACTION (COMPREHENSIVE) ───
#             salary_min, salary_max, salary_text = None, None, None
#             compensation_currency = "USD"
#             compensation_interval = "yearly"
            
#             try:
#                 salary_selectors = [
#                     "span.job-details-salary-meta__salary",
#                     "span.jobs-details-salary-meta__salary",
#                     "div.job-details-salary-meta__salary",
#                     "div.jobs-details-salary-meta__salary",
#                     "span.salary",
#                     "div.salary",
#                     "[data-test-id='salary']"
#                 ]
                
#                 for selector in salary_selectors:
#                     salary_tag = soup.select_one(selector)
#                     if salary_tag:
#                         salary_text = salary_tag.get_text(strip=True)
#                         if salary_text:
#                             salary_range = re.findall(r'\$(\d+(?:,\d+)?(?:\.\d+)?)\s*[-–]\s*\$?(\d+(?:,\d+)?(?:\.\d+)?)', salary_text)
#                             if salary_range:
#                                 try:
#                                     salary_min = float(salary_range[0][0].replace(',', ''))
#                                     salary_max = float(salary_range[0][1].replace(',', ''))
#                                     if 'k' in salary_text.lower():
#                                         salary_min *= 1000
#                                         salary_max *= 1000
#                                     break
#                                 except:
#                                     pass
                            
#                             salary_single = re.findall(r'\$(\d+(?:,\d+)?(?:\.\d+)?)', salary_text)
#                             if salary_single and not salary_min:
#                                 try:
#                                     salary_min = float(salary_single[0].replace(',', ''))
#                                     salary_max = salary_min
#                                     if 'k' in salary_text.lower():
#                                         salary_min *= 1000
#                                         salary_max *= 1000
#                                     break
#                                 except:
#                                     pass
                
#                 if not salary_text and description:
#                     salary_min, salary_max, salary_text = parse_salary_from_text(description, html)
                
#                 if salary_text:
#                     if '€' in salary_text:
#                         compensation_currency = "EUR"
#                     elif '£' in salary_text:
#                         compensation_currency = "GBP"
#                     elif '₹' in salary_text:
#                         compensation_currency = "INR"
                    
#                     salary_lower = salary_text.lower()
#                     if 'hour' in salary_lower:
#                         compensation_interval = "hourly"
#                     elif 'day' in salary_lower:
#                         compensation_interval = "daily"
#                     elif 'week' in salary_lower:
#                         compensation_interval = "weekly"
#                     elif 'month' in salary_lower:
#                         compensation_interval = "monthly"
                        
#             except Exception:
#                 pass

#             # ─── EXPERIENCE EXTRACTION (COMPREHENSIVE) ───
#             experience = None
#             try:
#                 exp_selectors = [
#                     "span.job-details-salary-meta__experience",
#                     "span.jobs-details-salary-meta__experience",
#                     "span.experience",
#                     "div.experience",
#                     "[data-test-id='experience']"
#                 ]
                
#                 for selector in exp_selectors:
#                     exp_tag = soup.select_one(selector)
#                     if exp_tag:
#                         experience = exp_tag.get_text(strip=True)
#                         break
                
#                 if not experience and description:
#                     experience = parse_experience_from_text(description, html)
#             except Exception:
#                 pass

#             # ─── SKILLS EXTRACTION ───
#             skills = self._extract_skills_from_description(description)
#             skills_text = ", ".join(skills) if skills else None

#             # ─── REQUIREMENTS EXTRACTION ───
#             requirements = self._extract_requirements_from_description(description)
#             requirements_text = "\n".join(requirements) if requirements else None

#             # ─── REMOTE STATUS ───
#             is_remote = is_job_remote(title, description, location)

#             # ─── EASY APPLY STATUS ───
#             is_easy_apply = not external_url

#             # ─── COMPENSATION OBJECT ───
#             compensation = None
#             if salary_min or salary_max:
#                 compensation = Compensation(
#                     min_amount=salary_min,
#                     max_amount=salary_max,
#                     currency=compensation_currency,
#                     interval=compensation_interval,
#                 )

#             # ─── SEARCH KEYWORD ───
#             search_keyword = job_data.get("keyword") if job_data else None

#             # ─── CREATE JOB POST OBJECT ───
#             job = JobPost(
#                 job_id=job_id,
#                 title=title,
#                 company_name=company,
#                 company_logo=company_logo,
#                 location=location,
#                 description=description[:10000] if description else None,
#                 date_posted=date_posted,
#                 job_url=job_view_url,
#                 apply_url=external_url,
#                 job_url_direct=external_url,
#                 job_type=job_type,
#                 job_level=job_level,
#                 company_industry=company_industry,
#                 is_remote=is_remote,
#                 is_easy_apply=is_easy_apply,
#                 compensation=compensation,
#                 emails=extract_emails_from_text(description or ""),
#                 search_keyword=search_keyword,
#                 experience=experience,
#                 salary_text=salary_text,
#             )

#             # Add custom attributes for skills and requirements
#             job.skills = skills_text
#             job.requirements = requirements_text

#             self._handle_success()
            
#             # Debug output
#             if job.apply_url:
#                 print(f"      📊 Extracted: Logo={bool(company_logo)}, Salary={salary_text}, "
#                       f"JobType={job_type}, Level={job_level}, Industry={company_industry}, "
#                       f"Experience={experience}, Skills={len(skills)}, Requirements={len(requirements)}")
            
#             return job

#         except Exception as e:
#             print(f"❌ Error fetching job {job_id}: {e}")
#             self._handle_error()
#             return None

#     # ─────────────────────────────────────────────────────────────────────────
#     # SEARCH
#     # ─────────────────────────────────────────────────────────────────────────

#     def search_all_jobs(self, keyword: str, location: str = "United States",
#                         hours_old: int = 24) -> List[Dict]:
#         jobs = []
#         seen_job_ids = set()
#         start = 0
#         page = 1
#         max_pages = 200
#         empty_page_retries = 2
#         consecutive_empty = 0

#         print(f"\n   📍 Searching all pages for: {keyword}")

#         while page <= max_pages:
#             params = {
#                 "keywords": keyword,
#                 "location": location,
#                 "distance": "100",
#                 "f_TPR": f"r{hours_old * 3600}",
#                 "start": start,
#                 "refresh": True,
#             }
#             url = f"{self.base_url}/jobs-guest/jobs/api/seeMoreJobPostings/search"

#             try:
#                 self._throttle()
#                 response = self.session.get(url, params=params, timeout=15)

#                 if response.status_code == 429:
#                     wait = random.uniform(10, 20)
#                     print(f"   ⚠️ Rate limited. Waiting {wait:.0f}s...")
#                     time.sleep(wait)
#                     continue

#                 if response.status_code != 200:
#                     print(f"   ❌ Search failed: HTTP {response.status_code}")
#                     self._handle_error()
#                     break

#                 soup = BeautifulSoup(response.text, "html.parser")
#                 job_cards = soup.find_all("div", class_="base-card")

#                 if not job_cards:
#                     consecutive_empty += 1
#                     if consecutive_empty <= empty_page_retries:
#                         print(f"   ⚠️ Empty page at start={start} ({consecutive_empty}/{empty_page_retries}), retrying...")
#                         time.sleep(random.uniform(3, 6))
#                         continue
#                     else:
#                         print(f"   ✅ End of results after {len(jobs)} jobs")
#                         break
#                 consecutive_empty = 0

#                 page_jobs = 0
#                 for card in job_cards:
#                     try:
#                         link_tag = card.find("a", class_="base-card__full-link")
#                         if not link_tag or not link_tag.get("href"):
#                             continue
#                         href = link_tag["href"]
#                         job_id = href.split("?")[0].split("-")[-1]
#                         if job_id in seen_job_ids:
#                             continue
#                         seen_job_ids.add(job_id)

#                         title_tag = card.find("h3", class_="base-search-card__title")
#                         title = title_tag.get_text(strip=True) if title_tag else "Unknown"
#                         company_tag = card.find("h4", class_="base-search-card__subtitle")
#                         company = company_tag.get_text(strip=True) if company_tag else "Unknown"
#                         location_tag = card.find("span", class_="job-search-card__location")
#                         location_str = location_tag.get_text(strip=True) if location_tag else ""

#                         jobs.append({
#                             "job_id": job_id,
#                             "title": title,
#                             "company": company,
#                             "location": location_str,
#                             "link": f"{self.base_url}/jobs/view/{job_id}",
#                         })
#                         page_jobs += 1
#                     except Exception as e:
#                         print(f"   ⚠️ Card parse error: {e}")
#                         continue

#                 print(f"   📄 Page {page} (start={start}): {page_jobs} jobs | total={len(jobs)}")
#                 start += 25
#                 page += 1
#                 self._handle_success()
#                 time.sleep(random.uniform(1.0, 2.5))

#             except Exception as e:
#                 print(f"   ❌ Search error page {page}: {e}")
#                 self._handle_error()
#                 time.sleep(5)
#                 break

#         print(f"   📊 Total unique jobs for '{keyword}': {len(jobs)}")
#         return jobs

#     # ─────────────────────────────────────────────────────────────────────────
#     # BATCH SCRAPE - REAL-TIME STORAGE
#     # ─────────────────────────────────────────────────────────────────────────

#     def scrape_all_jobs_batch(self, keywords: List[str],
#                               location: str = "United States",
#                               max_workers: int = 5,
#                               save_to_db: bool = True) -> List[JobPost]:
#         """
#         Scrape ALL jobs posted in last 24 hours for multiple keywords in parallel.
#         Saves each job to database IMMEDIATELY after it's fetched.
#         """
#         all_jobs = []
#         seen_global_ids = set()
#         total_keywords = len(keywords)
#         actual_workers = min(max_workers, 5)
        
#         grand_external = 0
#         grand_salary = 0
#         grand_exp = 0
#         saved_count = 0
#         duplicate_count = 0

#         if save_to_db and not (self.db and self.db.initialized):
#             print("\n⚠️ Supabase not initialised — DB saves will be skipped")
#             save_to_db = False

#         for idx, keyword in enumerate(keywords):
#             print(f"\n{'='*60}")
#             print(f"🔍 [{idx+1}/{total_keywords}] Keyword: {keyword}")
#             print(f"{'='*60}")

#             raw_jobs = self.search_all_jobs(keyword, location, hours_old=24)

#             keyword_results = []
#             for job in raw_jobs:
#                 if job["job_id"] not in seen_global_ids:
#                     seen_global_ids.add(job["job_id"])
#                     job["keyword"] = keyword
#                     keyword_results.append(job)

#             print(f"   📋 {len(keyword_results)} unique new jobs to fetch for '{keyword}'")

#             if not keyword_results:
#                 if idx < total_keywords - 1:
#                     delay = random.uniform(3, 6)
#                     print(f"   ⏱️  Waiting {delay:.1f}s...")
#                     time.sleep(delay)
#                 continue

#             print(f"   🔗 Fetching details and saving in REAL-TIME ({actual_workers} workers)...")

#             keyword_jobs = []
#             external_count = 0
#             salary_count = 0
#             exp_count = 0
#             completed = 0
#             kw_total = len(keyword_results)
#             keyword_saved = 0

#             with ThreadPoolExecutor(max_workers=actual_workers) as executor:
#                 future_to_job = {
#                     executor.submit(self.get_job_details, j["job_id"], j): j
#                     for j in keyword_results
#                 }
                
#                 for future in as_completed(future_to_job):
#                     completed += 1
#                     src_job = future_to_job[future]

#                     if completed % 25 == 0 or completed == 1 or completed == kw_total:
#                         print(f"   Progress: {completed}/{kw_total} ({completed/kw_total*100:.0f}%) | "
#                               f"external={external_count} | saved={saved_count}")

#                     try:
#                         job_post = future.result(timeout=15)
#                         if job_post:
#                             keyword_jobs.append(job_post)
#                             all_jobs.append(job_post)
                            
#                             if job_post.apply_url:
#                                 external_count += 1
#                             if job_post.compensation and job_post.compensation.min_amount:
#                                 salary_count += 1
#                             if job_post.experience:
#                                 exp_count += 1
                            
#                             if save_to_db and self.db and self.db.initialized:
#                                 job_dict = job_post.to_supabase_dict()
#                                 result = self.db.save_job(job_dict)
#                                 if result:
#                                     saved_count += 1
#                                     keyword_saved += 1
#                                     if job_post.apply_url:
#                                         print(f"      🚀 JOB {job_post.job_id} SAVED TO DB")
#                                 else:
#                                     duplicate_count += 1
                                
#                     except Exception as e:
#                         print(f"   ✗ {src_job['job_id']}: {e}")

#             grand_external += external_count
#             grand_salary += salary_count
#             grand_exp += exp_count

#             print(f"   ✅ '{keyword}': {len(keyword_jobs)} jobs, {external_count} external links, "
#                   f"{keyword_saved} saved to DB")

#             if idx < total_keywords - 1:
#                 delay = random.uniform(3, 6)
#                 print(f"   ⏱️  Waiting {delay:.1f}s before next keyword...")
#                 time.sleep(delay)

#         print(f"\n{'='*60}")
#         print("✅ SCRAPE COMPLETE")
#         print(f"{'='*60}")
#         if all_jobs:
#             pct = grand_external / len(all_jobs) * 100 if len(all_jobs) > 0 else 0
#             print(f"📊 Total jobs processed : {len(all_jobs)}")
#             print(f"🔗 External links found : {grand_external} ({pct:.1f}%)")
#             print(f"💰 Jobs with salary info: {grand_salary}")
#             print(f"📝 Jobs with experience : {grand_exp}")
#             if save_to_db:
#                 print(f"💾 IMMEDIATE SAVES      : {saved_count} new jobs saved")
#                 print(f"🔄 Duplicates skipped   : {duplicate_count}")

#         return all_jobs

#     def save_to_csv(self, jobs: List[JobPost], filename: str = None):
#         """Save jobs to CSV file with enhanced fields"""
#         if not filename:
#             filename = f"linkedin_jobs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

#         import csv
#         with open(filename, 'w', newline='', encoding='utf-8') as f:
#             writer = csv.writer(f)
#             writer.writerow([
#                 'Job ID', 'Title', 'Company', 'Company Logo', 'Location',
#                 'Date Posted', 'Job URL', 'External Apply URL', 'Is Remote',
#                 'Is Easy Apply', 'Job Type', 'Job Level', 'Industry',
#                 'Search Keyword', 'Salary Min', 'Salary Max', 'Salary Text',
#                 'Experience Required', 'Skills', 'Requirements', 'Description Preview'
#             ])

#             for job in jobs:
#                 writer.writerow([
#                     job.job_id, job.title, job.company_name,
#                     job.company_logo or "",
#                     job.location.display_location(),
#                     job.date_posted, job.job_url, job.apply_url or "",
#                     job.is_remote, job.is_easy_apply,
#                     ", ".join(jt.value for jt in job.job_type) if job.job_type else "",
#                     job.job_level or "", job.company_industry or "",
#                     job.search_keyword or "",
#                     job.compensation.min_amount if job.compensation else "",
#                     job.compensation.max_amount if job.compensation else "",
#                     getattr(job, 'salary_text', '') or "",
#                     getattr(job, 'experience', '') or "",
#                     getattr(job, 'skills', '') or "",
#                     getattr(job, 'requirements', '') or "",
#                     (job.description or "")[:500],
#                 ])
#         print(f"💾 Saved {len(jobs)} jobs to {filename}")















































































# """
# LinkedIn Scraper — Merged Version
# ─────────────────────────────────
# WHAT WAS MERGED:
#   • External URL extraction  → taken from Code B (_fetch_external_url, 6 methods)
#   • Field extraction logic   → taken from Code A (delegates to util.py helpers)
#   • Auth / cookie support    → taken from Code B (LINKEDIN_COOKIE env var)
#   • Graceful API fallback    → taken from Code B (api_html="" on failure)
#   • Duplicate tracking       → taken from Code B (duplicate_count in summary)

# WHAT WAS NOT CHANGED:
#   • search_all_jobs()         — untouched (identical in both)
#   • scrape_all_jobs_batch()   — untouched structure, only stats vars aligned
#   • save_to_csv()             — untouched (identical in both)
#   • Rate limiting / throttle  — untouched
#   • Threading / DB logic      — untouched
#   • All util.py delegations   — kept exactly as in Code A

# THREAD-SAFETY NOTE (discovered during research):
#   requests.Session is NOT thread-safe when shared across threads.
#   Both original codes shared one session. Fixed here via threading.local()
#   so each worker thread gets its own session automatically.
# """

# import os
# import time
# import random
# import re
# import json
# import threading
# from datetime import datetime
# from typing import Optional, List, Dict
# from urllib.parse import urlparse, unquote
# from concurrent.futures import ThreadPoolExecutor, as_completed

# import requests
# from bs4 import BeautifulSoup

# from .models import JobPost, Location, Compensation, JobType
# from .constant import headers
# from .util import (
#     parse_job_type,
#     parse_job_level,
#     parse_company_industry,
#     is_job_remote,
#     extract_external_url_from_html,
#     extract_emails_from_text,
#     parse_relative_date,
#     create_session,
#     parse_salary_from_text,
#     parse_experience_from_text,
#     extract_company_logo,
# )
# from .database import SupabaseManager


# # ─────────────────────────────────────────────────────────────────────────────
# # Module-level helper (from Code B — wired up properly here)
# # ─────────────────────────────────────────────────────────────────────────────

# def _is_external(url: str) -> bool:
#     """True only for real third-party URLs that are not LinkedIn."""
#     if not url or not url.startswith("http"):
#         return False
#     try:
#         host = urlparse(url).netloc.lower()
#     except Exception:
#         return False
#     return (
#         "linkedin.com" not in host
#         and "lnkd.in" not in host
#         and host != ""
#     )


# # ─────────────────────────────────────────────────────────────────────────────
# # Main Scraper Class
# # ─────────────────────────────────────────────────────────────────────────────

# class LinkedInScraper:
#     """
#     High-performance LinkedIn scraper.
#     External URL extraction  : Code B's 6-method _fetch_external_url()
#     Field extraction logic   : Code A's util.py-delegated get_job_details()
#     """

#     def __init__(self, proxies=None, ca_cert=None, user_agent=None, use_database=True):
#         self.base_url = "https://www.linkedin.com"

#         # ── Auth (Code B) ─────────────────────────────────────────────────
#         cookie = os.getenv("LINKEDIN_COOKIE")
#         self.session = create_session(proxies=proxies, ca_cert=ca_cert, cookie=cookie)
#         self.session.headers.update(headers)

#         # ── Thread-local sessions (fix: requests.Session is not thread-safe)
#         # Each worker thread will have its own isolated session clone.
#         self._thread_local = threading.local()
#         self._proxies = proxies
#         self._ca_cert = ca_cert
#         self._cookie = cookie

#         # ── Rate limiting ─────────────────────────────────────────────────
#         self.min_delay = 1.0
#         self.max_delay = 3.0
#         self.current_delay = self.min_delay
#         self.consecutive_errors = 0
#         self.max_consecutive_errors = 3
#         self.error_backoff = 1.5

#         # ── Thread safety for shared state ────────────────────────────────
#         self._lock = threading.Lock()
#         self._extracted_links = set()

#         # ── Database ──────────────────────────────────────────────────────
#         self.use_database = use_database
#         self.db = SupabaseManager() if use_database else None
#         if use_database:
#             self.db.initialize()

#         self.saved_jobs_count = 0

#     # ─────────────────────────────────────────────────────────────────────────
#     # Per-thread session (thread-safety fix)
#     # ─────────────────────────────────────────────────────────────────────────

#     def _get_thread_session(self) -> requests.Session:
#         """
#         Return a requests.Session bound to the current thread.
#         Creates one if it doesn't exist yet for this thread.
#         This avoids the known thread-unsafety of sharing one Session.
#         """
#         if not hasattr(self._thread_local, "session"):
#             sess = create_session(proxies=self._proxies, ca_cert=self._ca_cert,
#                                   cookie=self._cookie)
#             sess.headers.update(headers)
#             self._thread_local.session = sess
#         return self._thread_local.session

#     # ─────────────────────────────────────────────────────────────────────────
#     # Rate limiting helpers  (unchanged from both A and B)
#     # ─────────────────────────────────────────────────────────────────────────

#     def _throttle(self):
#         """Apply throttling based on current delay."""
#         with self._lock:
#             time.sleep(self.current_delay + random.uniform(0, 0.5))

#     def _handle_error(self):
#         """Increase delay on errors."""
#         with self._lock:
#             self.consecutive_errors += 1
#             if self.consecutive_errors >= self.max_consecutive_errors:
#                 self.current_delay = min(
#                     self.current_delay * self.error_backoff, self.max_delay
#                 )
#                 self.consecutive_errors = 0
#                 print(f"⚠️ Increasing delay to {self.current_delay:.1f}s due to errors")

#     def _handle_success(self):
#         """Gradually decrease delay on success."""
#         with self._lock:
#             self.consecutive_errors = 0
#             if self.current_delay > self.min_delay:
#                 self.current_delay = max(
#                     self.current_delay / self.error_backoff, self.min_delay
#                 )

#     # ─────────────────────────────────────────────────────────────────────────
#     # Internal URL checker  (from Code A — used throughout)
#     # ─────────────────────────────────────────────────────────────────────────

#     def _is_linkedin_internal(self, url: str) -> bool:
#         """Check if URL is a LinkedIn internal page."""
#         if not url:
#             return True
#         url_lower = url.lower()
#         if "linkedin.com" in url_lower:
#             return True
#         internal_patterns = [
#             "signup", "login", "auth", "checkpoint",
#             "cold-join", "registration", "sign-in",
#         ]
#         for pattern in internal_patterns:
#             if pattern in url_lower:
#                 return True
#         return False

#     # ─────────────────────────────────────────────────────────────────────────
#     # SEARCH  (unchanged — identical in both A and B)
#     # ─────────────────────────────────────────────────────────────────────────

#     def search_all_jobs(self, keyword: str, location: str = "United States",
#                         hours_old: int = 24) -> List[Dict]:
#         """
#         Search for ALL jobs posted in the last N hours for a keyword.
#         Continues pagination until LinkedIn returns an empty page.
#         """
#         jobs = []
#         seen_job_ids = set()
#         start = 0
#         page = 1
#         max_pages = 200
#         empty_page_retries = 2
#         consecutive_empty = 0

#         print(f"\n   📍 Searching all pages for: {keyword}")

#         while page <= max_pages:
#             params = {
#                 "keywords": keyword,
#                 "location": location,
#                 "distance": "100",
#                 "f_TPR": f"r{hours_old * 3600}",
#                 "start": start,
#                 "refresh": True,
#             }
#             url = f"{self.base_url}/jobs-guest/jobs/api/seeMoreJobPostings/search"

#             try:
#                 self._throttle()
#                 response = self.session.get(url, params=params, timeout=15)

#                 if response.status_code == 429:
#                     wait = random.uniform(10, 20)
#                     print(f"   ⚠️ Rate limited (429). Waiting {wait:.0f}s before retry...")
#                     time.sleep(wait)
#                     continue

#                 if response.status_code != 200:
#                     print(f"   ❌ Search failed: HTTP {response.status_code}")
#                     self._handle_error()
#                     break

#                 soup = BeautifulSoup(response.text, "html.parser")
#                 job_cards = soup.find_all("div", class_="base-card")

#                 if not job_cards:
#                     consecutive_empty += 1
#                     if consecutive_empty <= empty_page_retries:
#                         print(f"   ⚠️ Empty page at start={start} "
#                               f"(attempt {consecutive_empty}/{empty_page_retries}), retrying...")
#                         time.sleep(random.uniform(3, 6))
#                         continue
#                     else:
#                         print(f"   ✅ Confirmed end of results after {len(jobs)} jobs "
#                               f"(empty response at start={start})")
#                         break
#                 consecutive_empty = 0

#                 page_jobs = 0
#                 for card in job_cards:
#                     try:
#                         link_tag = card.find("a", class_="base-card__full-link")
#                         if not link_tag or not link_tag.get("href"):
#                             continue

#                         href = link_tag["href"]
#                         job_id = href.split("?")[0].split("-")[-1]

#                         if job_id in seen_job_ids:
#                             continue
#                         seen_job_ids.add(job_id)

#                         title_tag = card.find("h3", class_="base-search-card__title")
#                         title = title_tag.get_text(strip=True) if title_tag else "Unknown"

#                         company_tag = card.find("h4", class_="base-search-card__subtitle")
#                         company = company_tag.get_text(strip=True) if company_tag else "Unknown"

#                         location_tag = card.find("span", class_="job-search-card__location")
#                         location_str = location_tag.get_text(strip=True) if location_tag else ""

#                         jobs.append({
#                             "job_id": job_id,
#                             "title": title,
#                             "company": company,
#                             "location": location_str,
#                             "link": f"{self.base_url}/jobs/view/{job_id}",
#                         })
#                         page_jobs += 1

#                     except Exception as e:
#                         print(f"   ⚠️ Error parsing job card: {e}")
#                         continue

#                 print(f"   📄 Page {page} (start={start}): {page_jobs} new jobs "
#                       f"| Running total: {len(jobs)}")

#                 start += 25
#                 page += 1
#                 self._handle_success()
#                 time.sleep(random.uniform(1.0, 2.5))

#             except Exception as e:
#                 print(f"   ❌ Search error on page {page}: {e}")
#                 self._handle_error()
#                 time.sleep(5)
#                 break

#         if page > max_pages:
#             print(f"   ⚠️ Reached safety limit of {max_pages} pages for '{keyword}'")

#         print(f"   📊 Total unique jobs found for '{keyword}': {len(jobs)}")
#         return jobs

#     # ─────────────────────────────────────────────────────────────────────────
#     # EXTERNAL URL EXTRACTION  — taken fully from Code B
#     # ─────────────────────────────────────────────────────────────────────────

#     def _fetch_external_url(self, job_id: str,
#                             api_html: str,
#                             view_html: str) -> Optional[str]:
#         """
#         Extract the external apply URL using Code B's 6-method cascade.
#         Methods are tried in order; first valid external URL wins.
#         """
#         sess = self._get_thread_session()

#         # METHOD 0: Ultra-robust catch-all regex for offsiteApplyUrl
#         # Captures any https://... closely following offsiteApplyUrl regardless
#         # of quote style or backslash escaping.
#         for label, html in [("view", view_html), ("api", api_html)]:
#             if not html:
#                 continue
#             pattern = r'(?i)offsiteApplyUrl.*?[:=].*?(https?://[^"\'\\,&\s>]+)'
#             matches = re.findall(pattern, html)
#             for url in matches:
#                 try:
#                     url = unquote(url).replace("\\/", "/")
#                     if url and not self._is_linkedin_internal(url):
#                         print(f"      ✅ [catchall-{label}] {url[:80]}")
#                         return url
#                 except Exception:
#                     pass

#         # METHOD 1: Direct regex for offsiteApplyUrl (strict + escaped variants)
#         for label, html in [("view", view_html), ("api", api_html)]:
#             if not html:
#                 continue
#             # Strict JSON key
#             for url in re.findall(r'"offsiteApplyUrl"\s*:\s*"(https?://[^"]+)"', html):
#                 if not self._is_linkedin_internal(url):
#                     print(f"      ✅ [direct-{label}] {url[:80]}")
#                     return url
#             # Escaped variant
#             for url in re.findall(
#                 r'\\?"offsiteApplyUrl\\?"\s*:\s*\\?"(https?://[^"\\]+)\\"', html
#             ):
#                 url = url.replace("\\/", "/")
#                 if not self._is_linkedin_internal(url):
#                     print(f"      ✅ [direct-escaped-{label}] {url[:80]}")
#                     return url

#         # METHOD 2: Script tag scanning for applyUrl variants
#         for label, html in [("view", view_html), ("api", api_html)]:
#             if not html:
#                 continue
#             soup = BeautifulSoup(html, "html.parser")
#             patterns = [
#                 r'"offsiteApplyUrl"\s*:\s*"([^"]+)"',
#                 r'"applyUrl"\s*:\s*"([^"]+)"',
#                 r'"externalApplyUrl"\s*:\s*"([^"]+)"',
#             ]
#             for script in soup.find_all("script"):
#                 if not script.string:
#                     continue
#                 for pat in patterns:
#                     for url in re.findall(pat, script.string):
#                         url = url.replace("\\/", "/")
#                         if url and not self._is_linkedin_internal(url):
#                             print(f"      ✅ [script-{label}] {url[:80]}")
#                             return url

#         # METHOD 3: Hit the externalApply endpoint directly and follow redirects
#         try:
#             ext_url = f"{self.base_url}/jobs/view/externalApply/{job_id}"
#             ext_response = sess.get(ext_url, timeout=5, allow_redirects=True)
#             final_url = ext_response.url
#             if final_url and not self._is_linkedin_internal(final_url):
#                 print(f"      ✅ [endpoint] {final_url[:80]}")
#                 return final_url
#         except Exception:
#             pass

#         # METHOD 4: Apply-button link scanning with context heuristics
#         for label, html in [("view", view_html), ("api", api_html)]:
#             if not html:
#                 continue
#             soup = BeautifulSoup(html, "html.parser")
#             for a in soup.find_all("a", href=True):
#                 href = a.get("href", "")
#                 if not href or self._is_linkedin_internal(href):
#                     continue
#                 context = (
#                     a.get_text(strip=True).lower()
#                     + " " + str(a.get("class", "")).lower()
#                     + " " + str(a.get("id", "")).lower()
#                 )
#                 apply_indicators = ["apply", "application", "submit", "external", "offsite"]
#                 if any(ind in context for ind in apply_indicators):
#                     print(f"      ✅ [button-{label}] {href[:80]}")
#                     return href

#         # METHOD 5: Redirect URL query parameter extraction
#         for label, html in [("view", view_html), ("api", api_html)]:
#             if not html:
#                 continue
#             redirect_patterns = [
#                 r"[?&]url=([^&\"'\s>]+)",
#                 r"[?&]redirectUrl=([^&\"'\s>]+)",
#                 r"[?&]applyUrl=([^&\"'\s>]+)",
#             ]
#             for pat in redirect_patterns:
#                 for match in re.findall(pat, html):
#                     try:
#                         url = unquote(match)
#                         if url and not self._is_linkedin_internal(url):
#                             print(f"      ✅ [redirect-{label}] {url[:80]}")
#                             return url
#                     except Exception:
#                         pass

#         print(f"      ℹ️  No external URL found for {job_id} — Easy Apply")
#         return None

#     # ─────────────────────────────────────────────────────────────────────────
#     # JOB DETAILS  — Code B's fetch strategy + Code A's field extraction
#     # ─────────────────────────────────────────────────────────────────────────

#     def get_job_details(self, job_id: str, job_data: Dict = None) -> Optional[JobPost]:
#         """
#         Fetch detailed job information.

#         HTTP fetching  : Code B (graceful fallback if guest API fails)
#         External URL   : Code B's _fetch_external_url() (6-method cascade)
#         Field parsing  : Code A (delegates to util.py helpers)
#         """
#         job_view_url = f"{self.base_url}/jobs/view/{job_id}"
#         api_url = f"{self.base_url}/jobs-guest/jobs/api/jobPosting/{job_id}"
#         sess = self._get_thread_session()

#         try:
#             # ── Fetch API page (Code B: graceful fallback on failure) ──────
#             self._throttle()
#             api_resp = sess.get(api_url, timeout=10)

#             if api_resp.status_code == 429:
#                 print(f"      ℹ️ Guest API rate limited for {job_id}, falling back...")
#                 api_html = ""
#             elif api_resp.status_code != 200:
#                 print(f"      ℹ️ Guest API fetch failed {job_id}: "
#                       f"{api_resp.status_code}, falling back...")
#                 api_html = ""
#             else:
#                 api_html = api_resp.text

#             # ── Fetch view page ───────────────────────────────────────────
#             self._throttle()
#             view_resp = sess.get(job_view_url, timeout=10)
#             view_html = view_resp.text if view_resp.status_code == 200 else ""

#             # Use whichever page has content for BeautifulSoup parsing
#             soup = BeautifulSoup(view_html or api_html, "html.parser")

#             # ── External URL — Code B's 6-method cascade ──────────────────
#             external_url = self._fetch_external_url(job_id, api_html, view_html)

#             # Final guard: discard if it somehow resolved to a LinkedIn URL
#             if external_url and self._is_linkedin_internal(external_url):
#                 external_url = None

#             # ─────────────────────────────────────────────────────────────
#             # FIELD EXTRACTION — Code A logic (util.py delegation)
#             # ─────────────────────────────────────────────────────────────

#             # Title
#             title = job_data.get("title") if job_data else ""
#             if not title:
#                 title_tag = soup.find("h1", class_="top-card-layout__title")
#                 title = title_tag.get_text(strip=True) if title_tag else "Unknown"

#             # Company
#             company = job_data.get("company") if job_data else ""
#             if not company:
#                 company_tag = soup.find("a", class_="topcard__org-name-link")
#                 company = company_tag.get_text(strip=True) if company_tag else "Unknown"

#             # Company logo — delegates to util.py
#             # Both api_html and view_html passed so util searches JSON blobs
#             # on both pages for logoUrl / company-logo CDN URLs.
#             company_logo = extract_company_logo(soup, api_html=api_html, view_html=view_html)

#             # Description
#             description = ""
#             desc_selectors = [
#                 "div.show-more-less-html__markup",
#                 "div.description__text",
#                 "div.jobs-description__content",
#             ]
#             for selector in desc_selectors:
#                 desc_tag = soup.select_one(selector)
#                 if desc_tag:
#                     description = desc_tag.get_text(strip=True)
#                     break

#             # Location
#             location_str = job_data.get("location") if job_data else ""
#             if not location_str:
#                 location_tag = soup.find("span", class_="topcard__flavor--bullet")
#                 if location_tag:
#                     location_str = location_tag.get_text(strip=True)
#             location = Location.from_string(location_str) if location_str else Location()

#             # Date posted
#             date_posted = None
#             time_tag = soup.find("span", class_="posted-time-ago__text")
#             if time_tag:
#                 date_posted = parse_relative_date(time_tag.get_text(strip=True))

#             # Job type — Code A: delegates to util.py
#             job_type = parse_job_type(soup)

#             # Job level — Code A: delegates to util.py
#             job_level = parse_job_level(soup)

#             # Company industry — Code A: delegates to util.py
#             company_industry = parse_company_industry(soup)

#             # Salary — Code A: delegates to util.py
#             salary_min, salary_max, salary_text = parse_salary_from_text(
#                 description, view_html or api_html
#             )

#             # Experience — Code A: delegates to util.py
#             experience = parse_experience_from_text(description, view_html or api_html)

#             # Remote check — Code A: delegates to util.py
#             is_remote = is_job_remote(title, description, location)

#             # Easy apply flag
#             is_easy_apply = not external_url

#             # Compensation object
#             compensation = None
#             if salary_min or salary_max:
#                 compensation = Compensation(
#                     min_amount=salary_min,
#                     max_amount=salary_max,
#                     currency="USD",
#                     interval="yearly",
#                 )

#             # Search keyword
#             search_keyword = job_data.get("keyword") if job_data else None

#             # ── Build JobPost ─────────────────────────────────────────────
#             job = JobPost(
#                 job_id=job_id,
#                 title=title,
#                 company_name=company,
#                 company_logo=company_logo,
#                 location=location,
#                 description=description[:10000] if description else None,
#                 date_posted=date_posted,
#                 job_url=job_view_url,
#                 apply_url=external_url,
#                 job_url_direct=external_url,
#                 job_type=job_type,
#                 job_level=job_level,
#                 company_industry=company_industry,
#                 is_remote=is_remote,
#                 is_easy_apply=is_easy_apply,
#                 compensation=compensation,
#                 emails=extract_emails_from_text(description or ""),
#                 search_keyword=search_keyword,
#                 experience=experience,
#                 salary_text=salary_text,
#             )

#             self._handle_success()

#             if job.apply_url:
#                 print(
#                     f"      📊 Extracted: Logo={bool(company_logo)}, "
#                     f"Salary={salary_text}, JobType={job_type}, "
#                     f"Level={job_level}, Experience={experience}"
#                 )

#             return job

#         except Exception as e:
#             print(f"❌ Error fetching job {job_id}: {e}")
#             self._handle_error()
#             return None

#     # ─────────────────────────────────────────────────────────────────────────
#     # BATCH SCRAPE  (structure from Code B + stats alignment)
#     # ─────────────────────────────────────────────────────────────────────────

#     def scrape_all_jobs_batch(self, keywords: List[str],
#                               location: str = "United States",
#                               max_workers: int = 5,
#                               save_to_db: bool = True) -> List[JobPost]:
#         """
#         Scrape ALL jobs posted in last 24 hours for multiple keywords in parallel.
#         Saves each job to database IMMEDIATELY after it's fetched (real-time storage).
#         """
#         all_jobs = []
#         seen_global_ids = set()
#         total_keywords = len(keywords)
#         actual_workers = min(max_workers, 5)

#         grand_external = 0
#         grand_salary = 0
#         grand_exp = 0
#         saved_count = 0
#         duplicate_count = 0

#         if save_to_db and not (self.db and self.db.initialized):
#             print("\n⚠️ Supabase not initialised — DB saves will be skipped")
#             save_to_db = False

#         for idx, keyword in enumerate(keywords):
#             print(f"\n{'='*60}")
#             print(f"🔍 [{idx+1}/{total_keywords}] Keyword: {keyword}")
#             print(f"{'='*60}")

#             raw_jobs = self.search_all_jobs(keyword, location, hours_old=24)

#             keyword_results = []
#             for job in raw_jobs:
#                 if job["job_id"] not in seen_global_ids:
#                     seen_global_ids.add(job["job_id"])
#                     job["keyword"] = keyword
#                     keyword_results.append(job)

#             print(f"   📋 {len(keyword_results)} unique new jobs to fetch for '{keyword}'")

#             if not keyword_results:
#                 if idx < total_keywords - 1:
#                     delay = random.uniform(3, 6)
#                     print(f"   ⏱️  Waiting {delay:.1f}s before next keyword...")
#                     time.sleep(delay)
#                 continue

#             print(f"   🔗 Fetching details and saving in REAL-TIME "
#                   f"({actual_workers} workers)...")

#             keyword_jobs = []
#             external_count = 0
#             salary_count = 0
#             exp_count = 0
#             completed = 0
#             kw_total = len(keyword_results)
#             keyword_saved = 0

#             with ThreadPoolExecutor(max_workers=actual_workers) as executor:
#                 future_to_job = {
#                     executor.submit(self.get_job_details, j["job_id"], j): j
#                     for j in keyword_results
#                 }

#                 for future in as_completed(future_to_job):
#                     completed += 1
#                     src_job = future_to_job[future]

#                     if completed % 25 == 0 or completed == 1 or completed == kw_total:
#                         print(
#                             f"   Progress: {completed}/{kw_total} "
#                             f"({completed / kw_total * 100:.0f}%) | "
#                             f"external={external_count} | saved={saved_count}"
#                         )

#                     try:
#                         job_post = future.result(timeout=15)
#                         if job_post:
#                             keyword_jobs.append(job_post)
#                             all_jobs.append(job_post)

#                             if job_post.apply_url:
#                                 external_count += 1
#                             if job_post.compensation and job_post.compensation.min_amount:
#                                 salary_count += 1
#                             if job_post.experience:
#                                 exp_count += 1

#                             # ─── IMMEDIATE DATABASE SAVE ──────────────────
#                             if save_to_db and self.db and self.db.initialized:
#                                 job_dict = job_post.to_supabase_dict()
#                                 result = self.db.save_job(job_dict)
#                                 if result:
#                                     saved_count += 1
#                                     keyword_saved += 1
#                                     if job_post.apply_url:
#                                         print(
#                                             f"      🚀 JOB {job_post.job_id} SAVED TO DB "
#                                             f"(external link found!)"
#                                         )
#                                 else:
#                                     duplicate_count += 1

#                     except Exception as e:
#                         print(f"   ✗ {src_job['job_id']}: {e}")

#             grand_external += external_count
#             grand_salary += salary_count
#             grand_exp += exp_count

#             print(
#                 f"   ✅ [{idx+1}/{total_keywords}] '{keyword}' done | "
#                 f"jobs={len(keyword_jobs)} external={external_count} | "
#                 f"saved={keyword_saved}"
#             )

#             if idx < total_keywords - 1:
#                 delay = random.uniform(3, 6)
#                 print(f"   ⏱️  Waiting {delay:.1f}s before next keyword...")
#                 time.sleep(delay)

#         # ── Final summary ─────────────────────────────────────────────────────
#         print(f"\n{'='*60}")
#         print("✅ SCRAPE COMPLETE")
#         print(f"{'='*60}")
#         if all_jobs:
#             pct = grand_external / len(all_jobs) * 100
#             print(f"📊 Total jobs processed : {len(all_jobs)}")
#             print(f"🔗 External links found : {grand_external} ({pct:.1f}%)")
#             print(f"💰 Jobs with salary info: {grand_salary}")
#             print(f"📝 Jobs with experience : {grand_exp}")
#             if save_to_db:
#                 print(f"💾 IMMEDIATE SAVES      : {saved_count} new jobs saved")
#                 print(f"🔄 Duplicates skipped   : {duplicate_count}")

#         return all_jobs

#     # ─────────────────────────────────────────────────────────────────────────
#     # CSV EXPORT  (unchanged — identical in both A and B)
#     # ─────────────────────────────────────────────────────────────────────────

#     def save_to_csv(self, jobs: List[JobPost], filename: str = None):
#         """Save jobs to CSV file with enhanced fields."""
#         if not filename:
#             filename = f"linkedin_jobs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

#         import csv
#         with open(filename, "w", newline="", encoding="utf-8") as f:
#             writer = csv.writer(f)
#             writer.writerow([
#                 "Job ID", "Title", "Company", "Company Logo", "Location",
#                 "Date Posted", "Job URL", "External Apply URL", "Is Remote",
#                 "Is Easy Apply", "Job Type", "Job Level", "Industry",
#                 "Search Keyword", "Salary Min", "Salary Max", "Salary Text",
#                 "Experience Required", "Description Preview",
#             ])
#             for job in jobs:
#                 writer.writerow([
#                     job.job_id,
#                     job.title,
#                     job.company_name,
#                     job.company_logo or "",
#                     job.location.display_location(),
#                     job.date_posted,
#                     job.job_url,
#                     job.apply_url or "",
#                     job.is_remote,
#                     job.is_easy_apply,
#                     ", ".join(jt.value for jt in job.job_type) if job.job_type else "",
#                     job.job_level or "",
#                     job.company_industry or "",
#                     job.search_keyword or "",
#                     job.compensation.min_amount if job.compensation else "",
#                     job.compensation.max_amount if job.compensation else "",
#                     getattr(job, "salary_text", "") or "",
#                     getattr(job, "experience", "") or "",
#                     (job.description or "")[:200] + "..."
#                     if job.description and len(job.description) > 200
#                     else (job.description or ""),
#                 ])

#         print(f"💾 Saved {len(jobs)} jobs to {filename}")



















































































# """
# LinkedIn Scraper — Merged Version
# ─────────────────────────────────
# WHAT WAS MERGED:
#   • External URL extraction  → taken from Code B (_fetch_external_url, 6 methods)
#   • Field extraction logic   → taken from Code A (delegates to util.py helpers)
#   • Auth / cookie support    → taken from Code B (LINKEDIN_COOKIE env var)
#   • Graceful API fallback    → taken from Code B (api_html="" on failure)
#   • Duplicate tracking       → taken from Code B (duplicate_count in summary)

# WHAT WAS NOT CHANGED:
#   • search_all_jobs()         — untouched (identical in both)
#   • scrape_all_jobs_batch()   — untouched structure, only stats vars aligned
#   • save_to_csv()             — untouched (identical in both)
#   • Rate limiting / throttle  — untouched
#   • Threading / DB logic      — untouched
#   • All util.py delegations   — kept exactly as in Code A

# THREAD-SAFETY NOTE (discovered during research):
#   requests.Session is NOT thread-safe when shared across threads.
#   Both original codes shared one session. Fixed here via threading.local()
#   so each worker thread gets its own session automatically.
# """

# import os
# import time
# import random
# import re
# import json
# import threading
# from datetime import datetime
# from typing import Optional, List, Dict
# from urllib.parse import urlparse, unquote
# from concurrent.futures import ThreadPoolExecutor, as_completed

# import requests
# from bs4 import BeautifulSoup

# from .models import JobPost, Location, Compensation, JobType
# from .constant import headers
# from .util import (
#     parse_job_type,
#     parse_job_level,
#     parse_company_industry,
#     is_job_remote,
#     extract_external_url_from_html,
#     extract_emails_from_text,
#     parse_relative_date,
#     create_session,
#     parse_salary_from_text,
#     parse_experience_from_text,
#     extract_company_logo,
# )
# from .database import SupabaseManager


# # ─────────────────────────────────────────────────────────────────────────────
# # Module-level helper (from Code B — wired up properly here)
# # ─────────────────────────────────────────────────────────────────────────────

# def _is_external(url: str) -> bool:
#     """True only for real third-party URLs that are not LinkedIn."""
#     if not url or not url.startswith("http"):
#         return False
#     try:
#         host = urlparse(url).netloc.lower()
#     except Exception:
#         return False
#     return (
#         "linkedin.com" not in host
#         and "lnkd.in" not in host
#         and host != ""
#     )


# # ─────────────────────────────────────────────────────────────────────────────
# # Main Scraper Class
# # ─────────────────────────────────────────────────────────────────────────────

# class LinkedInScraper:
#     """
#     High-performance LinkedIn scraper.
#     External URL extraction  : Code B's 6-method _fetch_external_url()
#     Field extraction logic   : Code A's util.py-delegated get_job_details()
#     """

#     def __init__(self, proxies=None, ca_cert=None, user_agent=None, use_database=True):
#         self.base_url = "https://www.linkedin.com"

#         # ── Auth (Code B) ─────────────────────────────────────────────────
#         cookie = os.getenv("LINKEDIN_COOKIE")
#         self.session = create_session(proxies=proxies, ca_cert=ca_cert, cookie=cookie)
#         self.session.headers.update(headers)

#         # ── Thread-local sessions (fix: requests.Session is not thread-safe)
#         # Each worker thread will have its own isolated session clone.
#         self._thread_local = threading.local()
#         self._proxies = proxies
#         self._ca_cert = ca_cert
#         self._cookie = cookie

#         # ── Rate limiting ─────────────────────────────────────────────────
#         self.min_delay = 1.0
#         self.max_delay = 3.0
#         self.current_delay = self.min_delay
#         self.consecutive_errors = 0
#         self.max_consecutive_errors = 3
#         self.error_backoff = 1.5

#         # ── Thread safety for shared state ────────────────────────────────
#         self._lock = threading.Lock()
#         self._extracted_links = set()

#         # ── Database ──────────────────────────────────────────────────────
#         self.use_database = use_database
#         self.db = SupabaseManager() if use_database else None
#         if use_database:
#             self.db.initialize()

#         self.saved_jobs_count = 0

#     # ─────────────────────────────────────────────────────────────────────────
#     # Per-thread session (thread-safety fix)
#     # ─────────────────────────────────────────────────────────────────────────

#     def _get_thread_session(self) -> requests.Session:
#         """
#         Return a requests.Session bound to the current thread.
#         Creates one if it doesn't exist yet for this thread.
#         This avoids the known thread-unsafety of sharing one Session.
#         """
#         if not hasattr(self._thread_local, "session"):
#             sess = create_session(proxies=self._proxies, ca_cert=self._ca_cert,
#                                   cookie=self._cookie)
#             sess.headers.update(headers)
#             self._thread_local.session = sess
#         return self._thread_local.session

#     # ─────────────────────────────────────────────────────────────────────────
#     # Rate limiting helpers  (unchanged from both A and B)
#     # ─────────────────────────────────────────────────────────────────────────

#     def _throttle(self):
#         """Apply throttling based on current delay."""
#         with self._lock:
#             time.sleep(self.current_delay + random.uniform(0, 0.5))

#     def _handle_error(self):
#         """Increase delay on errors."""
#         with self._lock:
#             self.consecutive_errors += 1
#             if self.consecutive_errors >= self.max_consecutive_errors:
#                 self.current_delay = min(
#                     self.current_delay * self.error_backoff, self.max_delay
#                 )
#                 self.consecutive_errors = 0
#                 print(f"⚠️ Increasing delay to {self.current_delay:.1f}s due to errors")

#     def _handle_success(self):
#         """Gradually decrease delay on success."""
#         with self._lock:
#             self.consecutive_errors = 0
#             if self.current_delay > self.min_delay:
#                 self.current_delay = max(
#                     self.current_delay / self.error_backoff, self.min_delay
#                 )

#     # ─────────────────────────────────────────────────────────────────────────
#     # Internal URL checker  (from Code A — used throughout)
#     # ─────────────────────────────────────────────────────────────────────────

#     def _is_linkedin_internal(self, url: str) -> bool:
#         """Check if URL is a LinkedIn internal page."""
#         if not url:
#             return True
#         url_lower = url.lower()
#         if "linkedin.com" in url_lower:
#             return True
#         internal_patterns = [
#             "signup", "login", "auth", "checkpoint",
#             "cold-join", "registration", "sign-in",
#         ]
#         for pattern in internal_patterns:
#             if pattern in url_lower:
#                 return True
#         return False

#     # ─────────────────────────────────────────────────────────────────────────
#     # SEARCH  (unchanged — identical in both A and B)
#     # ─────────────────────────────────────────────────────────────────────────

#     def search_all_jobs(self, keyword: str, location: str = "United States",
#                         hours_old: int = 24) -> List[Dict]:
#         """
#         Search for ALL jobs posted in the last N hours for a keyword.
#         Continues pagination until LinkedIn returns an empty page.
#         """
#         jobs = []
#         seen_job_ids = set()
#         start = 0
#         page = 1
#         max_pages = 200
#         empty_page_retries = 2
#         consecutive_empty = 0

#         print(f"\n   📍 Searching all pages for: {keyword}")

#         while page <= max_pages:
#             params = {
#                 "keywords": keyword,
#                 "location": location,
#                 "distance": "100",
#                 "f_TPR": f"r{hours_old * 3600}",
#                 "start": start,
#                 "refresh": True,
#             }
#             url = f"{self.base_url}/jobs-guest/jobs/api/seeMoreJobPostings/search"

#             try:
#                 self._throttle()
#                 response = self.session.get(url, params=params, timeout=15)

#                 if response.status_code == 429:
#                     wait = random.uniform(10, 20)
#                     print(f"   ⚠️ Rate limited (429). Waiting {wait:.0f}s before retry...")
#                     time.sleep(wait)
#                     continue

#                 if response.status_code != 200:
#                     print(f"   ❌ Search failed: HTTP {response.status_code}")
#                     self._handle_error()
#                     break

#                 soup = BeautifulSoup(response.text, "html.parser")
#                 job_cards = soup.find_all("div", class_="base-card")

#                 if not job_cards:
#                     consecutive_empty += 1
#                     if consecutive_empty <= empty_page_retries:
#                         print(f"   ⚠️ Empty page at start={start} "
#                               f"(attempt {consecutive_empty}/{empty_page_retries}), retrying...")
#                         time.sleep(random.uniform(3, 6))
#                         continue
#                     else:
#                         print(f"   ✅ Confirmed end of results after {len(jobs)} jobs "
#                               f"(empty response at start={start})")
#                         break
#                 consecutive_empty = 0

#                 page_jobs = 0
#                 for card in job_cards:
#                     try:
#                         link_tag = card.find("a", class_="base-card__full-link")
#                         if not link_tag or not link_tag.get("href"):
#                             continue

#                         href = link_tag["href"]
#                         job_id = href.split("?")[0].split("-")[-1]

#                         if job_id in seen_job_ids:
#                             continue
#                         seen_job_ids.add(job_id)

#                         title_tag = card.find("h3", class_="base-search-card__title")
#                         title = title_tag.get_text(strip=True) if title_tag else "Unknown"

#                         company_tag = card.find("h4", class_="base-search-card__subtitle")
#                         company = company_tag.get_text(strip=True) if company_tag else "Unknown"

#                         location_tag = card.find("span", class_="job-search-card__location")
#                         location_str = location_tag.get_text(strip=True) if location_tag else ""

#                         jobs.append({
#                             "job_id": job_id,
#                             "title": title,
#                             "company": company,
#                             "location": location_str,
#                             "link": f"{self.base_url}/jobs/view/{job_id}",
#                         })
#                         page_jobs += 1

#                     except Exception as e:
#                         print(f"   ⚠️ Error parsing job card: {e}")
#                         continue

#                 print(f"   📄 Page {page} (start={start}): {page_jobs} new jobs "
#                       f"| Running total: {len(jobs)}")

#                 start += 25
#                 page += 1
#                 self._handle_success()
#                 time.sleep(random.uniform(1.0, 2.5))

#             except Exception as e:
#                 print(f"   ❌ Search error on page {page}: {e}")
#                 self._handle_error()
#                 time.sleep(5)
#                 break

#         if page > max_pages:
#             print(f"   ⚠️ Reached safety limit of {max_pages} pages for '{keyword}'")

#         print(f"   📊 Total unique jobs found for '{keyword}': {len(jobs)}")
#         return jobs

#     # ─────────────────────────────────────────────────────────────────────────
#     # EXTERNAL URL EXTRACTION  — taken fully from Code B
#     # ─────────────────────────────────────────────────────────────────────────

#     def _fetch_external_url(self, job_id: str,
#                             api_html: str,
#                             view_html: str) -> Optional[str]:
#         """
#         Extract the external apply URL using Code B's 6-method cascade.
#         Methods are tried in order; first valid external URL wins.
#         """
#         sess = self._get_thread_session()

#         # METHOD 0: Ultra-robust catch-all regex for offsiteApplyUrl
#         # Captures any https://... closely following offsiteApplyUrl regardless
#         # of quote style or backslash escaping.
#         for label, html in [("view", view_html), ("api", api_html)]:
#             if not html:
#                 continue
#             pattern = r'(?i)offsiteApplyUrl.*?[:=].*?(https?://[^"\'\\,&\s>]+)'
#             matches = re.findall(pattern, html)
#             for url in matches:
#                 try:
#                     url = unquote(url).replace("\\/", "/")
#                     if url and not self._is_linkedin_internal(url):
#                         print(f"      ✅ [catchall-{label}] {url[:80]}")
#                         return url
#                 except Exception:
#                     pass

#         # METHOD 1: Direct regex for offsiteApplyUrl (strict + escaped variants)
#         for label, html in [("view", view_html), ("api", api_html)]:
#             if not html:
#                 continue
#             # Strict JSON key
#             for url in re.findall(r'"offsiteApplyUrl"\s*:\s*"(https?://[^"]+)"', html):
#                 if not self._is_linkedin_internal(url):
#                     print(f"      ✅ [direct-{label}] {url[:80]}")
#                     return url
#             # Escaped variant
#             for url in re.findall(
#                 r'\\?"offsiteApplyUrl\\?"\s*:\s*\\?"(https?://[^"\\]+)\\"', html
#             ):
#                 url = url.replace("\\/", "/")
#                 if not self._is_linkedin_internal(url):
#                     print(f"      ✅ [direct-escaped-{label}] {url[:80]}")
#                     return url

#         # METHOD 2: Script tag scanning for applyUrl variants
#         for label, html in [("view", view_html), ("api", api_html)]:
#             if not html:
#                 continue
#             soup = BeautifulSoup(html, "html.parser")
#             patterns = [
#                 r'"offsiteApplyUrl"\s*:\s*"([^"]+)"',
#                 r'"applyUrl"\s*:\s*"([^"]+)"',
#                 r'"externalApplyUrl"\s*:\s*"([^"]+)"',
#             ]
#             for script in soup.find_all("script"):
#                 if not script.string:
#                     continue
#                 for pat in patterns:
#                     for url in re.findall(pat, script.string):
#                         url = url.replace("\\/", "/")
#                         if url and not self._is_linkedin_internal(url):
#                             print(f"      ✅ [script-{label}] {url[:80]}")
#                             return url

#         # METHOD 3: Hit the externalApply endpoint directly and follow redirects
#         try:
#             ext_url = f"{self.base_url}/jobs/view/externalApply/{job_id}"
#             ext_response = sess.get(ext_url, timeout=5, allow_redirects=True)
#             final_url = ext_response.url
#             if final_url and not self._is_linkedin_internal(final_url):
#                 print(f"      ✅ [endpoint] {final_url[:80]}")
#                 return final_url
#         except Exception:
#             pass

#         # METHOD 4: Apply-button link scanning with context heuristics
#         for label, html in [("view", view_html), ("api", api_html)]:
#             if not html:
#                 continue
#             soup = BeautifulSoup(html, "html.parser")
#             for a in soup.find_all("a", href=True):
#                 href = a.get("href", "")
#                 if not href or self._is_linkedin_internal(href):
#                     continue
#                 context = (
#                     a.get_text(strip=True).lower()
#                     + " " + str(a.get("class", "")).lower()
#                     + " " + str(a.get("id", "")).lower()
#                 )
#                 apply_indicators = ["apply", "application", "submit", "external", "offsite"]
#                 if any(ind in context for ind in apply_indicators):
#                     print(f"      ✅ [button-{label}] {href[:80]}")
#                     return href

#         # METHOD 5: Redirect URL query parameter extraction
#         for label, html in [("view", view_html), ("api", api_html)]:
#             if not html:
#                 continue
#             redirect_patterns = [
#                 r"[?&]url=([^&\"'\s>]+)",
#                 r"[?&]redirectUrl=([^&\"'\s>]+)",
#                 r"[?&]applyUrl=([^&\"'\s>]+)",
#             ]
#             for pat in redirect_patterns:
#                 for match in re.findall(pat, html):
#                     try:
#                         url = unquote(match)
#                         if url and not self._is_linkedin_internal(url):
#                             print(f"      ✅ [redirect-{label}] {url[:80]}")
#                             return url
#                     except Exception:
#                         pass

#         print(f"      ℹ️  No external URL found for {job_id} — Easy Apply")
#         return None

#     # ─────────────────────────────────────────────────────────────────────────
#     # JOB DETAILS  — Code B's fetch strategy + Code A's field extraction
#     # ─────────────────────────────────────────────────────────────────────────

#     def get_job_details(self, job_id: str, job_data: Dict = None) -> Optional[JobPost]:
#         """
#         Fetch detailed job information.

#         HTTP fetching  : Code B (graceful fallback if guest API fails)
#         External URL   : Code B's _fetch_external_url() (6-method cascade)
#         Field parsing  : Code A (delegates to util.py helpers)
#         """
#         job_view_url = f"{self.base_url}/jobs/view/{job_id}"
#         api_url = f"{self.base_url}/jobs-guest/jobs/api/jobPosting/{job_id}"
#         sess = self._get_thread_session()

#         try:
#             # ── Fetch API page (Code B: graceful fallback on failure) ──────
#             self._throttle()
#             api_resp = sess.get(api_url, timeout=10)

#             if api_resp.status_code == 429:
#                 print(f"      ℹ️ Guest API rate limited for {job_id}, falling back...")
#                 api_html = ""
#             elif api_resp.status_code != 200:
#                 print(f"      ℹ️ Guest API fetch failed {job_id}: "
#                       f"{api_resp.status_code}, falling back...")
#                 api_html = ""
#             else:
#                 api_html = api_resp.text

#             # ── Fetch view page ───────────────────────────────────────────
#             self._throttle()
#             view_resp = sess.get(job_view_url, timeout=10)
#             view_html = view_resp.text if view_resp.status_code == 200 else ""

#             # Use whichever page has content for BeautifulSoup parsing
#             soup = BeautifulSoup(view_html or api_html, "html.parser")

#             # ── External URL — Code B's 6-method cascade ──────────────────
#             external_url = self._fetch_external_url(job_id, api_html, view_html)

#             # Final guard: discard if it somehow resolved to a LinkedIn URL
#             if external_url and self._is_linkedin_internal(external_url):
#                 external_url = None

#             # ─────────────────────────────────────────────────────────────
#             # FIELD EXTRACTION — Code A logic (util.py delegation)
#             # ─────────────────────────────────────────────────────────────

#             # Title
#             title = job_data.get("title") if job_data else ""
#             if not title:
#                 title_tag = soup.find("h1", class_="top-card-layout__title")
#                 title = title_tag.get_text(strip=True) if title_tag else "Unknown"

#             # Company
#             company = job_data.get("company") if job_data else ""
#             if not company:
#                 company_tag = soup.find("a", class_="topcard__org-name-link")
#                 company = company_tag.get_text(strip=True) if company_tag else "Unknown"

#             # Company logo — delegates to util.py
#             # Both api_html and view_html passed so util searches JSON blobs
#             # on both pages for logoUrl / company-logo CDN URLs.
#             company_logo = extract_company_logo(soup, api_html=api_html, view_html=view_html)

#             # Description
#             # Tries view page soup first, then api page soup as fallback.
#             # Covers all known LinkedIn class names (guest API + view page, 2024-2025).
#             description = ""
#             desc_selectors = [
#                 "div.show-more-less-html__markup",          # guest API page (primary)
#                 "div.description__text",                    # older guest API layout
#                 "div.jobs-description__content",            # view page layout A
#                 "div.decorated-job-posting__details",       # view page layout B
#                 "div.description__text--rich",              # view page layout C
#                 "div.job-description__content",             # some company-hosted layouts
#                 "div#job-details",                          # view page fallback
#                 "section.description",                      # section wrapper fallback
#             ]
#             # First pass: view soup
#             for selector in desc_selectors:
#                 desc_tag = soup.select_one(selector)
#                 if desc_tag:
#                     description = desc_tag.get_text(strip=True)
#                     break

#             # Second pass: api_html soup (if view page had nothing)
#             if not description and api_html:
#                 api_soup_desc = BeautifulSoup(api_html, "html.parser")
#                 for selector in desc_selectors:
#                     desc_tag = api_soup_desc.select_one(selector)
#                     if desc_tag:
#                         description = desc_tag.get_text(strip=True)
#                         break

#             # Third pass: JSON blob in either HTML (LinkedIn embeds description in JSON)
#             if not description:
#                 for raw_html in [api_html, view_html]:
#                     if not raw_html:
#                         continue
#                     import json as _json
#                     # Try to extract description from embedded JSON
#                     try:
#                         m = re.search(
#                             r'"description"\s*:\s*\{\s*"text"\s*:\s*"((?:[^"\\]|\\.)+)"',
#                             raw_html
#                         )
#                         if m:
#                             description = m.group(1).replace('\\n', '\n').replace('\\"', '"')
#                             break
#                     except Exception:
#                         pass

#             # Location
#             location_str = job_data.get("location") if job_data else ""
#             if not location_str:
#                 location_tag = soup.find("span", class_="topcard__flavor--bullet")
#                 if location_tag:
#                     location_str = location_tag.get_text(strip=True)
#             location = Location.from_string(location_str) if location_str else Location()

#             # Date posted
#             # Tries all known LinkedIn date selectors across view + api pages.
#             # Falls back to JSON blob extraction if no HTML tag found.
#             date_posted = None

#             # All known date tag selectors (confirmed across 2024-2025 layouts)
#             date_tag = (
#                 soup.find("span", class_="posted-time-ago__text")           # guest API primary
#                 or soup.find("span", class_="topcard__flavor--bullet")      # older layout
#                 or soup.find("span", class_="jobs-top-card__posted-date")   # view page A
#                 or soup.find("time", attrs={"datetime": True})              # <time> element
#                 or soup.find("span", attrs={"class": lambda c: c and
#                              any("posted" in x or "date" in x
#                                  for x in (c if isinstance(c, list) else [c]))})
#             )
#             if date_tag:
#                 date_text = date_tag.get("datetime") or date_tag.get_text(strip=True)
#                 if date_text:
#                     date_posted = parse_relative_date(date_text)

#             # Fallback: JSON blob in api_html or view_html
#             if not date_posted:
#                 for raw_html in [api_html, view_html]:
#                     if not raw_html:
#                         continue
#                     try:
#                         m = re.search(
#                             r'"listedAt"\s*:\s*(\d+)',
#                             raw_html
#                         )
#                         if m:
#                             import datetime as _dt
#                             ts = int(m.group(1)) / 1000  # LinkedIn uses ms timestamps
#                             date_posted = _dt.datetime.utcfromtimestamp(ts).date()
#                             break
#                     except Exception:
#                         pass

#             # Job type — Code A: delegates to util.py
#             job_type = parse_job_type(soup)

#             # Job level — Code A: delegates to util.py
#             job_level = parse_job_level(soup)

#             # Company industry — Code A: delegates to util.py
#             company_industry = parse_company_industry(soup)

#             # Salary — Code A: delegates to util.py
#             salary_min, salary_max, salary_text = parse_salary_from_text(
#                 description, view_html or api_html
#             )

#             # Experience — Code A: delegates to util.py
#             experience = parse_experience_from_text(description, view_html or api_html)

#             # Remote check — Code A: delegates to util.py
#             is_remote = is_job_remote(title, description, location)

#             # Easy apply flag
#             is_easy_apply = not external_url

#             # Compensation object
#             compensation = None
#             if salary_min or salary_max:
#                 compensation = Compensation(
#                     min_amount=salary_min,
#                     max_amount=salary_max,
#                     currency="USD",
#                     interval="yearly",
#                 )

#             # Search keyword
#             search_keyword = job_data.get("keyword") if job_data else None

#             # ── Build JobPost ─────────────────────────────────────────────
#             job = JobPost(
#                 job_id=job_id,
#                 title=title,
#                 company_name=company,
#                 company_logo=company_logo,
#                 location=location,
#                 description=description[:10000] if description else None,
#                 date_posted=date_posted,
#                 job_url=job_view_url,
#                 apply_url=external_url,
#                 job_url_direct=external_url,
#                 job_type=job_type,
#                 job_level=job_level,
#                 company_industry=company_industry,
#                 is_remote=is_remote,
#                 is_easy_apply=is_easy_apply,
#                 compensation=compensation,
#                 emails=extract_emails_from_text(description or ""),
#                 search_keyword=search_keyword,
#                 experience=experience,
#                 salary_text=salary_text,
#             )

#             self._handle_success()

#             if job.apply_url:
#                 print(
#                     f"      📊 Extracted: Logo={bool(company_logo)}, "
#                     f"Salary={salary_text}, JobType={job_type}, "
#                     f"Level={job_level}, Experience={experience}"
#                 )

#             return job

#         except Exception as e:
#             print(f"❌ Error fetching job {job_id}: {e}")
#             self._handle_error()
#             return None

#     # ─────────────────────────────────────────────────────────────────────────
#     # BATCH SCRAPE  (structure from Code B + stats alignment)
#     # ─────────────────────────────────────────────────────────────────────────

#     def scrape_all_jobs_batch(self, keywords: List[str],
#                               location: str = "United States",
#                               max_workers: int = 5,
#                               save_to_db: bool = True) -> List[JobPost]:
#         """
#         Scrape ALL jobs posted in last 24 hours for multiple keywords in parallel.
#         Saves each job to database IMMEDIATELY after it's fetched (real-time storage).
#         """
#         all_jobs = []
#         seen_global_ids = set()
#         total_keywords = len(keywords)
#         actual_workers = min(max_workers, 5)

#         grand_external = 0
#         grand_salary = 0
#         grand_exp = 0
#         saved_count = 0
#         duplicate_count = 0

#         if save_to_db and not (self.db and self.db.initialized):
#             print("\n⚠️ Supabase not initialised — DB saves will be skipped")
#             save_to_db = False

#         for idx, keyword in enumerate(keywords):
#             print(f"\n{'='*60}")
#             print(f"🔍 [{idx+1}/{total_keywords}] Keyword: {keyword}")
#             print(f"{'='*60}")

#             raw_jobs = self.search_all_jobs(keyword, location, hours_old=24)

#             keyword_results = []
#             for job in raw_jobs:
#                 if job["job_id"] not in seen_global_ids:
#                     seen_global_ids.add(job["job_id"])
#                     job["keyword"] = keyword
#                     keyword_results.append(job)

#             print(f"   📋 {len(keyword_results)} unique new jobs to fetch for '{keyword}'")

#             if not keyword_results:
#                 if idx < total_keywords - 1:
#                     delay = random.uniform(3, 6)
#                     print(f"   ⏱️  Waiting {delay:.1f}s before next keyword...")
#                     time.sleep(delay)
#                 continue

#             print(f"   🔗 Fetching details and saving in REAL-TIME "
#                   f"({actual_workers} workers)...")

#             keyword_jobs = []
#             external_count = 0
#             salary_count = 0
#             exp_count = 0
#             completed = 0
#             kw_total = len(keyword_results)
#             keyword_saved = 0

#             with ThreadPoolExecutor(max_workers=actual_workers) as executor:
#                 future_to_job = {
#                     executor.submit(self.get_job_details, j["job_id"], j): j
#                     for j in keyword_results
#                 }

#                 for future in as_completed(future_to_job):
#                     completed += 1
#                     src_job = future_to_job[future]

#                     if completed % 25 == 0 or completed == 1 or completed == kw_total:
#                         print(
#                             f"   Progress: {completed}/{kw_total} "
#                             f"({completed / kw_total * 100:.0f}%) | "
#                             f"external={external_count} | saved={saved_count}"
#                         )

#                     try:
#                         job_post = future.result(timeout=15)
#                         if job_post:
#                             keyword_jobs.append(job_post)
#                             all_jobs.append(job_post)

#                             if job_post.apply_url:
#                                 external_count += 1
#                             if job_post.compensation and job_post.compensation.min_amount:
#                                 salary_count += 1
#                             if job_post.experience:
#                                 exp_count += 1

#                             # ─── IMMEDIATE DATABASE SAVE ──────────────────
#                             if save_to_db and self.db and self.db.initialized:
#                                 job_dict = job_post.to_supabase_dict()
#                                 result = self.db.save_job(job_dict)
#                                 if result:
#                                     saved_count += 1
#                                     keyword_saved += 1
#                                     if job_post.apply_url:
#                                         print(
#                                             f"      🚀 JOB {job_post.job_id} SAVED TO DB "
#                                             f"(external link found!)"
#                                         )
#                                 else:
#                                     duplicate_count += 1

#                     except Exception as e:
#                         print(f"   ✗ {src_job['job_id']}: {e}")

#             grand_external += external_count
#             grand_salary += salary_count
#             grand_exp += exp_count

#             print(
#                 f"   ✅ [{idx+1}/{total_keywords}] '{keyword}' done | "
#                 f"jobs={len(keyword_jobs)} external={external_count} | "
#                 f"saved={keyword_saved}"
#             )

#             if idx < total_keywords - 1:
#                 delay = random.uniform(3, 6)
#                 print(f"   ⏱️  Waiting {delay:.1f}s before next keyword...")
#                 time.sleep(delay)

#         # ── Final summary ─────────────────────────────────────────────────────
#         print(f"\n{'='*60}")
#         print("✅ SCRAPE COMPLETE")
#         print(f"{'='*60}")
#         if all_jobs:
#             pct = grand_external / len(all_jobs) * 100
#             print(f"📊 Total jobs processed : {len(all_jobs)}")
#             print(f"🔗 External links found : {grand_external} ({pct:.1f}%)")
#             print(f"💰 Jobs with salary info: {grand_salary}")
#             print(f"📝 Jobs with experience : {grand_exp}")
#             if save_to_db:
#                 print(f"💾 IMMEDIATE SAVES      : {saved_count} new jobs saved")
#                 print(f"🔄 Duplicates skipped   : {duplicate_count}")

#         return all_jobs

#     # ─────────────────────────────────────────────────────────────────────────
#     # CSV EXPORT  (unchanged — identical in both A and B)
#     # ─────────────────────────────────────────────────────────────────────────

#     def save_to_csv(self, jobs: List[JobPost], filename: str = None):
#         """Save jobs to CSV file with enhanced fields."""
#         if not filename:
#             filename = f"linkedin_jobs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

#         import csv
#         with open(filename, "w", newline="", encoding="utf-8") as f:
#             writer = csv.writer(f)
#             writer.writerow([
#                 "Job ID", "Title", "Company", "Company Logo", "Location",
#                 "Date Posted", "Job URL", "External Apply URL", "Is Remote",
#                 "Is Easy Apply", "Job Type", "Job Level", "Industry",
#                 "Search Keyword", "Salary Min", "Salary Max", "Salary Text",
#                 "Experience Required", "Description Preview",
#             ])
#             for job in jobs:
#                 writer.writerow([
#                     job.job_id,
#                     job.title,
#                     job.company_name,
#                     job.company_logo or "",
#                     job.location.display_location(),
#                     job.date_posted,
#                     job.job_url,
#                     job.apply_url or "",
#                     job.is_remote,
#                     job.is_easy_apply,
#                     ", ".join(jt.value for jt in job.job_type) if job.job_type else "",
#                     job.job_level or "",
#                     job.company_industry or "",
#                     job.search_keyword or "",
#                     job.compensation.min_amount if job.compensation else "",
#                     job.compensation.max_amount if job.compensation else "",
#                     getattr(job, "salary_text", "") or "",
#                     getattr(job, "experience", "") or "",
#                     (job.description or "")[:200] + "..."
#                     if job.description and len(job.description) > 200
#                     else (job.description or ""),
#                 ])

#         print(f"💾 Saved {len(jobs)} jobs to {filename}")























































































































"""
LinkedIn Scraper — Merged Version
─────────────────────────────────
WHAT WAS MERGED:
  • External URL extraction  → taken from Code B (_fetch_external_url, 6 methods)
  • Field extraction logic   → taken from Code A (delegates to util.py helpers)
  • Auth / cookie support    → taken from Code B (LINKEDIN_COOKIE env var)
  • Graceful API fallback    → taken from Code B (api_html="" on failure)
  • Duplicate tracking       → taken from Code B (duplicate_count in summary)

WHAT WAS NOT CHANGED:
  • search_all_jobs()         — untouched (identical in both)
  • scrape_all_jobs_batch()   — untouched structure, only stats vars aligned
  • save_to_csv()             — untouched (identical in both)
  • Rate limiting / throttle  — untouched
  • Threading / DB logic      — untouched
  • All util.py delegations   — kept exactly as in Code A

THREAD-SAFETY NOTE (discovered during research):
  requests.Session is NOT thread-safe when shared across threads.
  Both original codes shared one session. Fixed here via threading.local()
  so each worker thread gets its own session automatically.
"""

import os
import time
import random
import re
import json
import threading
from datetime import datetime
from typing import Optional, List, Dict
from urllib.parse import urlparse, unquote
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

from .models import JobPost, Location, Compensation, JobType, Country
from .constant import headers
from .util import (
    parse_job_type,
    parse_job_level,
    parse_company_industry,
    is_job_remote,
    extract_external_url_from_html,
    extract_emails_from_text,
    parse_relative_date,
    create_session,
    parse_salary_from_text,
    parse_experience_from_text,
    extract_company_logo,
    parse_skills_requirements,
    has_offsite_apply_icon,
)
from .database import SupabaseManager


# ─────────────────────────────────────────────────────────────────────────────
# Module-level helper (from Code B — wired up properly here)
# ─────────────────────────────────────────────────────────────────────────────

def _is_external(url: str) -> bool:
    """True only for real third-party URLs that are not LinkedIn."""
    if not url or not url.startswith("http"):
        return False
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return False
    return (
        "linkedin.com" not in host
        and "lnkd.in" not in host
        and host != ""
    )


# ─────────────────────────────────────────────────────────────────────────────
# Main Scraper Class
# ─────────────────────────────────────────────────────────────────────────────

class LinkedInScraper:
    """
    High-performance LinkedIn scraper.
    External URL extraction  : Code B's 6-method _fetch_external_url()
    Field extraction logic   : Code A's util.py-delegated get_job_details()
    """

    def __init__(self, proxies=None, ca_cert=None, user_agent=None, use_database=True):
        self.base_url = "https://www.linkedin.com"

        # ── Proxy Pool Handling ──────────────────────────────────────────
        if isinstance(proxies, str):
            if "," in proxies:
                self._proxies = [p.strip() for p in proxies.split(",") if p.strip()]
            else:
                self._proxies = proxies.strip()
        else:
            self._proxies = proxies

        # ── Webshare Gateway Handling ────────────────────────────────────
        # If user provided a specific rotating port (e.g. :80), use it directly.
        # Avoid manufacturing fake ports (10000-10009) that cause ConnectTimeoutError.
        original_proxy = self._proxies
        if isinstance(self._proxies, str) and "p.webshare.io" in self._proxies:
            if ":80" in self._proxies or ":8080" in self._proxies or "-rotate" in self._proxies:
                self._proxies = [self._proxies]
                clean = self._proxies[0].split("@")[-1] if "@" in self._proxies[0] else self._proxies[0]
                self._proxy_labels = {self._proxies[0]: f"Rotating Proxy: {clean}"}
            else:
                match = re.search(r'https?://([^@]+)@', self._proxies)
                if match:
                    creds = match.group(1)
                    self._proxies = [f"http://{creds}@p.webshare.io:{port}" for port in range(10000, 10010)] + [f"http://{creds}@p.webshare.io:80"]

        self._proxy_index = 0
        self._ca_cert = ca_cert
        self._proxy_labels = getattr(self, "_proxy_labels", {})
        self._last_request_time = 0.0

        # Pre-resolve proxy exit IPs once in parallel at startup for accurate logging,
        # keeping ONLY active verified proxies (discarding any that time out or fail).
        if isinstance(self._proxies, list) and len(self._proxies) > 1:
            def _check_ip(p):
                try:
                    s = requests.Session()
                    s.proxies = {"http": p, "https": p}
                    r = s.get("https://api.ipify.org?format=json", timeout=4)
                    ip = r.json().get("ip")
                    s.close()
                    return (p, ip)
                except Exception:
                    return (p, None)

            try:
                with ThreadPoolExecutor(max_workers=min(len(self._proxies), 11)) as ex:
                    raw_results = dict(ex.map(_check_ip, self._proxies))

                seen_ips = set()
                deduped_proxies = []
                for p, ip in raw_results.items():
                    if ip and ip not in seen_ips:
                        seen_ips.add(ip)
                        deduped_proxies.append(p)
                        self._proxy_labels[p] = f"Proxy IP: {ip}"

                if deduped_proxies:
                    self._proxies = deduped_proxies
                    print(f"🔀 Proxy pool: {len(self._proxies)} active verified IP(s) ready → {sorted(seen_ips)}")
                else:
                    self._proxies = [original_proxy] if isinstance(original_proxy, str) else original_proxy
                    if self._proxies:
                        clean = self._proxies[0].split("@")[-1] if "@" in self._proxies[0] else self._proxies[0]
                        self._proxy_labels[self._proxies[0]] = f"Proxy: {clean}"
            except Exception:
                pass

        # ── Guest Mode (100% Cookie-Free) ────────────────────────────────
        first_proxy = self._proxies[0] if isinstance(self._proxies, list) and self._proxies else self._proxies
        self.session = create_session(proxies=first_proxy, ca_cert=ca_cert)
        self.session.headers.update(headers)

        # ── Thread-local sessions (fix: requests.Session is not thread-safe)
        # Each worker thread will have its own isolated session clone.
        self._thread_local = threading.local()

        # ── Rate limiting / thread pacing ─────────────────────────────────
        self.worker_delay = float(os.getenv("WORKER_DELAY", "0.5"))
        self.min_delay = 0.5
        self.max_delay = 2.0
        self.current_delay = 0.5
        self.consecutive_errors = 0
        self.max_consecutive_errors = 3
        self.error_backoff = 1.2

        # ── Thread safety for shared state ────────────────────────────────
        self._lock = threading.Lock()
        self._extracted_links = set()

        # ── Database ──────────────────────────────────────────────────────
        self.use_database = use_database
        self.db = SupabaseManager() if use_database else None
        if use_database:
            self.db.initialize()

        self.saved_jobs_count = 0

    # ─────────────────────────────────────────────────────────────────────────
    # Dynamic Per-thread session & proxy rotation
    # ─────────────────────────────────────────────────────────────────────────

    def _rotate_thread_proxy(self):
        """
        Dynamically rotate the calling worker thread to a different proxy IP.
        Ensures workers are never locked to a single static IP address across jobs.
        """
        if not self._proxies:
            return

        with self._lock:
            if isinstance(self._proxies, list) and self._proxies:
                next_proxy = self._proxies[self._proxy_index % len(self._proxies)]
                self._proxy_index += 1
            else:
                next_proxy = self._proxies

        sess = self._get_thread_session()
        if next_proxy:
            sess.proxies = {"http": next_proxy, "https": next_proxy}
            # Close connection adapters so next request establishes connection to the new proxy IP
            for adapter in sess.adapters.values():
                adapter.close()
            self._thread_local.proxy = next_proxy
            lbl = self._proxy_labels.get(next_proxy)
            if not lbl:
                clean = next_proxy.split("@")[-1] if "@" in next_proxy else next_proxy
                lbl = f"Proxy: {clean}"
            self._thread_local.proxy_label = lbl

    def _get_thread_session(self) -> requests.Session:
        """
        Return a requests.Session bound to the current thread.
        Creates one if it doesn't exist yet for this thread.
        """
        if not hasattr(self._thread_local, "session"):
            with self._lock:
                if isinstance(self._proxies, list) and self._proxies:
                    thread_proxy = self._proxies[self._proxy_index % len(self._proxies)]
                    self._proxy_index += 1
                elif self._proxies:
                    thread_proxy = self._proxies
                else:
                    thread_proxy = None

            if thread_proxy:
                lbl = self._proxy_labels.get(thread_proxy)
                if not lbl:
                    clean = thread_proxy.split("@")[-1] if "@" in thread_proxy else thread_proxy
                    lbl = f"Proxy: {clean}"
                self._thread_local.proxy_label = lbl
            else:
                self._thread_local.proxy_label = "Direct IP"

            sess = create_session(proxies=thread_proxy, ca_cert=self._ca_cert)
            sess.headers.update(headers)
            self._thread_local.session = sess
            self._thread_local.proxy = thread_proxy

        return self._thread_local.session

    def _get_thread_proxy_label(self) -> str:
        """Return the active proxy label for the calling thread."""
        if not hasattr(self._thread_local, "proxy_label"):
            self._get_thread_session()
        return getattr(self._thread_local, "proxy_label", "Proxy")

    # ─────────────────────────────────────────────────────────────────────────
    # Rate limiting helpers  (unchanged from both A and B)
    # ─────────────────────────────────────────────────────────────────────────

    def _throttle(self):
        """Apply pacing per worker thread so parallel workers can run concurrently via rotating proxies."""
        last_req = getattr(self._thread_local, "last_request_time", 0.0)
        now = time.time()
        elapsed = now - last_req
        delay = getattr(self, "worker_delay", 0.5)
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self._thread_local.last_request_time = time.time()

    def _handle_error(self):
        """Increase delay on errors."""
        with self._lock:
            self.consecutive_errors += 1
            if self.consecutive_errors >= self.max_consecutive_errors:
                self.worker_delay = min(self.worker_delay * 1.5, 2.0)
                self.consecutive_errors = 0
                print(f"⚠️ Increasing worker delay to {self.worker_delay:.1f}s due to errors")

    def _handle_success(self):
        """Gradually decrease delay on success."""
        with self._lock:
            self.consecutive_errors = 0
            if self.worker_delay > 0.5:
                self.worker_delay = max(self.worker_delay / 1.2, 0.5)

    # ─────────────────────────────────────────────────────────────────────────
    # Internal URL checker  (from Code A — used throughout)
    # ─────────────────────────────────────────────────────────────────────────

    def _is_linkedin_internal(self, url: str) -> bool:
        """Check if URL is a LinkedIn internal page."""
        if not url:
            return True
        url_lower = url.lower()
        if "linkedin.com" in url_lower:
            return True
        internal_patterns = [
            "signup", "login", "auth", "checkpoint",
            "cold-join", "registration", "sign-in",
        ]
        for pattern in internal_patterns:
            if pattern in url_lower:
                return True
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # SEARCH  (unchanged — identical in both A and B)
    # ─────────────────────────────────────────────────────────────────────────

    def search_all_jobs(self, keyword: str, location: str = "United States",
                        hours_old: int = 24, max_results: Optional[int] = None) -> List[Dict]:
        """
        Search for ALL jobs posted in the last N hours for a keyword.
        Continues pagination until LinkedIn returns an empty page.
        """
        jobs = []
        seen_job_ids = set()
        start = 0
        page = 1
        max_pages = 200
        empty_page_retries = 2
        consecutive_empty = 0

        proxy_info = self._get_thread_proxy_label()
        print(f"\n   📍 Searching all pages for: {keyword} via [{proxy_info}]")

        while page <= max_pages:
            params = {
                "keywords": keyword,
                "location": location,
                "distance": "100",
                "f_TPR": f"r{hours_old * 3600}",
                "start": start,
                "refresh": True,
            }
            url = f"{self.base_url}/jobs-guest/jobs/api/seeMoreJobPostings/search"

            try:
                self._throttle()
                sess = self._get_thread_session()
                response = None
                for attempt in range(2):
                    try:
                        response = sess.get(url, params=params, timeout=15)
                        break
                    except (requests.exceptions.ProxyError, requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError):
                        self._rotate_thread_proxy()
                        sess = self._get_thread_session()

                if not response:
                    print(f"   ⚠️ Search request failed across proxies on page {page}")
                    self._handle_error()
                    break

                if response.status_code == 429:
                    wait = 10.0
                    print(f"   ⚠️ Rate limited (429). Rotating proxy & waiting {wait:.0f}s before retry...")
                    self._rotate_thread_proxy()
                    time.sleep(wait)
                    continue

                if response.status_code != 200:
                    print(f"   ❌ Search failed: HTTP {response.status_code}")
                    self._handle_error()
                    self._rotate_thread_proxy()
                    break

                soup = BeautifulSoup(response.text, "html.parser")
                job_cards = soup.find_all("div", class_="base-card")

                if not job_cards:
                    consecutive_empty += 1
                    if consecutive_empty <= empty_page_retries:
                        print(f"   ⚠️ Empty page at start={start} "
                              f"(attempt {consecutive_empty}/{empty_page_retries}), retrying...")
                        time.sleep(random.uniform(3, 6))
                        continue
                    else:
                        print(f"   ✅ Confirmed end of results after {len(jobs)} jobs "
                              f"(empty response at start={start})")
                        break
                consecutive_empty = 0

                page_jobs = 0
                for card in job_cards:
                    try:
                        link_tag = card.find("a", class_="base-card__full-link")
                        if not link_tag or not link_tag.get("href"):
                            continue

                        href = link_tag["href"]
                        job_id = href.split("?")[0].split("-")[-1]

                        if job_id in seen_job_ids:
                            continue
                        seen_job_ids.add(job_id)

                        title_tag = card.find("h3", class_="base-search-card__title")
                        title = title_tag.get_text(strip=True) if title_tag else "Unknown"

                        company_tag = card.find("h4", class_="base-search-card__subtitle")
                        company = company_tag.get_text(strip=True) if company_tag else "Unknown"

                        location_tag = card.find("span", class_="job-search-card__location")
                        location_str = location_tag.get_text(strip=True) if location_tag else ""

                        jobs.append({
                            "job_id": job_id,
                            "title": title,
                            "company": company,
                            "location": location_str,
                            "link": f"{self.base_url}/jobs/view/{job_id}",
                        })
                        page_jobs += 1

                    except Exception as e:
                        print(f"   ⚠️ Error parsing job card: {e}")
                        continue

                print(f"   📄 Page {page} (start={start}): {page_jobs} new jobs "
                      f"| Running total: {len(jobs)}")

                start += 25
                page += 1
                self._handle_success()

                if max_results and len(jobs) >= max_results:
                    print(f"   🎯 Reached search candidate limit of {max_results} jobs for '{keyword}'")
                    break

                time.sleep(1.0)

            except Exception as e:
                print(f"   ❌ Search error on page {page}: {e}")
                self._handle_error()
                time.sleep(5)
                break

        if page > max_pages:
            print(f"   ⚠️ Reached safety limit of {max_pages} pages for '{keyword}'")

        print(f"   📊 Total unique jobs found for '{keyword}': {len(jobs)}")
        return jobs

    # ─────────────────────────────────────────────────────────────────────────
    # EXTERNAL URL EXTRACTION  — taken fully from Code B
    # ─────────────────────────────────────────────────────────────────────────

    def _fetch_external_url(self, job_id: str,
                            api_html: str,
                            view_html: str) -> Optional[str]:
        """
        Extract the external apply URL using Code B's 6-method cascade.
        Methods are tried in order; first valid external URL wins.
        """
        sess = self._get_thread_session()

        # METHOD 0: Ultra-robust catch-all regex for offsiteApplyUrl
        # Captures any https://... closely following offsiteApplyUrl regardless
        # of quote style or backslash escaping.
        for label, html in [("view", view_html), ("api", api_html)]:
            if not html:
                continue
            pattern = r'(?i)offsiteApplyUrl.*?[:=].*?(https?://[^"\'\\,&\s>]+)'
            matches = re.findall(pattern, html)
            for url in matches:
                try:
                    url = unquote(url).replace("\\/", "/")
                    if url and not self._is_linkedin_internal(url):
                        print(f"      ✅ [catchall-{label}] {url[:80]}")
                        return url
                except Exception:
                    pass

        # METHOD 1: Direct regex for offsiteApplyUrl (strict + escaped variants)
        for label, html in [("view", view_html), ("api", api_html)]:
            if not html:
                continue
            # Strict JSON key
            for url in re.findall(r'"offsiteApplyUrl"\s*:\s*"(https?://[^"]+)"', html):
                if not self._is_linkedin_internal(url):
                    print(f"      ✅ [direct-{label}] {url[:80]}")
                    return url
            # Escaped variant
            for url in re.findall(
                r'\\?"offsiteApplyUrl\\?"\s*:\s*\\?"(https?://[^"\\]+)\\"', html
            ):
                url = url.replace("\\/", "/")
                if not self._is_linkedin_internal(url):
                    print(f"      ✅ [direct-escaped-{label}] {url[:80]}")
                    return url

        # METHOD 2: Script tag scanning for applyUrl variants
        for label, html in [("view", view_html), ("api", api_html)]:
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            patterns = [
                r'"offsiteApplyUrl"\s*:\s*"([^"]+)"',
                r'"applyUrl"\s*:\s*"([^"]+)"',
                r'"externalApplyUrl"\s*:\s*"([^"]+)"',
            ]
            for script in soup.find_all("script"):
                if not script.string:
                    continue
                for pat in patterns:
                    for url in re.findall(pat, script.string):
                        url = url.replace("\\/", "/")
                        if url and not self._is_linkedin_internal(url):
                            print(f"      ✅ [script-{label}] {url[:80]}")
                            return url

        # METHOD 3: Hit the externalApply endpoint directly and follow redirects
        try:
            ext_url = f"{self.base_url}/jobs/view/externalApply/{job_id}"
            ext_response = sess.get(ext_url, timeout=5, allow_redirects=True)
            final_url = ext_response.url
            if final_url and not self._is_linkedin_internal(final_url):
                print(f"      ✅ [endpoint] {final_url[:80]}")
                return final_url
        except Exception:
            pass

        # METHOD 4: Apply-button link scanning with context heuristics
        for label, html in [("view", view_html), ("api", api_html)]:
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                if not href or self._is_linkedin_internal(href):
                    continue
                context = (
                    a.get_text(strip=True).lower()
                    + " " + str(a.get("class", "")).lower()
                    + " " + str(a.get("id", "")).lower()
                )
                apply_indicators = ["apply", "application", "submit", "external", "offsite"]
                if any(ind in context for ind in apply_indicators):
                    print(f"      ✅ [button-{label}] {href[:80]}")
                    return href

        # METHOD 5: Redirect URL query parameter extraction
        for label, html in [("view", view_html), ("api", api_html)]:
            if not html:
                continue
            redirect_patterns = [
                r"[?&]url=([^&\"'\s>]+)",
                r"[?&]redirectUrl=([^&\"'\s>]+)",
                r"[?&]applyUrl=([^&\"'\s>]+)",
            ]
            for pat in redirect_patterns:
                for match in re.findall(pat, html):
                    try:
                        url = unquote(match)
                        if url and not self._is_linkedin_internal(url):
                            print(f"      ✅ [redirect-{label}] {url[:80]}")
                            return url
                    except Exception:
                        pass

        print(f"      ℹ️  No external URL found for {job_id} — Easy Apply")
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # JOB DETAILS  — Code B's fetch strategy + Code A's field extraction
    # ─────────────────────────────────────────────────────────────────────────

    def get_job_details(self, job_id: str, job_data: Dict = None) -> Optional[JobPost]:
        """
        Fetch detailed job information.

        HTTP fetching  : Code B (graceful fallback if guest API fails)
        External URL   : Code B's _fetch_external_url() (6-method cascade)
        Field parsing  : Code A (delegates to util.py helpers)
        """
        # Dynamically rotate proxy for this job so workers never stay on a single static IP
        self._rotate_thread_proxy()

        job_view_url = f"{self.base_url}/jobs/view/{job_id}"
        api_url = f"{self.base_url}/jobs-guest/jobs/api/jobPosting/{job_id}"
        sess = self._get_thread_session()
        proxy_label = self._get_thread_proxy_label()
        print(f"      🌐 [{proxy_label}] Fetching job: {job_id}")

        try:
            # ── Fetch API page with automatic retry on proxy failure ──────
            self._throttle()
            api_resp = None
            for _ in range(2):
                try:
                    api_resp = sess.get(api_url, timeout=12)
                    break
                except (requests.exceptions.ProxyError, requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError) as pe:
                    self._rotate_thread_proxy()
                    sess = self._get_thread_session()

            if api_resp and api_resp.status_code == 429:
                print(f"      ℹ️ Guest API rate limited for {job_id}, falling back...")
                api_html = ""
            elif not api_resp or api_resp.status_code != 200:
                code_str = f"{api_resp.status_code}" if api_resp else "Connection/Proxy Timeout"
                print(f"      ℹ️ Guest API fetch failed {job_id}: {code_str}, falling back...")
                api_html = ""
            else:
                api_html = api_resp.text

            # ── Fetch view page with automatic retry on proxy failure ─────
            self._throttle()
            view_resp = None
            for _ in range(2):
                try:
                    view_resp = sess.get(job_view_url, timeout=12)
                    break
                except (requests.exceptions.ProxyError, requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError) as pe:
                    self._rotate_thread_proxy()
                    sess = self._get_thread_session()

            view_html = view_resp.text if (view_resp and view_resp.status_code == 200) else ""

            # Use whichever page has content for BeautifulSoup parsing
            soup = BeautifulSoup(view_html or api_html, "html.parser")

            # ── External URL — 6-method cascade ───────────────────────────
            external_url = self._fetch_external_url(job_id, api_html, view_html)

            # Final guard: discard if it somehow resolved to a LinkedIn URL
            if external_url and self._is_linkedin_internal(external_url):
                external_url = None

            # ── Filter: Reject if no external URL and no offsite apply indicator ──
            if not external_url and not has_offsite_apply_icon(soup, view_html or api_html):
                print(f"      ⏭️ [REJECTED] Job {job_id}: No external URL found (Easy Apply)")
                return None

            # ─────────────────────────────────────────────────────────────
            # FIELD EXTRACTION — Code A logic (util.py delegation)
            # ─────────────────────────────────────────────────────────────

            # Title
            title = job_data.get("title") if job_data else ""
            if not title:
                title_tag = soup.find("h1", class_="top-card-layout__title")
                title = title_tag.get_text(strip=True) if title_tag else "Unknown"

            # Company
            company = job_data.get("company") if job_data else ""
            if not company:
                company_tag = soup.find("a", class_="topcard__org-name-link")
                company = company_tag.get_text(strip=True) if company_tag else "Unknown"

            # Company logo — delegates to util.py
            # Both api_html and view_html passed so util searches JSON blobs
            # on both pages for logoUrl / company-logo CDN URLs.
            company_logo = extract_company_logo(soup, api_html=api_html, view_html=view_html)

            # Description
            # Tries view page soup first, then api page soup as fallback.
            # Covers all known LinkedIn class names (guest API + view page, 2024-2025).
            description = ""
            desc_selectors = [
                "div.show-more-less-html__markup",          # guest API page (primary)
                "div.description__text",                    # older guest API layout
                "div.jobs-description__content",            # view page layout A
                "div.decorated-job-posting__details",       # view page layout B
                "div.description__text--rich",              # view page layout C
                "div.job-description__content",             # some company-hosted layouts
                "div#job-details",                          # view page fallback
                "section.description",                      # section wrapper fallback
            ]
            # First pass: view soup
            for selector in desc_selectors:
                desc_tag = soup.select_one(selector)
                if desc_tag:
                    description = desc_tag.get_text(separator="\n", strip=True)
                    break

            # Second pass: api_html soup (if view page had nothing)
            if not description and api_html:
                api_soup_desc = BeautifulSoup(api_html, "html.parser")
                for selector in desc_selectors:
                    desc_tag = api_soup_desc.select_one(selector)
                    if desc_tag:
                        description = desc_tag.get_text(separator="\n", strip=True)
                        break

            # Third pass: JSON blob in either HTML (LinkedIn embeds description in JSON)
            if not description:
                for raw_html in [api_html, view_html]:
                    if not raw_html:
                        continue
                    import json as _json
                    # Try to extract description from embedded JSON
                    try:
                        m = re.search(
                            r'"description"\s*:\s*\{\s*"text"\s*:\s*"((?:[^"\\]|\\.)+)"',
                            raw_html
                        )
                        if m:
                            description = m.group(1).replace('\\n', '\n').replace('\\"', '"')
                            break
                    except Exception:
                        pass

            # Location
            location_str = job_data.get("location") if job_data else ""
            if not location_str:
                location_tag = soup.find("span", class_="topcard__flavor--bullet")
                if location_tag:
                    location_str = location_tag.get_text(strip=True)
            location = Location.from_string(location_str) if location_str else Location()
            search_loc = job_data.get("search_location") if job_data else None
            if search_loc:
                curr_country = getattr(location, "country", None)
                curr_c_str = str(getattr(curr_country, "value", curr_country) or "").strip().lower()
                if not curr_c_str or curr_c_str in ("unknown", "none"):
                    location.country = search_loc

            # Date posted
            # Tries all known LinkedIn date selectors across view + api pages.
            # Falls back to JSON blob extraction if no HTML tag found.
            date_posted = None

            # All known date tag selectors (confirmed across 2024-2025 layouts)
            date_tag = (
                soup.find("span", class_="posted-time-ago__text")           # guest API primary
                or soup.find("span", class_="topcard__flavor--bullet")      # older layout
                or soup.find("span", class_="jobs-top-card__posted-date")   # view page A
                or soup.find("time", attrs={"datetime": True})              # <time> element
                or soup.find("span", attrs={"class": lambda c: c and
                             any("posted" in x or "date" in x
                                 for x in (c if isinstance(c, list) else [c]))})
            )
            if date_tag:
                date_text = date_tag.get("datetime") or date_tag.get_text(strip=True)
                if date_text:
                    date_posted = parse_relative_date(date_text)

            # Fallback: JSON blob in api_html or view_html
            if not date_posted:
                for raw_html in [api_html, view_html]:
                    if not raw_html:
                        continue
                    try:
                        m = re.search(
                            r'"listedAt"\s*:\s*(\d+)',
                            raw_html
                        )
                        if m:
                            import datetime as _dt
                            ts = int(m.group(1)) / 1000  # LinkedIn uses ms timestamps
                            date_posted = _dt.datetime.utcfromtimestamp(ts).date()
                            break
                    except Exception:
                        pass

            # Job type
            # Pass 1: util.py HTML tag extraction (original logic)
            # Pass 2: JSON blob fallback — LinkedIn embeds "employment_type"
            #         in the guest API JSON (confirmed via research 2024-2025)
            job_type = parse_job_type(soup)
            if not job_type:
                for raw_html in [api_html, view_html]:
                    if not raw_html:
                        continue
                    try:
                        m = re.search(
                            r'"employment_?[Tt]ype"\s*:\s*"([^"]+)"', raw_html
                        )
                        if m:
                            et = m.group(1).lower().replace("-", "").replace(" ", "")
                            type_map = {
                                "fulltime":   JobType.FULL_TIME,
                                "parttime":   JobType.PART_TIME,
                                "contract":   JobType.CONTRACT,
                                "internship": JobType.INTERNSHIP,
                                "temporary":  JobType.TEMPORARY,
                            }
                            for key, val in type_map.items():
                                if key in et:
                                    job_type = [val]
                                    break
                        if job_type:
                            break
                    except Exception:
                        pass

            # Job level
            # Pass 1: util.py HTML tag extraction (original logic)
            # Pass 2: JSON blob fallback — LinkedIn embeds "seniority_level"
            job_level = parse_job_level(soup)
            if not job_level:
                for raw_html in [api_html, view_html]:
                    if not raw_html:
                        continue
                    try:
                        m = re.search(
                            r'"seniority_?[Ll]evel"\s*:\s*"([^"]+)"', raw_html
                        )
                        if m:
                            job_level = m.group(1).strip()
                            break
                    except Exception:
                        pass

            # Company industry
            # Pass 1: util.py HTML tag extraction (original logic)
            # Pass 2: JSON blob fallback — LinkedIn embeds "industries"
            company_industry = parse_company_industry(soup)
            if not company_industry:
                for raw_html in [api_html, view_html]:
                    if not raw_html:
                        continue
                    try:
                        # Matches both "industries":["Software Development"] and
                        # "industry":"Software Development"
                        m = re.search(
                            r'"industries?"\s*:\s*[\["]([^"\]]+)', raw_html
                        )
                        if m:
                            company_industry = m.group(1).strip().strip('"')
                            break
                    except Exception:
                        pass

            # Salary — Code A: delegates to util.py
            salary_min, salary_max, salary_text = parse_salary_from_text(
                description, view_html or api_html
            )

            # Experience
            # Pass 1: util.py description/html text parsing (original logic)
            # Pass 2: description-based keyword fallback if util returns None
            experience = parse_experience_from_text(description, view_html or api_html)
            if not experience and description:
                # Broader fallback: catch patterns util.py may have missed
                desc_lower = description.lower()
                try:
                    m = re.search(
                        r'(\d+)\+?\s*(?:to|-)\s*(\d+)\s*years?', desc_lower
                    ) or re.search(
                        r'(\d+)\+\s*years?', desc_lower
                    ) or re.search(
                        r'(\d+)\s*years?\s*(?:of\s+)?experience', desc_lower
                    )
                    if m:
                        if len(m.groups()) == 2:
                            experience = f"{m.group(1)}-{m.group(2)} years"
                        else:
                            experience = f"{m.group(1)}+ years"
                    elif "entry level" in desc_lower or "entry-level" in desc_lower:
                        experience = "Entry Level"
                    elif "no experience" in desc_lower or "fresh" in desc_lower:
                        experience = "Entry Level (0-2 years)"
                except Exception:
                    pass

            # Remote check — Code A: delegates to util.py
            is_remote = is_job_remote(title, description, location)

            # Skills / Requirements extraction
            skills = parse_skills_requirements(description, view_html or api_html)

            # Easy apply flag
            is_easy_apply = not external_url

            # Compensation object
            compensation = None
            if salary_min or salary_max:
                compensation = Compensation(
                    min_amount=salary_min,
                    max_amount=salary_max,
                    currency="USD",
                    interval="yearly",
                )

            # Search keyword
            search_keyword = job_data.get("keyword") if job_data else None

            # ── Build JobPost ─────────────────────────────────────────────
            job = JobPost(
                job_id=job_id,
                title=title,
                company_name=company,
                company_logo=company_logo,
                location=location,
                description=description[:10000] if description else None,
                date_posted=date_posted,
                job_url=job_view_url,
                apply_url=external_url,
                job_url_direct=external_url,
                job_type=job_type,
                job_level=job_level,
                company_industry=company_industry,
                is_remote=is_remote,
                is_easy_apply=is_easy_apply,
                compensation=compensation,
                emails=extract_emails_from_text(description or ""),
                search_keyword=search_keyword,
                experience=experience,
                salary_text=salary_text,
                skills=skills,
                sponsorship_h1b=None,
                source="l_i",
            )

            self._handle_success()

            if job.apply_url:
                print(
                    f"      📊 Extracted: Logo={bool(company_logo)}, "
                    f"Salary={salary_text}, JobType={job_type}, "
                    f"Level={job_level}, Experience={experience}, "
                    f"Skills={bool(skills)}"
                )

            return job

        except Exception as e:
            print(f"❌ Error fetching job {job_id}: {e}")
            self._handle_error()
            return None

    def _append_job_to_csv(self, filename: str, job: JobPost, lock: threading.Lock = None):
        """Append a single job with all attributes to CSV in real-time (thread-safe)."""
        import csv
        row = [
            job.job_id,
            job.title,
            job.company_name,
            job.company_logo or "",
            getattr(job, "company_url", "") or "",
            job.location.display_location() if job.location else "",
            job.location.city if job.location else "",
            job.location.state if job.location else "",
            job.location.country if job.location else "",
            str(job.date_posted) if job.date_posted else "",
            job.job_url or "",
            job.apply_url or "",
            job.is_remote,
            job.is_easy_apply,
            ", ".join(jt.value for jt in job.job_type) if job.job_type else "",
            job.job_level or "",
            job.company_industry or "",
            getattr(job, "job_function", "") or "",
            job.search_keyword or "",
            job.compensation.min_amount if job.compensation else "",
            job.compensation.max_amount if job.compensation else "",
            getattr(job, "salary_text", "") or "",
            getattr(job, "experience", "") or "",
            getattr(job, "skills", "") or "",
            getattr(job, "sponsorship_h1b", "") or "",
            getattr(job, "source", "l_i") or "l_i",
            ", ".join(job.emails) if job.emails else "",
            (job.description or "")[:500] if job.description else "",
        ]

        def _do_write():
            file_exists = os.path.isfile(filename)
            with open(filename, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow([
                        "Job ID", "Title", "Company", "Company Logo", "Company URL",
                        "Location", "Location City", "Location State", "Location Country",
                        "Date Posted", "Job URL", "External Apply URL", "Is Remote",
                        "Is Easy Apply", "Job Type", "Job Level", "Industry",
                        "Job Function", "Search Keyword", "Salary Min", "Salary Max",
                        "Salary Text", "Experience Required", "Skills / Requirements",
                        "Sponsorship H1B", "Source", "Emails", "Description Preview",
                    ])
                writer.writerow(row)

        if lock:
            with lock:
                _do_write()
        else:
            _do_write()

    # ─────────────────────────────────────────────────────────────────────────
    # BATCH SCRAPE  (structure from Code B + stats alignment)
    # ─────────────────────────────────────────────────────────────────────────

    def scrape_all_jobs_batch(self, keywords: List[str],
                              location: str = "United States",
                              max_workers: int = 15,
                              save_to_db: bool = True,
                              csv_filename: str = None,
                              max_jobs: Optional[int] = None,
                              max_jobs_per_keyword: Optional[int] = None) -> List[JobPost]:
        """
        Scrape ALL jobs posted in last 24 hours for multiple keywords in parallel.
        Stores all job data in a CSV file during scraping, and automatically uploads
        the CSV data directly into the database 'links' table upon scraping completion.
        """
        if max_jobs is None:
            env_max = os.getenv("MAX_JOBS")
            if env_max and env_max.strip().isdigit() and int(env_max) > 0:
                max_jobs = int(env_max)

        if max_jobs_per_keyword is None:
            env_kw_max = os.getenv("MAX_JOBS_PER_KEYWORD")
            if env_kw_max and env_kw_max.strip().isdigit() and int(env_kw_max) > 0:
                max_jobs_per_keyword = int(env_kw_max)
            else:
                max_jobs_per_keyword = 100

        if max_jobs:
            print(f"🎯 Target test job limit: {max_jobs} jobs across run")
        print(f"🎯 Per-keyword job limit: {max_jobs_per_keyword} jobs (last 24 hours)")

        all_jobs = []
        seen_global_ids = set()
        total_keywords = len(keywords)
        actual_workers = max(1, max_workers)

        if not csv_filename:
            csv_filename = f"scraped_jobs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        csv_lock = threading.Lock()
        print(f"📄 Local CSV buffer: {csv_filename} (saving all job data in real-time)")

        grand_external = 0
        grand_salary = 0
        grand_exp = 0
        saved_count = 0
        duplicate_count = 0
        rejected_count = 0

        if save_to_db and not (self.db and self.db.initialized):
            print("\n⚠️ Supabase not initialised — DB saves will be skipped")
            save_to_db = False

        for idx, keyword in enumerate(keywords):
            if max_jobs and len(all_jobs) >= max_jobs:
                break

            print(f"\n{'='*60}")
            print(f"🔍 [{idx+1}/{total_keywords}] Keyword: '{keyword}' | Location: '{location}'")
            print(f"{'='*60}")

            # Fetch candidate jobs posted in last 24h (buffer up to 1.5x of per-keyword limit to account for easy-apply/rejected jobs)
            search_limit = int(max_jobs_per_keyword * 1.5)
            if max_jobs:
                search_limit = min(search_limit, max((max_jobs - len(all_jobs)) * 3, 25))

            raw_jobs = self.search_all_jobs(keyword, location, hours_old=24, max_results=search_limit)

            keyword_results = []
            for job in raw_jobs:
                if job["job_id"] not in seen_global_ids:
                    seen_global_ids.add(job["job_id"])
                    job["keyword"] = keyword
                    job["search_location"] = location
                    keyword_results.append(job)

            print(f"   📋 {len(keyword_results)} unique new jobs to fetch for '{keyword}' (target: up to {max_jobs_per_keyword})")

            if not keyword_results:
                if idx < total_keywords - 1:
                    delay = int(os.getenv("KEYWORD_DELAY", "30"))
                    print(f"   ⏱️  Waiting {delay}s before next keyword rotation...")
                    time.sleep(delay)
                continue

            print(f"   🔗 Fetching details and saving in REAL-TIME "
                  f"({actual_workers} workers)...")

            keyword_jobs = []
            external_count = 0
            salary_count = 0
            exp_count = 0
            completed = 0
            kw_total = len(keyword_results)
            keyword_saved = 0

            with ThreadPoolExecutor(max_workers=actual_workers) as executor:
                future_to_job = {
                    executor.submit(self.get_job_details, j["job_id"], j): j
                    for j in keyword_results
                }

                for future in as_completed(future_to_job):
                    completed += 1
                    src_job = future_to_job[future]

                    if completed % 25 == 0 or completed == 1 or completed == kw_total:
                        print(
                            f"   Progress: {completed}/{kw_total} "
                            f"({completed / kw_total * 100:.0f}%) | "
                            f"external={external_count} | saved={saved_count} | "
                            f"rejected={rejected_count}"
                        )

                    try:
                        job_post = future.result(timeout=15)
                        if job_post:
                            keyword_jobs.append(job_post)
                            all_jobs.append(job_post)

                            # ── 1. Store complete job data in CSV file in real-time ──
                            self._append_job_to_csv(csv_filename, job_post, csv_lock)

                            if job_post.apply_url:
                                external_count += 1
                            if job_post.compensation and job_post.compensation.min_amount:
                                salary_count += 1
                            if job_post.experience:
                                exp_count += 1

                            if len(keyword_jobs) >= max_jobs_per_keyword:
                                print(f"\n🎯 Reached per-keyword limit ({len(keyword_jobs)}/{max_jobs_per_keyword} jobs) for '{keyword}'!")
                                for f in future_to_job:
                                    f.cancel()
                                break

                            if max_jobs and len(all_jobs) >= max_jobs:
                                print(f"\n🎯 Reached target job limit ({len(all_jobs)}/{max_jobs} jobs)!")
                                for f in future_to_job:
                                    f.cancel()
                                break
                        else:
                            rejected_count += 1

                    except Exception as e:
                        print(f"   ✗ {src_job['job_id']}: {e}")

            # ── 2. Automatically store CSV data in the database 'links' table ──
            if save_to_db and self.db and self.db.initialized and keyword_jobs:
                print(
                    f"\n💾 [CSV -> DATABASE] Scraping completed for '{keyword}'. "
                    f"Automatically storing {len(keyword_jobs)} jobs from CSV to Neon DB '{self.db.table_name}' table..."
                )
                batch_dicts = [j.to_supabase_dict() for j in keyword_jobs]
                db_results = self.db.save_jobs_batch(batch_dicts)
                keyword_saved = db_results.get("success", 0)
                saved_count += keyword_saved
                duplicate_count += db_results.get("duplicate", 0)
                print(
                    f"   ✅ Auto-store complete: {keyword_saved}/{len(keyword_jobs)} jobs saved to '{self.db.table_name}' table"
                )

            grand_external += external_count
            grand_salary += salary_count
            grand_exp += exp_count

            print(
                f"   ✅ [{idx+1}/{total_keywords}] '{keyword}' done | "
                f"jobs={len(keyword_jobs)} external={external_count} | "
                f"saved={keyword_saved}"
            )

            if max_jobs and len(all_jobs) >= max_jobs:
                print(f"🎯 Target limit of {max_jobs} jobs reached. Completing scrape.")
                break

            if idx < total_keywords - 1:
                delay = int(os.getenv("KEYWORD_DELAY", "30"))
                print(f"   ⏱️  Waiting {delay}s before next keyword rotation...")
                time.sleep(delay)

        # ── Final summary ─────────────────────────────────────────────────────
        print(f"\n{'='*60}")
        print("✅ SCRAPE COMPLETE")
        print(f"{'='*60}")
        if all_jobs:
            pct = grand_external / len(all_jobs) * 100
            print(f"📊 Total jobs processed : {len(all_jobs)}")
            print(f"🔗 External links found : {grand_external} ({pct:.1f}%)")
            print(f"⏭️ Rejected (no <icon>) : {rejected_count}")
            print(f"💰 Jobs with salary info: {grand_salary}")
            print(f"📝 Jobs with experience : {grand_exp}")
            if save_to_db:
                print(f"💾 IMMEDIATE SAVES      : {saved_count} new jobs saved")
                print(f"🔄 Duplicates skipped   : {duplicate_count}")

        return all_jobs

    # ─────────────────────────────────────────────────────────────────────────
    # CSV EXPORT  (unchanged — identical in both A and B)
    # ─────────────────────────────────────────────────────────────────────────

    def save_to_csv(self, jobs: List[JobPost], filename: str = None):
        """Save jobs to CSV file with enhanced fields."""
        if not filename:
            filename = f"linkedin_jobs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        import csv
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Job ID", "Title", "Company", "Company Logo", "Company URL",
                "Location", "Location City", "Location State", "Location Country",
                "Date Posted", "Job URL", "External Apply URL", "Is Remote",
                "Is Easy Apply", "Job Type", "Job Level", "Industry",
                "Job Function", "Search Keyword", "Salary Min", "Salary Max",
                "Salary Text", "Experience Required", "Skills / Requirements",
                "Sponsorship H1B", "Source", "Emails", "Description Preview",
            ])
            for job in jobs:
                writer.writerow([
                    job.job_id,
                    job.title,
                    job.company_name,
                    job.company_logo or "",
                    getattr(job, "company_url", "") or "",
                    job.location.display_location() if job.location else "",
                    job.location.city if job.location else "",
                    job.location.state if job.location else "",
                    job.location.country if job.location else "",
                    str(job.date_posted) if job.date_posted else "",
                    job.job_url or "",
                    job.apply_url or "",
                    job.is_remote,
                    job.is_easy_apply,
                    ", ".join(jt.value for jt in job.job_type) if job.job_type else "",
                    job.job_level or "",
                    job.company_industry or "",
                    getattr(job, "job_function", "") or "",
                    job.search_keyword or "",
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

        print(f"💾 Saved {len(jobs)} jobs to {filename}")

    def upload_csv_to_db(self, csv_filename: str) -> Dict[str, int]:
        """Read all rows from a CSV file and store them into the database table."""
        if not self.db or not self.db.initialized:
            print("⚠️ Database not initialized — cannot upload CSV to DB")
            return {"success": 0, "failed": 0, "duplicate": 0}

        import csv
        if not os.path.isfile(csv_filename):
            print(f"❌ CSV file '{csv_filename}' not found.")
            return {"success": 0, "failed": 0, "duplicate": 0}

        job_dicts = []
        with open(csv_filename, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                d = {
                    "job_id": r.get("Job ID"),
                    "title": r.get("Title"),
                    "company_name": r.get("Company"),
                    "company_logo": r.get("Company Logo") or None,
                    "company_url": r.get("Company URL") or None,
                    "location_display": r.get("Location") or None,
                    "location_city": r.get("Location City") or None,
                    "location_state": r.get("Location State") or None,
                    "location_country": r.get("Location Country") or None,
                    "date_posted": r.get("Date Posted") or None,
                    "job_url": r.get("Job URL") or None,
                    "apply_url": r.get("External Apply URL") or None,
                    "is_remote": r.get("Is Remote") == "True",
                    "is_easy_apply": r.get("Is Easy Apply") == "True",
                    "job_type": r.get("Job Type") or None,
                    "job_level": r.get("Job Level") or None,
                    "company_industry": r.get("Industry") or None,
                    "job_function": r.get("Job Function") or None,
                    "search_keyword": r.get("Search Keyword") or None,
                    "compensation_min": float(r.get("Salary Min")) if r.get("Salary Min") else None,
                    "compensation_max": float(r.get("Salary Max")) if r.get("Salary Max") else None,
                    "salary_text": r.get("Salary Text") or None,
                    "experience": r.get("Experience Required") or None,
                    "skills": r.get("Skills / Requirements") or None,
                    "sponsorship_h1b": r.get("Sponsorship H1B") or None,
                    "source": r.get("Source") or "l_i",
                    "emails": r.get("Emails") or None,
                    "description": r.get("Description Preview") or None,
                }
                job_dicts.append(d)

        print(f"💾 Uploading {len(job_dicts)} jobs from '{csv_filename}' to Neon DB '{self.db.table_name}' table...")
        return self.db.save_jobs_batch(job_dicts)