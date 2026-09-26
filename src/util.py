# """Utility functions for LinkedIn scraper"""

# import re
# import random
# import time
# from datetime import datetime, timedelta, date
# from typing import Optional, List
# from urllib.parse import unquote

# from bs4 import BeautifulSoup
# import requests

# from .models import JobType, Location


# def job_type_code(job_type_enum: JobType) -> str:
#     """Convert JobType enum to LinkedIn job type code"""
#     return {
#         JobType.FULL_TIME: "F",
#         JobType.PART_TIME: "P",
#         JobType.INTERNSHIP: "I",
#         JobType.CONTRACT: "C",
#         JobType.TEMPORARY: "T",
#     }.get(job_type_enum, "")


# def parse_job_type(soup: BeautifulSoup) -> Optional[List[JobType]]:
#     """Extract job type from job page"""
#     h3_tag = soup.find(
#         "h3",
#         class_="description__job-criteria-subheader",
#         string=lambda text: text and "Employment type" in text,
#     )
    
#     if not h3_tag:
#         return None
        
#     employment_type_span = h3_tag.find_next_sibling(
#         "span",
#         class_="description__job-criteria-text description__job-criteria-text--criteria",
#     )
    
#     if not employment_type_span:
#         return None
        
#     employment_type = employment_type_span.get_text(strip=True).lower().replace("-", "")
    
#     type_map = {
#         "fulltime": JobType.FULL_TIME,
#         "full time": JobType.FULL_TIME,
#         "parttime": JobType.PART_TIME,
#         "part time": JobType.PART_TIME,
#         "contract": JobType.CONTRACT,
#         "internship": JobType.INTERNSHIP,
#         "temporary": JobType.TEMPORARY,
#     }
    
#     for key, value in type_map.items():
#         if key in employment_type:
#             return [value]
    
#     return None


# def parse_job_level(soup: BeautifulSoup) -> Optional[str]:
#     """Extract job level/seniority from job page"""
#     h3_tag = soup.find(
#         "h3",
#         class_="description__job-criteria-subheader",
#         string=lambda text: text and "Seniority level" in text,
#     )
    
#     if not h3_tag:
#         return None
        
#     job_level_span = h3_tag.find_next_sibling(
#         "span",
#         class_="description__job-criteria-text description__job-criteria-text--criteria",
#     )
    
#     return job_level_span.get_text(strip=True) if job_level_span else None


# def parse_company_industry(soup: BeautifulSoup) -> Optional[str]:
#     """Extract company industry from job page"""
#     h3_tag = soup.find(
#         "h3",
#         class_="description__job-criteria-subheader",
#         string=lambda text: text and "Industries" in text,
#     )
    
#     if not h3_tag:
#         return None
        
#     industry_span = h3_tag.find_next_sibling(
#         "span",
#         class_="description__job-criteria-text description__job-criteria-text--criteria",
#     )
    
#     return industry_span.get_text(strip=True) if industry_span else None


# def is_job_remote(title: str, description: str, location: Location) -> bool:
#     """Check if job is remote based on title, description, and location"""
#     remote_keywords = ["remote", "work from home", "wfh", "virtual", "telecommute", "hybrid"]
    
#     location_str = location.display_location().lower() if location else ""
#     title_lower = title.lower() if title else ""
#     description_lower = description.lower() if description else ""
    
#     full_string = f"{title_lower} {description_lower} {location_str}"
    
#     return any(keyword in full_string for keyword in remote_keywords)


# def extract_external_url_from_html(html: str, job_id: str) -> Optional[str]:
#     """Extract external apply URL from raw HTML using multiple methods"""
#     if not html or not job_id:
#         return None
    
#     # Method 1: Look for applyUrl code block
#     code_pattern = r'<code\s+id="applyUrl"[^>]*>(.*?)</code>'
#     code_match = re.search(code_pattern, html, re.IGNORECASE | re.DOTALL)
    
#     if code_match:
#         code_content = code_match.group(1)
        
#         # Look for URL in HTML comments
#         comment_pattern = r'<!--\s*"([^"]+)"\s*-->'
#         comment_match = re.search(comment_pattern, code_content)
#         if comment_match:
#             url_candidate = comment_match.group(1)
            
#             # Extract url parameter
#             url_param_match = re.search(r'url=([^&\s]+)', url_candidate)
#             if url_param_match:
#                 encoded_url = url_param_match.group(1)
#                 decoded_url = unquote(encoded_url)
                
#                 # Skip LinkedIn internal pages
#                 if decoded_url and 'linkedin.com' not in decoded_url.lower() and not any(x in decoded_url.lower() for x in ['signup', 'login', 'auth']):
#                     return decoded_url.split('&urlHash=')[0]
    
#     # Method 2: Look for externalApply pattern
#     ext_apply_pattern = rf'externalApply/{job_id}\?url=([^"&\s>]+)'
#     ext_match = re.search(ext_apply_pattern, html, re.IGNORECASE)
    
#     if ext_match:
#         encoded_url = ext_match.group(1)
#         decoded_url = unquote(encoded_url)
#         if decoded_url and 'linkedin.com' not in decoded_url.lower():
#             return decoded_url.split('&urlHash=')[0]
    
#     return None


# def extract_emails_from_text(text: str) -> List[str]:
#     """Extract email addresses from text"""
#     if not text:
#         return []
    
#     email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
#     return re.findall(email_pattern, text)


# def parse_relative_date(date_text: str) -> Optional[date]:
#     """Parse relative date strings like '2 days ago'"""
#     if not date_text:
#         return None
    
#     today = date.today()
#     date_text = date_text.lower()
    
#     if 'just posted' in date_text or 'moments ago' in date_text:
#         return today
    
#     # Hours ago
#     hours_match = re.search(r'(\d+)\s*hours?\s*ago', date_text)
#     if hours_match:
#         hours = int(hours_match.group(1))
#         return today - timedelta(hours=hours)
    
#     # Minutes ago
#     minutes_match = re.search(r'(\d+)\s*minutes?\s*ago', date_text)
#     if minutes_match:
#         minutes = int(minutes_match.group(1))
#         return today - timedelta(minutes=minutes)
    
