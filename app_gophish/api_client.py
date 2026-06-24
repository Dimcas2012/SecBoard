# app_gophish/api_client.py

import requests
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from django.conf import settings
import json

logger = logging.getLogger(__name__)


class GophishAPIError(Exception):
    """Custom exception for Gophish API errors"""
    pass


class GophishAPIClient:
    """Client for interacting with Gophish API"""
    
    def __init__(self, base_url: str, api_key: str, verify_ssl: bool = True):
        """
        Initialize the Gophish API client
        
        Args:
            base_url: Base URL of the Gophish server
            api_key: API key for authentication
            verify_ssl: Whether to verify SSL certificates
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        
        # Disable SSL verification warnings
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Test connection on initialization
        self._test_connection()
    
    def _test_connection(self):
        """Test the connection to the Gophish API"""
        try:
            # First, test if the base URL is reachable
            logger.info(f"Testing connection to {self.base_url}")
            
            # Try the root endpoint first to see if it's a Gophish server
            try:
                root_response = self.session.get(
                    f"{self.base_url}/",
                    verify=False,
                    timeout=10
                )
                logger.info(f"Root endpoint response: HTTP {root_response.status_code}")
                if root_response.status_code == 200:
                    logger.info("Root endpoint accessible - this appears to be a web server")
            except Exception as e:
                logger.warning(f"Root endpoint test failed: {str(e)}")
            
            # Try multiple API endpoints to find one that works
            endpoints_to_try = [
                "/api/campaigns",      # Most common endpoint
                "/api/groups",         # Alternative endpoint
                "/api/templates",      # Templates endpoint
                "/api/pages",          # Landing pages endpoint
                "/api/smtp",           # SMTP profiles endpoint
                "/api/version",        # Version endpoint (if available)
                "/api/summary",        # Summary endpoint (if available)
                "/api/users",          # Users endpoint
                "/api/import",         # Import endpoint
            ]
            
            successful_endpoints = []
            failed_endpoints = []
            
            for endpoint in endpoints_to_try:
                try:
                    response = self.session.get(
                        f"{self.base_url}{endpoint}",
                        verify=False,  # Disable SSL verification for testing
                        timeout=10
                    )
                    
                    logger.info(f"Testing {endpoint}: HTTP {response.status_code}")
                    
                    if response.status_code == 200:
                        successful_endpoints.append(endpoint)
                        logger.info(f"✅ Successfully connected to Gophish at {self.base_url} via {endpoint}")
                        return
                    elif response.status_code == 401:
                        raise GophishAPIError(f"Authentication failed: Invalid API key (endpoint: {endpoint})")
                    elif response.status_code == 404:
                        failed_endpoints.append(f"{endpoint} (404)")
                        logger.debug(f"❌ Endpoint {endpoint} not found")
                        continue
                    else:
                        failed_endpoints.append(f"{endpoint} ({response.status_code})")
                        logger.warning(f"⚠️ Endpoint {endpoint} returned HTTP {response.status_code}")
                        continue
                        
                except requests.RequestException as e:
                    failed_endpoints.append(f"{endpoint} (error)")
                    logger.debug(f"❌ Endpoint {endpoint} failed: {str(e)}")
                    continue
            
            # If we get here, all endpoints failed
            error_msg = f"Failed to connect to Gophish: All API endpoints failed\n"
            error_msg += f"Successful endpoints: {successful_endpoints}\n"
            error_msg += f"Failed endpoints: {failed_endpoints}\n"
            error_msg += f"This might not be a Gophish server or the API is not enabled"
            
            raise GophishAPIError(error_msg)
            
        except requests.exceptions.SSLError as e:
            raise GophishAPIError(f"SSL certificate error: {str(e)}")
        except requests.exceptions.ConnectionError as e:
            raise GophishAPIError(f"Connection error: Cannot reach server at {self.base_url}")
        except requests.exceptions.Timeout as e:
            raise GophishAPIError(f"Connection timeout: Server did not respond within 10 seconds")
        except requests.RequestException as e:
            raise GophishAPIError(f"Connection failed: {str(e)}")
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, params: Optional[Dict] = None) -> Dict:
        """
        Make a request to the Gophish API
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint
            data: Request data for POST/PUT
            params: Query parameters
            
        Returns:
            Response data as dictionary
            
        Raises:
            GophishAPIError: If the request fails
        """
        url = f"{self.base_url}/api{endpoint}"
        
        logger.info(f"Making {method} request to: {url}")
        logger.info(f"Headers: {dict(self.session.headers)}")
        
        try:
            if method.upper() == 'GET':
                response = self.session.get(url, params=params, verify=self.verify_ssl, timeout=30)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=data, verify=self.verify_ssl, timeout=30)
            elif method.upper() == 'PUT':
                response = self.session.put(url, json=data, verify=self.verify_ssl, timeout=30)
            elif method.upper() == 'DELETE':
                response = self.session.delete(url, verify=self.verify_ssl, timeout=30)
            else:
                raise GophishAPIError(f"Unsupported HTTP method: {method}")
            
            # Handle response
            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Response headers: {dict(response.headers)}")
            
            if response.status_code in [200, 201]:
                try:
                    response_data = response.json()
                    logger.info(f"Response data: {response_data}")
                    return response_data
                except Exception as e:
                    logger.error(f"Failed to parse JSON response: {str(e)}")
                    logger.error(f"Raw response: {response.text}")
                    raise GophishAPIError(f"Invalid JSON response: {str(e)}")
            elif response.status_code == 404:
                logger.warning(f"Endpoint not found: {url}")
                raise GophishAPIError(f"Endpoint not found: {url}")
            else:
                error_msg = f"API request failed: {response.status_code}"
                try:
                    error_data = response.json()
                    logger.error(f"Error response: {error_data}")
                    if 'message' in error_data:
                        error_msg += f" - {error_data['message']}"
                except:
                    logger.error(f"Raw error response: {response.text}")
                    error_msg += f" - {response.text}"
                raise GophishAPIError(error_msg)
                
        except requests.RequestException as e:
            raise GophishAPIError(f"Request failed: {str(e)}")
    
    # Groups API methods
    def get_groups(self) -> List[Dict]:
        """Get all groups from Gophish"""
        return self._make_request('GET', '/groups')
    
    def get_group(self, group_id: str) -> Optional[Dict]:
        """Get a specific group by ID"""
        return self._make_request('GET', f'/groups/{group_id}')
    
    def create_group(self, group_data: Dict) -> Dict:
        """Create a new group"""
        return self._make_request('POST', '/groups', data=group_data)
    
    def update_group(self, group_id: str, group_data: Dict) -> Dict:
        """Update an existing group"""
        return self._make_request('PUT', f'/groups/{group_id}', data=group_data)
    
    def delete_group(self, group_id: str) -> bool:
        """Delete a group"""
        result = self._make_request('DELETE', f'/groups/{group_id}')
        return result is not None
    
    # Templates API methods
    def get_templates(self) -> List[Dict]:
        """Get all email templates"""
        return self._make_request('GET', '/templates')
    
    def get_template(self, template_id: str) -> Optional[Dict]:
        """Get a specific template by ID"""
        return self._make_request('GET', f'/templates/{template_id}')
    
    def create_template(self, template_data: Dict) -> Dict:
        """Create a new email template"""
        return self._make_request('POST', '/templates', data=template_data)
    
    def update_template(self, template_id: str, template_data: Dict) -> Dict:
        """Update an existing template"""
        return self._make_request('PUT', f'/templates/{template_id}', data=template_data)
    
    def delete_template(self, template_id: str) -> bool:
        """Delete a template"""
        result = self._make_request('DELETE', f'/templates/{template_id}')
        return result is not None
    
    # Landing Pages API methods
    def get_landing_pages(self) -> List[Dict]:
        """Get all landing pages"""
        return self._make_request('GET', '/pages')
    
    def get_landing_page(self, page_id: str) -> Optional[Dict]:
        """Get a specific landing page by ID"""
        return self._make_request('GET', f'/pages/{page_id}')
    
    def create_landing_page(self, page_data: Dict) -> Dict:
        """Create a new landing page"""
        return self._make_request('POST', '/pages', data=page_data)
    
    def update_landing_page(self, page_id: str, page_data: Dict) -> Dict:
        """Update an existing landing page"""
        return self._make_request('PUT', f'/pages/{page_id}', data=page_data)
    
    def delete_landing_page(self, page_id: str) -> bool:
        """Delete a landing page"""
        result = self._make_request('DELETE', f'/pages/{page_id}')
        return result is not None
    
    # Sending Profiles API methods
    def get_sending_profiles(self) -> List[Dict]:
        """Get all sending profiles"""
        return self._make_request('GET', '/smtp')
    
    def get_sending_profile(self, profile_id: str) -> Optional[Dict]:
        """Get a specific sending profile by ID"""
        return self._make_request('GET', f'/smtp/{profile_id}')
    
    def create_sending_profile(self, profile_data: Dict) -> Dict:
        """Create a new sending profile"""
        return self._make_request('POST', '/smtp', data=profile_data)
    
    def update_sending_profile(self, profile_id: str, profile_data: Dict) -> Dict:
        """Update an existing sending profile"""
        return self._make_request('PUT', f'/smtp/{profile_id}', data=profile_data)
    
    def delete_sending_profile(self, profile_id: str) -> bool:
        """Delete a sending profile"""
        result = self._make_request('DELETE', f'/smtp/{profile_id}')
        return result is not None
    
    # Campaigns API methods
    def get_campaigns(self) -> List[Dict]:
        """Get all campaigns"""
        return self._make_request('GET', '/campaigns')
    
    def get_campaign(self, campaign_id: str) -> Optional[Dict]:
        """Get a specific campaign by ID"""
        return self._make_request('GET', f'/campaigns/{campaign_id}')
    
    def create_campaign(self, campaign_data: Dict) -> Dict:
        """Create a new campaign"""
        return self._make_request('POST', '/campaigns', data=campaign_data)
    
    def update_campaign(self, campaign_id: str, campaign_data: Dict) -> Dict:
        """Update an existing campaign"""
        return self._make_request('PUT', f'/campaigns/{campaign_id}', data=campaign_data)
    
    def delete_campaign(self, campaign_id: str) -> bool:
        """Delete a campaign"""
        result = self._make_request('DELETE', f'/campaigns/{campaign_id}')
        return result is not None
    
    def launch_campaign(self, campaign_id: str) -> Dict:
        """Launch a campaign"""
        return self._make_request('POST', f'/campaigns/{campaign_id}/launch')
    
    def complete_campaign(self, campaign_id: str) -> Dict:
        """Complete a campaign"""
        return self._make_request('POST', f'/campaigns/{campaign_id}/complete')
    
    def get_campaign_results(self, campaign_id: str) -> Dict:
        """Get campaign results and statistics"""
        return self._make_request('GET', f'/campaigns/{campaign_id}/results')
    
    def get_campaign_events(self, campaign_id: str) -> List[Dict]:
        """Get campaign events"""
        return self._make_request('GET', f'/campaigns/{campaign_id}/results')
    
    # Webhooks API methods
    def get_webhooks(self) -> List[Dict]:
        """Get all webhooks"""
        return self._make_request('GET', '/webhooks')
    
    def create_webhook(self, webhook_data: Dict) -> Dict:
        """Create a new webhook"""
        return self._make_request('POST', '/webhooks', data=webhook_data)
    
    def delete_webhook(self, webhook_id: str) -> bool:
        """Delete a webhook"""
        result = self._make_request('DELETE', f'/webhooks/{webhook_id}')
        return result is not None
    
    # Utility methods
    def get_version(self) -> Dict:
        """Get Gophish version information"""
        try:
            return self._make_request('GET', '/version')
        except GophishAPIError:
            # If version endpoint doesn't exist, return a default response
            logger.warning("Version endpoint not available, using default response")
            return {'version': 'Unknown', 'build': 'Unknown'}
    
    def get_summary_stats(self) -> Dict:
        """Get summary statistics"""
        return self._make_request('GET', '/api/summary')
    
    def export_campaign_results(self, campaign_id: str, format: str = 'csv') -> bytes:
        """
        Export campaign results
        
        Args:
            campaign_id: Campaign ID to export
            format: Export format (csv, json)
            
        Returns:
            Exported data as bytes
        """
        url = f"{self.base_url}/api/campaigns/{campaign_id}/export"
        params = {'format': format}
        
        try:
            response = self.session.get(url, params=params, verify=self.verify_ssl, timeout=60)
            if response.status_code == 200:
                return response.content
            else:
                raise GophishAPIError(f"Export failed: {response.status_code}")
        except requests.RequestException as e:
            raise GophishAPIError(f"Export request failed: {str(e)}")


class GophishAPIManager:
    """Manager class for handling multiple Gophish servers"""
    
    def __init__(self):
        self.clients = {}
    
    def get_client(self, server) -> GophishAPIClient:
        """
        Get or create a client for a specific server
        
        Args:
            server: GophishServer model instance
            
        Returns:
            GophishAPIClient instance
        """
        server_key = f"{server.id}_{server.base_url}"
        
        if server_key not in self.clients:
            try:
                self.clients[server_key] = GophishAPIClient(
                    base_url=server.base_url,
                    api_key=server.api_key,
                    verify_ssl=False  # Disable SSL verification for self-signed certificates
                )
            except GophishAPIError as e:
                logger.error(f"Failed to create client for server {server.name}: {str(e)}")
                raise
        else:
            # Clear the cached client to ensure fresh SSL settings
            del self.clients[server_key]
            self.clients[server_key] = GophishAPIClient(
                base_url=server.base_url,
                api_key=server.api_key,
                verify_ssl=False  # Disable SSL verification for self-signed certificates
            )
        
        return self.clients[server_key]
    
    def test_server_connection(self, server) -> bool:
        """
        Test connection to a Gophish server
        
        Args:
            server: GophishServer model instance
            
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Try to get campaigns as a simple connection test
            client = self.get_client(server)
            client.get_campaigns()
            return True
        except GophishAPIError as e:
            logger.error(f"Connection test failed for server {server.name}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error testing connection to server {server.name}: {str(e)}")
            return False
    
    def clear_client_cache(self):
        """Clear the client cache"""
        self.clients.clear()


# Global instance
gophish_manager = GophishAPIManager()
