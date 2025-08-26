import requests
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class CloudflareClient:
    """Client for interacting with Cloudflare Waiting Room API."""
    
    def __init__(self, api_token: str, zone_id: str):
        self.api_token = api_token
        self.zone_id = zone_id
        self.base_url = "https://api.cloudflare.com/client/v4"
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
    
    def _make_request(self, endpoint: str) -> Optional[Dict]:
        """Make authenticated request to Cloudflare API."""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            if not data.get("success", False):
                logger.error(f"Cloudflare API error: {data.get('errors', [])}")
                return None
                
            return data.get("result")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP request failed: {e}")
            return None
        except ValueError as e:
            logger.error(f"Invalid JSON response: {e}")
            return None
    
    
    def get_waiting_room_status(self, waiting_room_id: str) -> Optional[Dict]:
        """Get current status of a waiting room."""
        endpoint = f"/zones/{self.zone_id}/waiting_rooms/{waiting_room_id}/status"
        return self._make_request(endpoint)
    
    def list_waiting_rooms(self) -> Optional[List[Dict]]:
        """List all waiting rooms for the zone."""
        endpoint = f"/zones/{self.zone_id}/waiting_rooms"
        result = self._make_request(endpoint)
        return result if result else []