#     # Days ago
#     days_match = re.search(r'(\d+)\s*days?\s*ago', date_text)
#     if days_match:
#         days = int(days_match.group(1))
#         return today - timedelta(days=days)
    
#     # Weeks ago
#     weeks_match = re.search(r'(\d+)\s*weeks?\s*ago', date_text)
#     if weeks_match:
#         weeks = int(weeks_match.group(1))
#         return today - timedelta(days=weeks*7)
    
#     return None


# def currency_parser(salary_text: str) -> Optional[float]:
#     """Parse salary amount from text"""
#     if not salary_text:
#         return None
    
#     # Remove currency symbols and commas
#     cleaned = re.sub(r'[$,€£¥]', '', salary_text)
    
#     # Extract numbers
#     numbers = re.findall(r'(\d+(?:\.\d+)?)', cleaned)
    
#     if numbers:
#         return float(numbers[0])
    
#     return None


# def create_session(proxies=None, ca_cert=None):
#     """Create a requests session with retry logic"""
#     session = requests.Session()
    
#     if proxies:
#         if isinstance(proxies, list):
#             session.proxies = {"http": proxies[0], "https": proxies[0]}
#         else:
#             session.proxies = {"http": proxies, "https": proxies}
    
#     return session


# def remove_attributes(soup: BeautifulSoup, keep_tags=None) -> BeautifulSoup:
#     """Remove all attributes from HTML tags except those in keep_tags"""
#     if keep_tags is None:
#         keep_tags = []
    
#     for tag in soup.find_all(True):
#         if tag.name not in keep_tags:
#             tag.attrs = {}
    
#     return soup































# """Utility functions for LinkedIn scraper"""

# import re
# import random
# import time
# from datetime import datetime, timedelta, date
# from typing import Optional, List, Tuple
# from urllib.parse import unquote

# from bs4 import BeautifulSoup
# import requests

# from .models import JobType, Location


# def job_type_code(job_type_enum: JobType) -> str:
#     """Convert JobType enum to LinkedIn job type code"""
#     return {
#         JobType.FULL_TIME: "F",
#         JobType.PART_TIME: "P",
#         JobType.INTERNSHIP: "I",
#         JobType.CONTRACT: "C",
#         JobType.TEMPORARY: "T",
#     }.get(job_type_enum, "")


# def parse_job_type(soup: BeautifulSoup) -> Optional[List[JobType]]:
#     """Extract job type from job page"""
#     h3_tag = soup.find(
#         "h3",
#         class_="description__job-criteria-subheader",
#         string=lambda text: text and "Employment type" in text,
#     )
    
#     if not h3_tag:
#         return None
        
#     employment_type_span = h3_tag.find_next_sibling(
#         "span",
#         class_="description__job-criteria-text description__job-criteria-text--criteria",
#     )
    
#     if not employment_type_span:
#         return None
        
#     employment_type = employment_type_span.get_text(strip=True).lower().replace("-", "")
    
#     type_map = {
#         "fulltime": JobType.FULL_TIME,
#         "full time": JobType.FULL_TIME,
#         "parttime": JobType.PART_TIME,
#         "part time": JobType.PART_TIME,
#         "contract": JobType.CONTRACT,
#         "internship": JobType.INTERNSHIP,
#         "temporary": JobType.TEMPORARY,
#     }
    
#     for key, value in type_map.items():
#         if key in employment_type:
#             return [value]
    
#     return None


# def parse_job_level(soup: BeautifulSoup) -> Optional[str]:
#     """Extract job level/seniority from job page"""
#     h3_tag = soup.find(
#         "h3",
#         class_="description__job-criteria-subheader",
#         string=lambda text: text and "Seniority level" in text,
#     )
    
#     if not h3_tag:
#         return None
        
#     job_level_span = h3_tag.find_next_sibling(
#         "span",
#         class_="description__job-criteria-text description__job-criteria-text--criteria",
#     )
    
#     return job_level_span.get_text(strip=True) if job_level_span else None


# def parse_company_industry(soup: BeautifulSoup) -> Optional[str]:
#     """Extract company industry from job page"""
#     h3_tag = soup.find(
#         "h3",
#         class_="description__job-criteria-subheader",
#         string=lambda text: text and "Industries" in text,
#     )
    
#     if not h3_tag:
#         return None
        
#     industry_span = h3_tag.find_next_sibling(
#         "span",
#         class_="description__job-criteria-text description__job-criteria-text--criteria",
#     )
    
#     return industry_span.get_text(strip=True) if industry_span else None


# def is_job_remote(title: str, description: str, location: Location) -> bool:
#     """Check if job is remote based on title, description, and location"""
#     remote_keywords = ["remote", "work from home", "wfh", "virtual", "telecommute", "hybrid"]
    
#     location_str = location.display_location().lower() if location else ""
#     title_lower = title.lower() if title else ""
#     description_lower = description.lower() if description else ""
    
#     full_string = f"{title_lower} {description_lower} {location_str}"
    
#     return any(keyword in full_string for keyword in remote_keywords)


# def extract_company_logo(soup: BeautifulSoup) -> Optional[str]:
#     """Extract company logo URL from job page"""
#     try:
#         # Look for logo image
#         logo_selectors = [
#             'img.artdeco-entity-image',
#             'img.presence-entity__image',
#             'img[data-delayed-url]',
#             'img.ivm-view-attr__img--centered'
#         ]
        
#         for selector in logo_selectors:
#             logo_img = soup.select_one(selector)
#             if logo_img:
#                 # Try different attributes where URL might be stored
#                 for attr in ['src', 'data-delayed-url', 'data-src']:
#                     if logo_img.get(attr):
#                         url = logo_img[attr]
#                         if url and url.startswith('http') and 'ghost' not in url.lower():
#                             return url
#     except:
#         pass
    
#     return None


# def parse_salary_from_text(description: str, html: str = "") -> Tuple[Optional[float], Optional[float], Optional[str]]:
#     """
#     Extract salary min, max, and full text from job description
#     Returns (min_amount, max_amount, salary_text)
#     """
#     # Combine description and HTML for searching
#     full_text = f"{description} {html}".lower()
    
