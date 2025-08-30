import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

class SupabaseService:
    def __init__(self):
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_ANON_KEY")
        self.supabase_access_token = os.getenv("SUPABASE_ACCESS_TOKEN")
        
        if not self.supabase_url or not self.supabase_key:
            print("Varning: Supabase credentials saknas. Använd mock-läge.")
            self.client = None
        else:
            # Skapa client med både anon key och access token
            self.client: Client = create_client(self.supabase_url, self.supabase_key)
            # Sätt access token för admin-operationer (endast om det är en giltig JWT)
            if self.supabase_access_token and len(self.supabase_access_token.split(".")) == 3:
                try:
                    self.client.auth.set_session(self.supabase_access_token, None)
                except Exception as e:
                    print(f"Varning: Kunde inte sätta access token: {e}")
    
    async def save_report(self, user_id: str, report_data: Dict[str, Any]) -> bool:
        """
        Sparar rapport till Supabase
        """
        if not self.client:
            print(f"Mock: Sparar rapport för användare {user_id}")
            return True
        
        try:
            data = {
                "user_id": user_id,
                "report_id": report_data["report_id"],
                "company_name": report_data["company_name"],
                "fiscal_year": report_data["fiscal_year"],
                "created_at": datetime.now().isoformat(),
                "pdf_path": report_data["pdf_path"]
            }
            
            result = self.client.table("reports").insert(data).execute()
            return True
            
        except Exception as e:
            print(f"Fel vid sparande till Supabase: {e}")
            return False
    
    async def get_user_reports(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Hämtar användarens rapporter från Supabase
        """
        if not self.client:
            print(f"Mock: Hämtar rapporter för användare {user_id}")
            return [
                {
                    "id": "mock-1",
                    "user_id": user_id,
                    "report_id": "mock-report-1",
                    "company_name": "Mock Företag AB",
                    "fiscal_year": 2024,
                    "created_at": datetime.now().isoformat(),
                    "download_url": "/download-report/mock-report-1"
                }
            ]
        
        try:
            result = self.client.table("reports").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
            return result.data
            
        except Exception as e:
            print(f"Fel vid hämtning från Supabase: {e}")
            return []
    
    async def save_user_preferences(self, user_id: str, preferences: Dict[str, Any]) -> bool:
        """
        Sparar användarens preferenser
        """
        if not self.client:
            print(f"Mock: Sparar preferenser för användare {user_id}")
            return True
        
        try:
            data = {
                "user_id": user_id,
                "preferences": preferences,
                "updated_at": datetime.now().isoformat()
            }
            
            # Upsert (uppdatera eller skapa ny)
            result = self.client.table("user_preferences").upsert(data).execute()
            return True
            
        except Exception as e:
            print(f"Fel vid sparande av preferenser: {e}")
            return False
    
    async def get_user_preferences(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Hämtar användarens preferenser
        """
        if not self.client:
            print(f"Mock: Hämtar preferenser för användare {user_id}")
            return {
                "default_location": "Stockholm",
                "default_depreciation_periods": {
                    "buildings": 50,
                    "machinery": 10,
                    "computers": 3
                }
            }
        
        try:
            result = self.client.table("user_preferences").select("*").eq("user_id", user_id).execute()
            if result.data:
                return result.data[0]["preferences"]
            return None
            
        except Exception as e:
            print(f"Fel vid hämtning av preferenser: {e}")
            return None 