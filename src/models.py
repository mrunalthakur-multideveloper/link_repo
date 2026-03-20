# """Data models for LinkedIn scraper - optimized for Supabase"""

# from datetime import datetime, date
# from typing import Optional, List
# from enum import Enum
# from dataclasses import dataclass, field, asdict
# import json


# class JobType(str, Enum):
#     FULL_TIME = "full_time"
#     PART_TIME = "part_time"
#     CONTRACT = "contract"
#     INTERNSHIP = "internship"
#     TEMPORARY = "temporary"


# class Country(str, Enum):
#     USA = "United States"
#     CANADA = "Canada"
#     UK = "United Kingdom"
#     AUSTRALIA = "Australia"
#     GERMANY = "Germany"
#     FRANCE = "France"
#     INDIA = "India"
#     UNKNOWN = "Unknown"


# @dataclass
# class Location:
#     city: Optional[str] = None
#     state: Optional[str] = None
#     country: Country = Country.UNKNOWN
    
#     def display_location(self) -> str:
#         parts = []
#         if self.city:
#             parts.append(self.city)
#         if self.state:
#             parts.append(self.state)
#         if self.country != Country.UNKNOWN:
#             parts.append(self.country.value)
#         return ", ".join(parts) if parts else "Unknown"
    
#     def to_dict(self) -> dict:
#         return {
#             "city": self.city,
#             "state": self.state,
#             "country": self.country.value if self.country else None
#         }
    
#     @classmethod
#     def from_string(cls, location_str: str) -> "Location":
#         """Parse location from string like "San Francisco, CA" or "New York, United States" """
#         if not location_str:
#             return cls()
        
#         parts = [p.strip() for p in location_str.split(",")]
        
#         if len(parts) == 2:
#             city, state = parts
#             # Check if second part is a country
#             if state in [c.value for c in Country]:
#                 return cls(city=city, country=Country(state))
#             return cls(city=city, state=state)
#         elif len(parts) == 3:
#             city, state, country = parts
#             return cls(city=city, state=state, country=Country(country))
#         else:
#             return cls(state=location_str)


# @dataclass
# class Compensation:
#     min_amount: Optional[float] = None
#     max_amount: Optional[float] = None
#     currency: str = "USD"
#     interval: str = "yearly"  # hourly, daily, weekly, monthly, yearly
    
#     def to_dict(self) -> dict:
#         return {
#             "min_amount": self.min_amount,
#             "max_amount": self.max_amount,
#             "currency": self.currency,
#             "interval": self.interval
#         }


# @dataclass
# class JobPost:
#     """Represents a job posting - optimized for Supabase storage"""
    
#     # Core fields
#     job_id: str
#     title: str
#     company_name: str
    
#     # Optional fields
#     company_url: Optional[str] = None
#     company_logo: Optional[str] = None
#     location: Location = field(default_factory=Location)
#     description: Optional[str] = None
    
#     # Dates
#     date_posted: Optional[date] = None
#     scraped_at: datetime = field(default_factory=datetime.now)
    
#     # URLs
#     job_url: Optional[str] = None
#     apply_url: Optional[str] = None  # Direct external apply URL
#     job_url_direct: Optional[str] = None  # Alias for backward compatibility
    
#     # Job details
#     job_type: Optional[List[JobType]] = None
#     job_level: Optional[str] = None
#     company_industry: Optional[str] = None
#     job_function: Optional[str] = None
#     is_remote: bool = False
#     is_easy_apply: bool = False
    
#     # Compensation
#     compensation: Optional[Compensation] = None
    
#     # Contact
#     emails: List[str] = field(default_factory=list)
    
#     # Metadata
#     search_keyword: Optional[str] = None  # Which keyword found this job
    
#     def __post_init__(self):
#         """Set apply_url from job_url_direct for backward compatibility"""
#         if self.job_url_direct and not self.apply_url:
#             self.apply_url = self.job_url_direct
#         elif self.apply_url and not self.job_url_direct:
#             self.job_url_direct = self.apply_url
    