#     # Common salary patterns
#     salary_patterns = [
#         # $100,000 - $120,000
#         r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*[-–]\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
#         # $100k - $120k
#         r'\$(\d{1,3})k\s*[-–]\s*\$?(\d{1,3})k',
#         # $100,000/year
#         r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:per|/)\s*(?:year|annum|yr)',
#         # $100k/year
#         r'\$(\d{1,3})k\s*(?:per|/)\s*(?:year|annum|yr)',
#         # $100,000 - 120,000
#         r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*[-–]\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
#     ]
    
#     for pattern in salary_patterns:
#         matches = re.findall(pattern, full_text, re.IGNORECASE)
#         if matches:
#             match = matches[0]
#             if isinstance(match, tuple) and len(match) >= 2:
#                 # Range pattern
#                 try:
#                     min_val = float(match[0].replace(',', ''))
#                     max_val = float(match[1].replace(',', ''))
#                     # Handle K notation
#                     if 'k' in pattern.lower():
#                         min_val *= 1000
#                         max_val *= 1000
#                     return min_val, max_val, f"${min_val:,.0f} - ${max_val:,.0f}"
#                 except:
#                     pass
#             elif isinstance(match, str):
#                 # Single value pattern
#                 try:
#                     val = float(match.replace(',', ''))
#                     return val, val, f"${val:,.0f}"
#                 except:
#                     pass
    
#     return None, None, None


# def parse_experience_from_text(description: str, html: str = "") -> Optional[str]:
#     """Extract experience requirements from job description"""
#     full_text = f"{description} {html}".lower()
    
#     experience_patterns = [
#         # X-Y years
#         r'(\d+)[\s-]+(\d+)\s+years?\s*(?:of)?\s*experience',
#         # X+ years
#         r'(\d+)[\+]?\s*(?:\+)?\s*years?\s*(?:of)?\s*experience',
#         # Minimum X years
#         r'minimum\s*(?:of)?\s*(\d+)\s*years?',
#         # At least X years
#         r'at\s*least\s*(\d+)\s*years?',
#         # X years required
#         r'(\d+)\s*years?\s*(?:of)?\s*(?:experience)?\s*required',
#         # Entry level (0 years)
#         r'(?:entry\s*level|fresher|no\s*experience)',
#     ]
    
#     for pattern in experience_patterns:
#         match = re.search(pattern, full_text, re.IGNORECASE)
#         if match:
#             if 'entry' in pattern or 'fresher' in pattern:
#                 return "Entry Level (0-2 years)"
            
#             if len(match.groups()) == 2:
#                 # Range found
#                 return f"{match.group(1)}-{match.group(2)} years"
#             elif len(match.groups()) == 1:
#                 # Single number found
#                 return f"{match.group(1)}+ years"
    
#     return None


# def extract_external_url_from_html(html: str, job_id: str) -> Optional[str]:
#     """
#     Extract external apply URL from raw HTML using multiple methods
#     """
#     if not html or not job_id:
#         return None
    
#     # Method 1: Look for applyUrl code block
#     code_pattern = r'<code\s+id="applyUrl"[^>]*>(.*?)</code>'
#     code_match = re.search(code_pattern, html, re.IGNORECASE | re.DOTALL)
    
#     if code_match:
#         code_content = code_match.group(1)
        
#         # Look for URL in HTML comments
#         comment_pattern = r'<!--\s*"([^"]+)"\s*-->'
#         comment_match = re.search(comment_pattern, code_content)
#         if comment_match:
#             url_candidate = comment_match.group(1)
            
#             # Extract url parameter
#             url_param_match = re.search(r'url=([^&\s]+)', url_candidate)
#             if url_param_match:
#                 encoded_url = url_param_match.group(1)
#                 decoded_url = unquote(encoded_url)
                
#                 # Skip LinkedIn internal pages
#                 if decoded_url and 'linkedin.com' not in decoded_url.lower() and not any(x in decoded_url.lower() for x in ['signup', 'login', 'auth']):
#                     return decoded_url.split('&urlHash=')[0]
    
#     # Method 2: Look for externalApply pattern
#     ext_apply_pattern = rf'externalApply/{job_id}\?url=([^"&\s>]+)'
#     ext_match = re.search(ext_apply_pattern, html, re.IGNORECASE)
    
#     if ext_match:
#         encoded_url = ext_match.group(1)
#         decoded_url = unquote(encoded_url)
#         if decoded_url and 'linkedin.com' not in decoded_url.lower():
#             return decoded_url.split('&urlHash=')[0]
    
#     return None


# def extract_emails_from_text(text: str) -> List[str]:
#     """Extract email addresses from text"""
#     if not text:
#         return []
    
#     email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
#     return re.findall(email_pattern, text)


# def parse_relative_date(date_text: str) -> Optional[date]:
#     """Parse relative date strings like '2 days ago'"""
#     if not date_text:
#         return None
    
#     today = date.today()
#     date_text = date_text.lower()
    
#     if 'just posted' in date_text or 'moments ago' in date_text:
#         return today
    
#     # Hours ago
#     hours_match = re.search(r'(\d+)\s*hours?\s*ago', date_text)
#     if hours_match:
#         hours = int(hours_match.group(1))
#         return today - timedelta(hours=hours)
    
#     # Minutes ago
#     minutes_match = re.search(r'(\d+)\s*minutes?\s*ago', date_text)
#     if minutes_match:
#         minutes = int(minutes_match.group(1))
#         return today - timedelta(minutes=minutes)
    
#     # Days ago
#     days_match = re.search(r'(\d+)\s*days?\s*ago', date_text)
#     if days_match:
#         days = int(days_match.group(1))
#         return today - timedelta(days=days)
    
#     # Weeks ago
#     weeks_match = re.search(r'(\d+)\s*weeks?\s*ago', date_text)
#     if weeks_match:
#         weeks = int(weeks_match.group(1))
#         return today - timedelta(days=weeks*7)
    
#     return None


# def currency_parser(salary_text: str) -> Optional[float]:
#     """Parse salary amount from text"""
#     if not salary_text:
#         return None
    
