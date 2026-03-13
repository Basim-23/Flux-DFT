"""
Supabase Client for FluxDFT Cloud.
Strings together Auth and Database interactions.
"""

from typing import Optional, Dict, List, Any
import os
from pathlib import Path

# Try to import supabase
try:
    from supabase import create_client, Client
    from gotrue.errors import AuthApiError
    HAS_SUPABASE = True
except ImportError:
    HAS_SUPABASE = False
    Client = object # Dummy for type hinting

class SupabaseManager:
    """
    Manages connection to FluxDFT Cloud (Supabase).
    Handles User Authentication and License Verification.
    """
    
    def __init__(self, url: str, key: str):
        self.url = url
        self.key = key
        self.client: Optional[Client] = None
        
        if HAS_SUPABASE and url and key:
            try:
                self.client = create_client(url, key)
            except Exception as e:
                print(f"Failed to initialize Supabase: {e}")
    
    def is_available(self) -> bool:
        """Check if Supabase client is initialized."""
        return self.client is not None
    
    def login(self, email: str, password: str) -> Dict[str, Any]:
        """
        Log in a user.
        Returns: User session/data or raises Exception.
        """
        if not self.is_available():
            raise RuntimeError("Cloud service not configured.")
        
        try:
            response = self.client.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            return response.user
        except AuthApiError as e:
            raise ValueError(f"Login failed: {e.message}")
        except Exception as e:
            raise RuntimeError(f"Connection error: {e}")
            
    def sign_up(self, email: str, password: str) -> Dict[str, Any]:
        """Sign up a new user."""
        if not self.is_available():
            raise RuntimeError("Cloud service not configured.")
            
        try:
            response = self.client.auth.sign_up({
                "email": email,
                "password": password
            })
            return response.user
        except Exception as e:
            raise RuntimeError(f"Sign up failed: {e}")
    
    def logout(self):
        """Sign out current user."""
        if self.is_available():
            self.client.auth.sign_out()
            
    def get_user(self):
        """Get current user."""
        if self.is_available():
            return self.client.auth.get_user()
        return None
        
    def check_license(self, user_id: str) -> bool:
        """
        Check if user has a valid license.
        Queries the 'licenses' table.
        """
        if not self.is_available():
            return False
            
        try:
            # Query 'licenses' table for this user, check 'active' status
            # Assumes table: licenses (user_id, status, expires_at)
            response = self.client.table("licenses")\
                .select("*")\
                .eq("user_id", user_id)\
                .eq("status", "active")\
                .execute()
            
            # If we find at least one active license, return True
            return len(response.data) > 0
        except Exception as e:
            print(f"License check failed: {e}")
            return False