#     def to_supabase_dict(self) -> dict:
#         """Convert job to dictionary format for Supabase insertion"""
        
#         # Convert job_type list to string
#         job_type_str = None
#         if self.job_type:
#             job_type_str = ",".join([jt.value for jt in self.job_type])
        
#         # Convert date to ISO string
#         date_posted_str = None
#         if self.date_posted:
#             if isinstance(self.date_posted, date):
#                 date_posted_str = self.date_posted.isoformat()
#             else:
#                 date_posted_str = str(self.date_posted)
        
#         # Convert datetime to ISO string
#         scraped_at_str = self.scraped_at.isoformat() if self.scraped_at else None
        
#         # Handle location
#         location_dict = self.location.to_dict() if self.location else {}
        
#         # Handle compensation
#         compensation_dict = self.compensation.to_dict() if self.compensation else {}
        
#         return {
#             "job_id": self.job_id,
#             "title": self.title[:500] if self.title else None,
#             "company_name": self.company_name[:255] if self.company_name else None,
#             "company_url": self.company_url[:500] if self.company_url else None,
#             "company_logo": self.company_logo[:1000] if self.company_logo else None,
#             "location_city": location_dict.get("city"),
#             "location_state": location_dict.get("state"),
#             "location_country": location_dict.get("country"),
#             "location_display": self.location.display_location() if self.location else None,
#             "description": self.description[:10000] if self.description else None,
#             "date_posted": date_posted_str,
#             "scraped_at": scraped_at_str,
#             "job_url": self.job_url[:1000] if self.job_url else None,
#             "apply_url": self.apply_url[:1000] if self.apply_url else None,
#             "job_type": job_type_str,
#             "job_level": self.job_level[:100] if self.job_level else None,
#             "company_industry": self.company_industry[:255] if self.company_industry else None,
#             "job_function": self.job_function[:255] if self.job_function else None,
#             "is_remote": self.is_remote,
#             "is_easy_apply": self.is_easy_apply,
#             "compensation_min": compensation_dict.get("min_amount"),
#             "compensation_max": compensation_dict.get("max_amount"),
#             "compensation_currency": compensation_dict.get("currency"),
#             "compensation_interval": compensation_dict.get("interval"),
#             "emails": ",".join(self.emails) if self.emails else None,
#             "search_keyword": self.search_keyword[:255] if self.search_keyword else None,
#         }



















































"""Data models for LinkedIn scraper - optimized for Supabase"""

from datetime import datetime, date
from typing import Optional, List
from enum import Enum
from dataclasses import dataclass, field
import json