#     # Remove currency symbols and commas
#     cleaned = re.sub(r'[$,€£¥]', '', salary_text)
    
#     # Extract numbers
#     numbers = re.findall(r'(\d+(?:\.\d+)?)', cleaned)
    
#     if numbers:
#         return float(numbers[0])
    
#     return None


# def create_session(proxies=None, ca_cert=None, cookie=None):
#     """Create a requests session with retry logic"""
#     session = requests.Session()
    
#     if cookie:
#         session.cookies.set("li_at", cookie, domain=".linkedin.com")
    
#     if proxies:
#         if isinstance(proxies, list):
#             session.proxies = {"http": proxies[0], "https": proxies[0]}
#         else:
#             session.proxies = {"http": proxies, "https": proxies}
    
#     return session


# def remove_attributes(soup: BeautifulSoup, keep_tags=None) -> BeautifulSoup:
#     """Remove all attributes from HTML tags except those in keep_tags"""
#     if keep_tags is None:
#         keep_tags = []
    
#     for tag in soup.find_all(True):
#         if tag.name not in keep_tags:
#             tag.attrs = {}
    
#     return soup













































# """Utility functions for LinkedIn scraper"""

# import re
# import random
# import time
# from datetime import datetime, timedelta, date
# from typing import Optional, List, Tuple
# from urllib.parse import unquote

# from bs4 import BeautifulSoup
# import requests

# from .models import JobType, Location


# def job_type_code(job_type_enum: JobType) -> str:
#     """Convert JobType enum to LinkedIn job type code"""
#     return {
#         JobType.FULL_TIME: "F",
#         JobType.PART_TIME: "P",
#         JobType.INTERNSHIP: "I",
#         JobType.CONTRACT: "C",
#         JobType.TEMPORARY: "T",
#     }.get(job_type_enum, "")


# def parse_job_type(soup: BeautifulSoup) -> Optional[List[JobType]]:
#     """Extract job type from job page"""
#     h3_tag = soup.find(
#         "h3",
#         class_="description__job-criteria-subheader",
#         string=lambda text: text and "Employment type" in text,
#     )

#     if not h3_tag:
#         return None

#     employment_type_span = h3_tag.find_next_sibling(
#         "span",
#         class_="description__job-criteria-text description__job-criteria-text--criteria",
#     )

#     if not employment_type_span:
#         return None

#     employment_type = employment_type_span.get_text(strip=True).lower().replace("-", "")

#     type_map = {
#         "fulltime": JobType.FULL_TIME,
#         "full time": JobType.FULL_TIME,
#         "parttime": JobType.PART_TIME,
#         "part time": JobType.PART_TIME,
#         "contract": JobType.CONTRACT,
#         "internship": JobType.INTERNSHIP,
#         "temporary": JobType.TEMPORARY,
#     }

#     for key, value in type_map.items():
#         if key in employment_type:
#             return [value]

#     return None


# def parse_job_level(soup: BeautifulSoup) -> Optional[str]:
#     """Extract job level/seniority from job page"""
#     h3_tag = soup.find(
#         "h3",
#         class_="description__job-criteria-subheader",
#         string=lambda text: text and "Seniority level" in text,
#     )

#     if not h3_tag:
#         return None

#     job_level_span = h3_tag.find_next_sibling(
#         "span",
#         class_="description__job-criteria-text description__job-criteria-text--criteria",
#     )

#     return job_level_span.get_text(strip=True) if job_level_span else None


# def parse_company_industry(soup: BeautifulSoup) -> Optional[str]:
#     """Extract company industry from job page"""
#     h3_tag = soup.find(
#         "h3",
#         class_="description__job-criteria-subheader",
#         string=lambda text: text and "Industries" in text,
#     )

#     if not h3_tag:
#         return None

#     industry_span = h3_tag.find_next_sibling(
#         "span",
#         class_="description__job-criteria-text description__job-criteria-text--criteria",
#     )

#     return industry_span.get_text(strip=True) if industry_span else None


# def is_job_remote(title: str, description: str, location: Location) -> bool:
#     """Check if job is remote based on title, description, and location"""
#     remote_keywords = ["remote", "work from home", "wfh", "virtual", "telecommute", "hybrid"]

#     location_str = location.display_location().lower() if location else ""
#     title_lower = title.lower() if title else ""
#     description_lower = description.lower() if description else ""

#     full_string = f"{title_lower} {description_lower} {location_str}"

#     return any(keyword in full_string for keyword in remote_keywords)


# def extract_company_logo(soup: BeautifulSoup,
#                          api_html: str = "",
#                          view_html: str = "") -> Optional[str]:
#     """
#     Extract company logo URL from job page.

#     CHANGES:
#     - api_html: searches LinkedIn's embedded JSON blob in <code> tags (guest API page)
#     - view_html: searches the view page HTML for logoUrl and company-logo CDN URLs
#     - Original img-tag selectors kept as fallback, unchanged.
#     Search order: api_html -> view_html -> img tags -> og:image meta
#     """

#     # ── METHOD 0: JSON blob search across BOTH api_html and view_html ─────────
#     # LinkedIn embeds job data as JSON inside <code> tags on both pages.
#     # JSON contains "logoUrl":"https://media.licdn.com/dms/image/.../company-logo_..."
#     for label, raw_html in [("api", api_html), ("view", view_html)]:
#         if not raw_html:
#             continue

#         # Step A: search inside <code> blocks (entities unescaped first)
#         try:
#             code_blocks = re.findall(r'<code[^>]*>(.*?)</code>', raw_html, re.DOTALL)
#             for block in code_blocks:
#                 block = (block
#                          .replace('&quot;', '"')
#                          .replace('&amp;', '&')
#                          .replace('&#39;', "'"))
#                 logo_match = re.search(
#                     r'"logoUrl"\s*:\s*"(https://media\.licdn\.com/[^"]+)"',
#                     block
#                 )
#                 if logo_match:
#                     url = logo_match.group(1)
#                     if url and 'ghost' not in url.lower() and 'blank' not in url.lower():
#                         return url
#         except Exception:
#             pass

