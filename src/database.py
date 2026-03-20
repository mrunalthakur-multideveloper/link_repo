"""Supabase database handler for LinkedIn scraper"""

import os
import socket
import time
from typing import Optional, List, Dict, Any
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class SupabaseManager:
    """Manages all Supabase database operations"""
    
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_KEY")
        self.client: Optional[Client] = None
        self.table_name = "linkedin_jobs"
        self.initialized = False
        self.offline_mode = False
        
    def initialize(self) -> bool:
        """Initialize Supabase connection with better error handling"""
        
        # Check if we're in offline mode
        if self.offline_mode:
            print("⚠️ Running in offline mode (database disabled)")
            return False
            
        if not self.url or not self.key:
            print("❌ Supabase credentials not found in .env file")
            print("   Please set SUPABASE_URL and SUPABASE_KEY")
            print("   Continuing without database...")
            self.offline_mode = True
            return False
        
        # Clean the URL
        self.url = self.url.strip().rstrip('/')
        if not self.url.startswith('http'):
            self.url = f"https://{self.url}"
        
        print(f"📡 Connecting to Supabase: {self.url}")
        
        # Test DNS resolution first
        try:
            hostname = self.url.replace('https://', '').replace('http://', '').split('/')[0]
            print(f"   Resolving hostname: {hostname}")
            socket.gethostbyname(hostname)
            print(f"   ✓ DNS resolution successful")
        except socket.gaierror as e:
            print(f"❌ DNS resolution failed: {e}")
            print("   This might be a network issue or the Supabase URL is incorrect")
            print("   Continuing without database...")
            self.offline_mode = True
            return False
        except Exception as e:
            print(f"⚠️ DNS check warning: {e}")
        
        # Try to connect with retry
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.client = create_client(self.url, self.key)
                self.initialized = True
                print("✓ Supabase client initialized successfully")
                
                # Test connection with a simple query
                try:
                    test = self.client.table(self.table_name).select("count").limit(1).execute()
                    print("✓ Database connection test successful")
                except Exception as e:
                    print(f"⚠️ Connection test warning: {e}")
                    # Still consider it initialized if client was created
                
                return True
                
            except Exception as e:
                print(f"❌ Attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    print(f"   Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    print("❌ Failed to initialize Supabase after all retries")
                    print("   Continuing without database...")
                    self.offline_mode = True
        
        return False
    
    def job_exists(self, job_id: str) -> bool:
        """Check if job already exists in database"""
        if self.offline_mode or not self.initialized or not self.client:
            return False
        
        try:
            result = self.client.table(self.table_name) \
                .select("id") \
                .eq("job_id", job_id) \
                .execute()
            
            return len(result.data) > 0
        except Exception as e:
            # Don't print every error to avoid spam
            return False
    
    def save_job(self, job_dict: dict) -> Optional[str]:
        """Save a single job to database"""
        if self.offline_mode or not self.initialized or not self.client:
            return None
        
        try:
            # Check if job already exists
            job_id = job_dict.get("job_id")
            if job_id and self.job_exists(job_id):
                return None
            
            # Insert into database
            result = self.client.table(self.table_name).insert(job_dict).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0].get('id')
            else:
                return None
                
        except Exception as e:
            # Only print occasional errors to avoid spam
            if random.randint(1, 10) == 1:  # Print about 10% of errors
                print(f"  ⚠️ Database save error (sporadic): {e}")
            return None
    
    def save_jobs_batch(self, jobs: List[dict]) -> Dict[str, int]:
        """Save multiple jobs in batch"""
        results = {
            "success": 0,
            "failed": 0,
            "duplicate": 0
        }
        
        if self.offline_mode or not jobs:
            if jobs:
                print(f"\n📊 Running in offline mode - jobs saved to CSV only")
                results["failed"] = len(jobs)
            return results
        
        print(f"\n💾 Saving jobs to Supabase...")
        
        success_count = 0
        for i, job_dict in enumerate(jobs):
            try:
                # Show progress occasionally
                if (i + 1) % 10 == 0 or i == 0:
                    print(f"   Processing job {i+1}/{len(jobs)}")
                
                record_id = self.save_job(job_dict)
                if record_id:
                    success_count += 1
                    
            except Exception:
                # Silently fail for individual jobs
                pass
        
        print(f"\n📊 Database Results:")
        print(f"   ✅ Successfully saved: {success_count}/{len(jobs)}")
        
        results["success"] = success_count
        results["failed"] = len(jobs) - success_count
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get scraping statistics from database"""
        if self.offline_mode or not self.initialized or not self.client:
            return {}
        
        try:
            # Total jobs count
            total = self.client.table(self.table_name) \
                .select("id", count="exact") \
                .execute()
            
            # Jobs with external links
            external = self.client.table(self.table_name) \
                .select("id", count="exact") \
                .not_.is_("apply_url", "null") \
                .execute()
            
            return {
                "total_jobs": total.count if hasattr(total, 'count') else 0,
                "external_links": external.count if hasattr(external, 'count') else 0,
            }
            
        except Exception as e:
            print(f"❌ Error getting statistics: {e}")
            return {}