class JobType(str, Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"
    TEMPORARY = "temporary"


class Country(str, Enum):
    USA = "United States"
    CANADA = "Canada"
    UK = "United Kingdom"
    AUSTRALIA = "Australia"
    GERMANY = "Germany"
    FRANCE = "France"
    INDIA = "India"
    UNKNOWN = "Unknown"


@dataclass
class Location:
    city: Optional[str] = None
    state: Optional[str] = None
    country: Country = Country.UNKNOWN
    
    def display_location(self) -> str:
        parts = []
        if self.city:
            parts.append(self.city)
        if self.state:
            parts.append(self.state)
        if self.country != Country.UNKNOWN:
            parts.append(self.country.value)
        return ", ".join(parts) if parts else "Unknown"
    
    def to_dict(self) -> dict:
        return {
            "city": self.city,
            "state": self.state,
            "country": self.country.value if self.country else None
        }
    
    @classmethod
    def from_string(cls, location_str: str) -> "Location":
        """Parse location from string like "San Francisco, CA" or "New York, United States" """
        if not location_str:
            return cls()
        
        parts = [p.strip() for p in location_str.split(",")]
        
        if len(parts) == 2:
            city, state = parts
            # Check if second part is a country
            if state in [c.value for c in Country]:
                return cls(city=city, country=Country(state))
            return cls(city=city, state=state)
        elif len(parts) == 3:
            city, state, country = parts
            return cls(city=city, state=state, country=Country(country))
        else:
            return cls(state=location_str)


@dataclass
class Compensation:
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    currency: str = "USD"
    interval: str = "yearly"
    
    def to_dict(self) -> dict:
        return {
            "min_amount": self.min_amount,
            "max_amount": self.max_amount,
            "currency": self.currency,
            "interval": self.interval
        }


@dataclass
class JobPost:
    """Represents a job posting - optimized for Supabase storage"""
    
    # Core fields
    job_id: str
    title: str
    company_name: str
    
    # Optional fields
    company_url: Optional[str] = None
    company_logo: Optional[str] = None
    location: Location = field(default_factory=Location)
    description: Optional[str] = None
    
    # Dates
    date_posted: Optional[date] = None
    scraped_at: datetime = field(default_factory=datetime.now)
    
    # URLs
    job_url: Optional[str] = None
    apply_url: Optional[str] = None
    job_url_direct: Optional[str] = None
    
    # Job details
    job_type: Optional[List[JobType]] = None
    job_level: Optional[str] = None
    company_industry: Optional[str] = None
    job_function: Optional[str] = None
    is_remote: bool = False
    is_easy_apply: bool = False
    
    # Compensation
    compensation: Optional[Compensation] = None
    
    # NEW FIELDS
    experience: Optional[str] = None
    salary_text: Optional[str] = None
    
    # Contact
    emails: List[str] = field(default_factory=list)
    
    # Metadata
    search_keyword: Optional[str] = None
    
    def __post_init__(self):
        """Set apply_url from job_url_direct for backward compatibility"""
        if self.job_url_direct and not self.apply_url:
            self.apply_url = self.job_url_direct
        elif self.apply_url and not self.job_url_direct:
            self.job_url_direct = self.apply_url
    
    def to_supabase_dict(self) -> dict:
        """Convert job to dictionary format for Supabase insertion"""
        
        # Convert job_type list to string
        job_type_str = None
        if self.job_type:
            job_type_str = ",".join([jt.value for jt in self.job_type])
        
        # Convert date to ISO string
        date_posted_str = None
        if self.date_posted:
            if isinstance(self.date_posted, date):
                date_posted_str = self.date_posted.isoformat()
            else:
                date_posted_str = str(self.date_posted)
        
        # Convert datetime to ISO string
        scraped_at_str = self.scraped_at.isoformat() if self.scraped_at else None
        
        # Handle location
        location_dict = self.location.to_dict() if self.location else {}
        
        # Handle compensation
        compensation_dict = self.compensation.to_dict() if self.compensation else {}
        
        return {
            "job_id": self.job_id,
            "title": self.title[:500] if self.title else None,
            "company_name": self.company_name[:255] if self.company_name else None,
            "company_url": self.company_url[:500] if self.company_url else None,
            "company_logo": self.company_logo[:1000] if self.company_logo else None,
            "location_city": location_dict.get("city"),
            "location_state": location_dict.get("state"),
            "location_country": location_dict.get("country"),
            "location_display": self.location.display_location() if self.location else None,
            "description": self.description[:10000] if self.description else None,
            "date_posted": date_posted_str,
            "scraped_at": scraped_at_str,
            "job_url": self.job_url[:1000] if self.job_url else None,
            "apply_url": self.apply_url[:1000] if self.apply_url else None,
            "job_type": job_type_str,
            "job_level": self.job_level[:100] if self.job_level else None,
            "company_industry": self.company_industry[:255] if self.company_industry else None,
            "job_function": self.job_function[:255] if self.job_function else None,
            "is_remote": self.is_remote,
            "is_easy_apply": self.is_easy_apply,
            "compensation_min": compensation_dict.get("min_amount"),
            "compensation_max": compensation_dict.get("max_amount"),
            "compensation_currency": compensation_dict.get("currency"),
            "compensation_interval": compensation_dict.get("interval"),
            "experience": self.experience[:255] if self.experience else None,
            "salary_text": self.salary_text[:255] if self.salary_text else None,
            "emails": ",".join(self.emails) if self.emails else None,
            "search_keyword": self.search_keyword[:255] if self.search_keyword else None,
        }