#         # Step B: direct regex on full raw HTML (catches escaped \/ variants)
#         try:
#             # Primary: logoUrl key anywhere in HTML
#             logo_match = re.search(
#                 r'"logoUrl"\s*:\s*"(https://media\.licdn\.com/[^"\\]+)"',
#                 raw_html
#             )
#             if logo_match:
#                 url = logo_match.group(1).replace('\\/', '/')
#                 if url and 'ghost' not in url.lower() and 'blank' not in url.lower():
#                     return url

#             # Secondary: any company-logo CDN URL present anywhere in the page
#             # Format confirmed: media.licdn.com/dms/image/.../company-logo_NxN/...
#             logo_match = re.search(
#                 r'(https://media\.licdn\.com/dms/image/[^"\'\\,\s]+/company-logo[^"\'\\,\s]+)',
#                 raw_html
#             )
#             if logo_match:
#                 url = logo_match.group(1).replace('\\/', '/')
#                 if url and 'ghost' not in url.lower() and 'blank' not in url.lower():
#                     return url
#         except Exception:
#             pass

#     # ── METHOD 1: img tag selectors (original logic — unchanged) ─────────────
#     try:
#         logo_selectors = [
#             'img.artdeco-entity-image',
#             'img.presence-entity__image',
#             'img[data-delayed-url]',
#             'img.ivm-view-attr__img--centered',
#         ]

#         for selector in logo_selectors:
#             logo_img = soup.select_one(selector)
#             if logo_img:
#                 for attr in ['src', 'data-delayed-url', 'data-src']:
#                     if logo_img.get(attr):
#                         url = logo_img[attr]
#                         if url and url.startswith('http') and 'ghost' not in url.lower():
#                             return url
#     except Exception:
#         pass

#     # ── METHOD 2: og:image meta tag fallback ─────────────────────────────────
#     try:
#         logo_meta = soup.find('meta', {'property': 'og:image'})
#         if logo_meta and logo_meta.get('content'):
#             url = logo_meta['content']
#             if url and url.startswith('http') and 'ghost' not in url.lower():
#                 return url
#     except Exception:
#         pass

#     return None



# def parse_salary_from_text(
#     description: str, html: str = ""
# ) -> Tuple[Optional[float], Optional[float], Optional[str]]:
#     """
#     Extract salary min, max, and full text from job description.
#     Returns (min_amount, max_amount, salary_text)
#     """
#     full_text = f"{description} {html}".lower()

#     salary_patterns = [
#         r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*[-–]\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
#         r'\$(\d{1,3})k\s*[-–]\s*\$?(\d{1,3})k',
#         r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:per|/)\s*(?:year|annum|yr)',
#         r'\$(\d{1,3})k\s*(?:per|/)\s*(?:year|annum|yr)',
#         r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*[-–]\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
#     ]

#     for pattern in salary_patterns:
#         matches = re.findall(pattern, full_text, re.IGNORECASE)
#         if matches:
#             match = matches[0]
#             if isinstance(match, tuple) and len(match) >= 2:
#                 try:
#                     min_val = float(match[0].replace(',', ''))
#                     max_val = float(match[1].replace(',', ''))
#                     if 'k' in pattern.lower():
#                         min_val *= 1000
#                         max_val *= 1000
#                     return min_val, max_val, f"${min_val:,.0f} - ${max_val:,.0f}"
#                 except Exception:
#                     pass
#             elif isinstance(match, str):
#                 try:
#                     val = float(match.replace(',', ''))
#                     return val, val, f"${val:,.0f}"
#                 except Exception:
#                     pass

#     return None, None, None


# def parse_experience_from_text(description: str, html: str = "") -> Optional[str]:
#     """Extract experience requirements from job description"""
#     full_text = f"{description} {html}".lower()

#     experience_patterns = [
#         r'(\d+)[\s-]+(\d+)\s+years?\s*(?:of)?\s*experience',
#         r'(\d+)[\+]?\s*(?:\+)?\s*years?\s*(?:of)?\s*experience',
#         r'minimum\s*(?:of)?\s*(\d+)\s*years?',
#         r'at\s*least\s*(\d+)\s*years?',
#         r'(\d+)\s*years?\s*(?:of)?\s*(?:experience)?\s*required',
#         r'(?:entry\s*level|fresher|no\s*experience)',
#     ]

#     for pattern in experience_patterns:
#         match = re.search(pattern, full_text, re.IGNORECASE)
#         if match:
#             if 'entry' in pattern or 'fresher' in pattern:
#                 return "Entry Level (0-2 years)"
#             if len(match.groups()) == 2:
#                 return f"{match.group(1)}-{match.group(2)} years"
#             elif len(match.groups()) == 1:
#                 return f"{match.group(1)}+ years"

#     return None


# def extract_external_url_from_html(html: str, job_id: str) -> Optional[str]:
#     """
#     Extract external apply URL from raw HTML using multiple methods.
#     """
#     if not html or not job_id:
#         return None

#     # Method 1: Look for applyUrl code block
#     code_pattern = r'<code\s+id="applyUrl"[^>]*>(.*?)</code>'
#     code_match = re.search(code_pattern, html, re.IGNORECASE | re.DOTALL)

#     if code_match:
#         code_content = code_match.group(1)
#         comment_pattern = r'<!--\s*"([^"]+)"\s*-->'
#         comment_match = re.search(comment_pattern, code_content)
#         if comment_match:
#             url_candidate = comment_match.group(1)
#             url_param_match = re.search(r'url=([^&\s]+)', url_candidate)
#             if url_param_match:
#                 encoded_url = url_param_match.group(1)
#                 decoded_url = unquote(encoded_url)
#                 if (decoded_url
#                         and 'linkedin.com' not in decoded_url.lower()
#                         and not any(x in decoded_url.lower()
#                                     for x in ['signup', 'login', 'auth'])):
#                     return decoded_url.split('&urlHash=')[0]

#     # Method 2: Look for externalApply pattern
#     ext_apply_pattern = rf'externalApply/{job_id}\?url=([^"&\s>]+)'
#     ext_match = re.search(ext_apply_pattern, html, re.IGNORECASE)

#     if ext_match:
#         encoded_url = ext_match.group(1)
#         decoded_url = unquote(encoded_url)
#         if decoded_url and 'linkedin.com' not in decoded_url.lower():
#             return decoded_url.split('&urlHash=')[0]

#     return None


# def extract_emails_from_text(text: str) -> List[str]:
#     """Extract email addresses from text"""
#     if not text:
#         return []
#     email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
#     return re.findall(email_pattern, text)


# def parse_relative_date(date_text: str) -> Optional[date]:
#     """Parse relative date strings like '2 days ago'"""
#     if not date_text:
#         return None

#     today = date.today()
#     date_text = date_text.lower()

#     if 'just posted' in date_text or 'moments ago' in date_text:
#         return today

#     hours_match = re.search(r'(\d+)\s*hours?\s*ago', date_text)
#     if hours_match:
#         return today - timedelta(hours=int(hours_match.group(1)))

#     minutes_match = re.search(r'(\d+)\s*minutes?\s*ago', date_text)
#     if minutes_match:
#         return today - timedelta(minutes=int(minutes_match.group(1)))

#     days_match = re.search(r'(\d+)\s*days?\s*ago', date_text)
#     if days_match:
#         return today - timedelta(days=int(days_match.group(1)))

#     weeks_match = re.search(r'(\d+)\s*weeks?\s*ago', date_text)
#     if weeks_match:
#         return today - timedelta(days=int(weeks_match.group(1)) * 7)

#     return None


# def currency_parser(salary_text: str) -> Optional[float]:
#     """Parse salary amount from text"""
#     if not salary_text:
#         return None
#     cleaned = re.sub(r'[$,€£¥]', '', salary_text)
#     numbers = re.findall(r'(\d+(?:\.\d+)?)', cleaned)
#     if numbers:
#         return float(numbers[0])
#     return None


# def create_session(proxies=None, ca_cert=None, cookie=None):
#     """Create a requests session with retry logic"""
#     session = requests.Session()

#     if cookie:
#         session.cookies.set("li_at", cookie, domain=".linkedin.com")

#     if proxies:
#         if isinstance(proxies, list):
#             session.proxies = {"http": proxies[0], "https": proxies[0]}
#         else:
#             session.proxies = {"http": proxies, "https": proxies}

#     return session


# def remove_attributes(soup: BeautifulSoup, keep_tags=None) -> BeautifulSoup:
#     """Remove all attributes from HTML tags except those in keep_tags"""
#     if keep_tags is None:
#         keep_tags = []
#     for tag in soup.find_all(True):
#         if tag.name not in keep_tags:
#             tag.attrs = {}
#     return soup





























































































"""Utility functions for LinkedIn scraper"""

import re
import random
import time
from datetime import datetime, timedelta, date
from typing import Optional, List, Tuple
from urllib.parse import unquote

from bs4 import BeautifulSoup
import requests

from .models import JobType, Location


def job_type_code(job_type_enum: JobType) -> str:
    """Convert JobType enum to LinkedIn job type code"""
    return {
        JobType.FULL_TIME: "F",
        JobType.PART_TIME: "P",
        JobType.INTERNSHIP: "I",
        JobType.CONTRACT: "C",
        JobType.TEMPORARY: "T",
    }.get(job_type_enum, "")


def parse_job_type(soup: BeautifulSoup) -> Optional[List[JobType]]:
    """Extract job type from job page"""
    h3_tag = soup.find(
        "h3",
        class_="description__job-criteria-subheader",
        string=lambda text: text and "Employment type" in text,
    )

    if not h3_tag:
        return None

    employment_type_span = h3_tag.find_next_sibling(
        "span",
        class_="description__job-criteria-text description__job-criteria-text--criteria",
    )

    if not employment_type_span:
        return None

    employment_type = employment_type_span.get_text(strip=True).lower().replace("-", "")

    type_map = {
        "fulltime": JobType.FULL_TIME,
        "full time": JobType.FULL_TIME,
        "parttime": JobType.PART_TIME,
        "part time": JobType.PART_TIME,
        "contract": JobType.CONTRACT,
        "internship": JobType.INTERNSHIP,
        "temporary": JobType.TEMPORARY,
    }

    for key, value in type_map.items():
        if key in employment_type:
            return [value]

    return None


def parse_job_level(soup: BeautifulSoup) -> Optional[str]:
    """Extract job level/seniority from job page"""
    h3_tag = soup.find(
        "h3",
        class_="description__job-criteria-subheader",
        string=lambda text: text and "Seniority level" in text,
    )

    if not h3_tag:
        return None

    job_level_span = h3_tag.find_next_sibling(
        "span",
        class_="description__job-criteria-text description__job-criteria-text--criteria",
    )

    return job_level_span.get_text(strip=True) if job_level_span else None


def parse_company_industry(soup: BeautifulSoup) -> Optional[str]:
    """Extract company industry from job page"""
    h3_tag = soup.find(
        "h3",
        class_="description__job-criteria-subheader",
        string=lambda text: text and "Industries" in text,
    )

    if not h3_tag:
        return None

    industry_span = h3_tag.find_next_sibling(
        "span",
        class_="description__job-criteria-text description__job-criteria-text--criteria",
    )

    return industry_span.get_text(strip=True) if industry_span else None


def is_job_remote(title: str, description: str, location: Location) -> bool:
    """Check if job is remote based on title, description, and location"""
    remote_keywords = ["remote", "work from home", "wfh", "virtual", "telecommute", "hybrid"]

    location_str = location.display_location().lower() if location else ""
    title_lower = title.lower() if title else ""
    description_lower = description.lower() if description else ""

    full_string = f"{title_lower} {description_lower} {location_str}"

    return any(keyword in full_string for keyword in remote_keywords)


def _clean_logo_url(url):
    """
    Sanitize a raw logo URL extracted from LinkedIn HTML.
    Fix 1: http -> https  (EdgeSuite CDN blocks plain HTTP with Access Denied)
    Fix 2: &amp; -> &     (HTML entities must be unescaped in stored URLs)
    Fix 3: strip backslash-escaped slashes and whitespace
    """
    if not url:
        return None
    url = (url.replace('&amp;', '&')
              .replace('&quot;', '"')
              .replace("&#39;", "'")
              .replace('\\/', '/')
              .strip())
    if url.startswith('http://'):
        url = 'https://' + url[7:]
    if not url.startswith('https://'):
        return None
    if 'ghost' in url.lower() or 'blank' in url.lower():
        return None
    return url


def extract_company_logo(soup, api_html="", view_html=""):
    """
    Extract company logo URL from job page.
    Search order: api_html code blocks -> view_html code blocks
                  -> img tags -> og:image meta
    All URLs sanitized via _clean_logo_url():
      - forces https:// (fixes Access Denied from EdgeSuite CDN)
      - unescapes &amp; in query params (fixes malformed stored URLs)
    """

    # ── METHOD 0: JSON blob in <code> tags — api_html then view_html ──────────
    for raw_html in [api_html, view_html]:
        if not raw_html:
            continue

        # Step A: inside <code> blocks with entity unescaping
        try:
            code_blocks = re.findall(r'<code[^>]*>(.*?)</code>', raw_html, re.DOTALL)
            for block in code_blocks:
                block = block.replace('&quot;', '"').replace('&amp;', '&').replace("&#39;", "'")
                m = re.search(r'"logoUrl"\s*:\s*"(https?://media\.licdn\.com/[^"]+)"', block)
                if m:
                    clean = _clean_logo_url(m.group(1))
                    if clean:
                        return clean
        except Exception:
            pass

        # Step B: direct regex on full raw HTML
        try:
            m = re.search(r'"logoUrl"\s*:\s*"(https?://media\.licdn\.com/[^"\\]+)"', raw_html)
            if m:
                clean = _clean_logo_url(m.group(1))
                if clean:
                    return clean

            m = re.search(
                r"(https?://media\.licdn\.com/dms/image/[^\"'\\,\s]+/company-logo[^\"'\\,\s]+)",
                raw_html
            )
            if m:
                clean = _clean_logo_url(m.group(1))
                if clean:
                    return clean
        except Exception:
            pass

    # ── METHOD 1: img tag selectors (original — unchanged) ───────────────────
    try:
        for selector in [
            'img.artdeco-entity-image',
            'img.presence-entity__image',
            'img[data-delayed-url]',
            'img.ivm-view-attr__img--centered',
        ]:
            logo_img = soup.select_one(selector)
            if logo_img:
                for attr in ['src', 'data-delayed-url', 'data-src']:
                    if logo_img.get(attr):
                        clean = _clean_logo_url(logo_img[attr])
                        if clean:
                            return clean
    except Exception:
        pass

    # ── METHOD 2: og:image meta fallback ─────────────────────────────────────
    try:
        meta = soup.find('meta', {'property': 'og:image'})
        if meta and meta.get('content'):
            clean = _clean_logo_url(meta['content'])
            if clean:
                return clean
    except Exception:
        pass

    return None

def parse_salary_from_text(
    description: str, html: str = ""
) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """
    Extract salary min, max, and full text from job description.
    Returns (min_amount, max_amount, salary_text)
    """
    full_text = f"{description} {html}".lower()

    salary_patterns = [
        r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*[-–]\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
        r'\$(\d{1,3})k\s*[-–]\s*\$?(\d{1,3})k',
        r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:per|/)\s*(?:year|annum|yr)',
        r'\$(\d{1,3})k\s*(?:per|/)\s*(?:year|annum|yr)',
        r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*[-–]\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
    ]

    for pattern in salary_patterns:
        matches = re.findall(pattern, full_text, re.IGNORECASE)
        if matches:
            match = matches[0]
            if isinstance(match, tuple) and len(match) >= 2:
                try:
                    min_val = float(match[0].replace(',', ''))
                    max_val = float(match[1].replace(',', ''))
                    if 'k' in pattern.lower():
                        min_val *= 1000
                        max_val *= 1000
                    return min_val, max_val, f"${min_val:,.0f} - ${max_val:,.0f}"
                except Exception:
                    pass
            elif isinstance(match, str):
                try:
                    val = float(match.replace(',', ''))
                    return val, val, f"${val:,.0f}"
                except Exception:
                    pass

    return None, None, None


def parse_experience_from_text(description: str, html: str = "") -> Optional[str]:
    """Extract experience requirements from job description"""
    full_text = f"{description} {html}".lower()

    experience_patterns = [
        r'(\d+)[\s-]+(\d+)\s+years?\s*(?:of)?\s*experience',
        r'(\d+)[\+]?\s*(?:\+)?\s*years?\s*(?:of)?\s*experience',
        r'minimum\s*(?:of)?\s*(\d+)\s*years?',
        r'at\s*least\s*(\d+)\s*years?',
        r'(\d+)\s*years?\s*(?:of)?\s*(?:experience)?\s*required',
        r'(?:entry\s*level|fresher|no\s*experience)',
    ]

    for pattern in experience_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            if 'entry' in pattern or 'fresher' in pattern:
                return "Entry Level (0-2 years)"
            if len(match.groups()) == 2:
                return f"{match.group(1)}-{match.group(2)} years"
            elif len(match.groups()) == 1:
                return f"{match.group(1)}+ years"

    return None


def parse_skills_requirements(description: str, html: str = "") -> Optional[str]:
    """
    Extract requirements and key skills from job description text.
    Returns the requirements / qualifications / skills section formatted as text.
    """
    if not description:
        return None

    # Step 1: Look for explicit Requirements / Qualifications / Skills section header
    start_pattern = (
        r'(?i)(?:(?:minimum|basic|required|key|core|technical|role|job)?\s*'
        r'(?:qualifications?|requirements?|skills?|competencies|prerequisites)|'
        r'what\s*(?:you|we)\'?ll?\s*(?:need|bring|require|look\s*for)|who\s*you\s*are|must\s*haves?)'
    )
    end_pattern = (
        r'(?i)\n\s*(?:benefits|perks|what\s*we\s*offer|compensation|salary|'
        r'about\s*(?:us|the\s*company|our\s*team)|equal\s*opportunity|diversity|'
        r'how\s*to\s*apply|physical\s*demands|work\s*environment)\b'
    )

    m_start = re.search(start_pattern, description)
    if m_start:
        sub = description[m_start.start():]
        m_end = re.search(end_pattern, sub)
        if m_end:
            extracted = sub[:m_end.start()].strip()
        else:
            extracted = sub[:3500].strip()
        if len(extracted) > 30:
            return extracted

    # Step 2: Fallback — scan for bullet points containing requirement keywords
    lines = [line.strip() for line in description.split("\n") if line.strip()]
    req_keywords = [
        "experience", "proficien", "knowledge", "degree", "bachelor", "master",
        "ability to", "skilled in", "familiar with", "understanding of", "must have",
        "python", "sql", "aws", "cloud", "developer", "engineer", "years"
    ]
    bullet_lines = []
    for line in lines:
        lower = line.lower()
        if any(kw in lower for kw in req_keywords) and len(line) > 15:
            bullet_lines.append(line)
        if len(bullet_lines) >= 15:
            break

    if bullet_lines:
        return "\n".join(bullet_lines)[:3500]

    return None


def has_offsite_apply_icon(soup: BeautifulSoup = None, raw_html: str = "") -> bool:
    """
    Check if the apply button in the DOM contains an <icon> tag,
    signifying an external / offsite apply button.
    Returns True if an <icon> tag exists inside the Apply button, or offsite-apply SVG is present.
    Returns False if it is Easy Apply (no <icon> tag inside the Apply button).
    """
    if soup:
        for btn in soup.find_all(["button", "a"]):
            btn_text = btn.get_text(separator=" ", strip=True).lower()
            btn_class = " ".join(btn.get("class", [])).lower()
            modal_data = str(btn.get("data-modal", "")).lower()

            # Check if this element is an Apply button
            if (
                "apply" in btn_text
                or "apply-button" in btn_class
                or "topcard-apply-modal" in modal_data
                or "sign-up-modal__outlet" in btn_class
            ):
                # 1. Contains <icon> tag inside the button
                if btn.find("icon"):
                    return True
                # 2. Contains offsite-apply SVG / class
                if "offsite-apply" in str(btn):
                    return True

    # Secondary check on raw HTML
    if raw_html:
        if (
            "apply-button__offsite-apply-icon-svg" in raw_html
            or "public_jobs_apply-link-offsite" in raw_html
        ):
            return True

    return False


def extract_external_url_from_html(html: str, job_id: str) -> Optional[str]:
    """
    Extract external apply URL from raw HTML using multiple methods.
    """
    if not html or not job_id:
        return None

    # Method 1: Look for applyUrl code block
    code_pattern = r'<code\s+id="applyUrl"[^>]*>(.*?)</code>'
    code_match = re.search(code_pattern, html, re.IGNORECASE | re.DOTALL)

    if code_match:
        code_content = code_match.group(1)
        comment_pattern = r'<!--\s*"([^"]+)"\s*-->'
        comment_match = re.search(comment_pattern, code_content)
        if comment_match:
            url_candidate = comment_match.group(1)
            url_param_match = re.search(r'url=([^&\s]+)', url_candidate)
            if url_param_match:
                encoded_url = url_param_match.group(1)
                decoded_url = unquote(encoded_url)
                if (decoded_url
                        and 'linkedin.com' not in decoded_url.lower()
                        and not any(x in decoded_url.lower()
                                    for x in ['signup', 'login', 'auth'])):
                    return decoded_url.split('&urlHash=')[0]

    # Method 2: Look for externalApply pattern
    ext_apply_pattern = rf'externalApply/{job_id}\?url=([^"&\s>]+)'
    ext_match = re.search(ext_apply_pattern, html, re.IGNORECASE)

    if ext_match:
        encoded_url = ext_match.group(1)
        decoded_url = unquote(encoded_url)
        if decoded_url and 'linkedin.com' not in decoded_url.lower():
            return decoded_url.split('&urlHash=')[0]

    return None


def extract_emails_from_text(text: str) -> List[str]:
    """Extract email addresses from text"""
    if not text:
        return []
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    return re.findall(email_pattern, text)


def parse_relative_date(date_text: str) -> Optional[date]:
    """Parse relative date strings like '2 days ago'"""
    if not date_text:
        return None

    today = date.today()
    date_text = date_text.lower()

    if 'just posted' in date_text or 'moments ago' in date_text:
        return today

    hours_match = re.search(r'(\d+)\s*hours?\s*ago', date_text)
    if hours_match:
        return today - timedelta(hours=int(hours_match.group(1)))

    minutes_match = re.search(r'(\d+)\s*minutes?\s*ago', date_text)
    if minutes_match:
        return today - timedelta(minutes=int(minutes_match.group(1)))

    days_match = re.search(r'(\d+)\s*days?\s*ago', date_text)
    if days_match:
        return today - timedelta(days=int(days_match.group(1)))

    weeks_match = re.search(r'(\d+)\s*weeks?\s*ago', date_text)
    if weeks_match:
        return today - timedelta(days=int(weeks_match.group(1)) * 7)

    return None


def currency_parser(salary_text: str) -> Optional[float]:
    """Parse salary amount from text"""
    if not salary_text:
        return None
    cleaned = re.sub(r'[$,€£¥]', '', salary_text)
    numbers = re.findall(r'(\d+(?:\.\d+)?)', cleaned)
    if numbers:
        return float(numbers[0])
    return None


def create_session(proxies=None, ca_cert=None, cookie=None):
    """Create a requests session with retry logic"""
    session = requests.Session()

    if cookie:
        session.cookies.set("li_at", cookie, domain=".linkedin.com")

    if proxies:
        if isinstance(proxies, list):
            session.proxies = {"http": proxies[0], "https": proxies[0]}
        else:
            session.proxies = {"http": proxies, "https": proxies}

    return session


def remove_attributes(soup: BeautifulSoup, keep_tags=None) -> BeautifulSoup:
    """Remove all attributes from HTML tags except those in keep_tags"""
    if keep_tags is None:
        keep_tags = []
    for tag in soup.find_all(True):
        if tag.name not in keep_tags:
            tag.attrs = {}
    return soup