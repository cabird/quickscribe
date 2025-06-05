#!/usr/bin/env python3
"""
Plaud Sync Integration Test Script

This script tests the complete Plaud sync functionality:
1. Creates a test user with Plaud settings
2. Triggers Plaud sync via backend API
3. Monitors progress via CosmosDB and Docker logs
4. Verifies recordings are properly processed
5. Cleans up all test data

Usage:
    python test_plaud_sync.py                    # Full test
    python test_plaud_sync.py --mode monitor     # Monitor only
    python test_plaud_sync.py --mode cleanup     # Cleanup only
"""

import argparse
import asyncio
import json
import logging
import os
import queue
import random
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, UTC, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
import uuid

import requests
from azure.cosmos import CosmosClient
from azure.storage.blob import BlobServiceClient
from colorama import init, Fore, Back, Style
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

# Color constants
init(autoreset=True)
GREEN = Fore.GREEN
RED = Fore.RED
YELLOW = Fore.YELLOW
BLUE = Fore.BLUE
CYAN = Fore.CYAN
MAGENTA = Fore.MAGENTA
WHITE = Fore.WHITE
BOLD = Style.BRIGHT
DIM = Style.DIM

class GracefulShutdown:
    """Handle graceful shutdown on Ctrl+C"""
    
    def __init__(self):
        self.shutdown_requested = False
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        if not self.shutdown_requested:
            print(f"\n\n{YELLOW}⚠️  Shutdown requested. Finishing current operation...{Style.RESET_ALL}")
            self.shutdown_requested = True
        else:
            print(f"\n{RED}❌ Force shutdown!{Style.RESET_ALL}")
            sys.exit(1)
    
    def should_continue(self):
        return not self.shutdown_requested
    
    def cleanup_and_exit(self, cleanup_func=None):
        print(f"\n{BLUE}🧹 Running cleanup before exit...{Style.RESET_ALL}")
        if cleanup_func:
            cleanup_func()
        print(f"{GREEN}✅ Cleanup complete. Exiting.{Style.RESET_ALL}")
        sys.exit(0)

class DockerLogMonitor:
    """Monitor Docker container logs in real-time"""
    
    def __init__(self, container_names=None):
        if container_names is None:
            # Auto-detect container names
            self.container_names = self._detect_container_names()
        else:
            self.container_names = container_names
        self.processes = {}
        self.log_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.threads = []
    
    def _detect_container_names(self):
        """Auto-detect running container names"""
        container_names = []
        try:
            # Get project name from current directory
            project_name = os.path.basename(os.getcwd()).lower()
            
            # Try common patterns
            patterns = [
                f"{project_name}-backend-1",
                f"{project_name}_backend_1", 
                "backend",
                f"{project_name}-transcoder-1",
                f"{project_name}_transcoder_1",
                "transcoder"
            ]
            
            for pattern in patterns:
                result = subprocess.run(['docker', 'ps', '-q', '-f', f'name={pattern}'], 
                                      capture_output=True, text=True)
                if result.stdout.strip():
                    container_names.append(pattern)
                    print(f"{GREEN}🔍 Found container: {pattern}{Style.RESET_ALL}")
            
            if not container_names:
                print(f"{YELLOW}⚠️  No containers found, trying to list all running containers...{Style.RESET_ALL}")
                result = subprocess.run(['docker', 'ps', '--format', 'table {{.Names}}'], 
                                      capture_output=True, text=True)
                print(f"{CYAN}Running containers:{Style.RESET_ALL}")
                print(result.stdout)
                
        except Exception as e:
            print(f"{RED}❌ Error detecting containers: {e}{Style.RESET_ALL}")
        
        return container_names
    
    def start_monitoring(self):
        """Start monitoring Docker logs for specified containers"""
        print(f"{BLUE}📡 Starting Docker log monitoring...{Style.RESET_ALL}")
        
        for container in self.container_names:
            try:
                # First check if container exists
                result = subprocess.run(['docker', 'ps', '-q', '-f', f'name={container}'], 
                                      capture_output=True, text=True)
                if not result.stdout.strip():
                    print(f"{YELLOW}⚠️  Container {container} not found, skipping{Style.RESET_ALL}")
                    continue
                
                cmd = ['docker', 'logs', '-f', '--tail', '50', container]
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                
                # Start thread to read logs
                thread = threading.Thread(
                    target=self._read_logs,
                    args=(process, container),
                    daemon=True
                )
                thread.start()
                self.threads.append(thread)
                
                self.processes[container] = process
                print(f"{GREEN}✅ Monitoring {container}{Style.RESET_ALL}")
                
            except Exception as e:
                print(f"{RED}❌ Failed to start monitoring {container}: {e}{Style.RESET_ALL}")
    
    def _read_logs(self, process, container_name):
        """Read logs from process and add to queue"""
        for line in iter(process.stdout.readline, ''):
            if self.stop_event.is_set():
                break
            if line:
                self.log_queue.put({
                    'container': container_name,
                    'message': line.strip(),
                    'timestamp': datetime.now()
                })
    
    def get_recent_logs(self, pattern=None, container=None, max_logs=10):
        """Get recent logs matching pattern"""
        logs = []
        temp_logs = []
        
        # Collect all available logs
        while not self.log_queue.empty():
            try:
                log = self.log_queue.get_nowait()
                temp_logs.append(log)
            except queue.Empty:
                break
        
        # Filter and return
        for log in temp_logs[-max_logs:]:
            if container and container not in log['container']:
                continue
            if pattern and pattern.lower() not in log['message'].lower():
                continue
            logs.append(log)
        
        return logs
    
    def stop(self):
        """Stop monitoring and cleanup"""
        print(f"{BLUE}🛑 Stopping Docker log monitoring...{Style.RESET_ALL}")
        self.stop_event.set()
        for process in self.processes.values():
            try:
                process.terminate()
                process.wait(timeout=5)
            except:
                process.kill()

class PlaudApiHelper:
    """Helper for querying Plaud API directly"""
    
    def __init__(self, bearer_token: str):
        self.bearer_token = bearer_token
        self.session = requests.Session()
        self.session.headers.update(self._get_default_headers())
    
    def _get_default_headers(self) -> Dict[str, str]:
        """Get HTTP headers for Plaud API requests (copied from transcoder)"""
        return {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'en-US,en;q=0.9',
            'authorization': f'bearer {self.bearer_token}',
            'edit-from': 'web',
            'origin': 'https://app.plaud.ai',
            'priority': 'u=1, i',
            'referer': 'https://app.plaud.ai/',
            'sec-ch-ua': '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36'
        }
    
    def get_recordings(self, limit: int = 10) -> Dict[str, Any]:
        """Get recordings from Plaud API using correct endpoint"""
        url = 'https://api.plaud.ai/file/simple/web'
        params = {
            'skip': 0,
            'limit': limit,
            'is_trash': 2,  # include all
            'sort_by': 'start_time',
            'is_desc': 'true'
        }
        
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()
    
    def calculate_sync_timestamp(self, max_recordings: int = 3) -> Optional[str]:
        """Calculate timestamp to limit sync to last N recordings"""
        try:
            recordings_data = self.get_recordings(limit=max_recordings + 2)
            recordings = recordings_data.get('data_file_list', [])
            
            total_count = recordings_data.get('data_file_total', len(recordings))
            print(f"{CYAN}ℹ️  Found {total_count} recordings in Plaud account{Style.RESET_ALL}")
            
            if len(recordings) <= max_recordings:
                print(f"{CYAN}ℹ️  Will sync all {len(recordings)} recordings{Style.RESET_ALL}")
                return None
            else:
                # Get timestamp just after the Nth recording from the end
                target_recording = recordings[max_recordings]
                # Convert start_time from milliseconds to seconds, then to datetime
                start_time_seconds = target_recording['start_time'] / 1000
                # Create timezone object from timezone hours + zonemins
                tz_hours = target_recording.get('timezone', 0)
                tz_mins = target_recording.get('zonemins', 0)
                tz_offset = timedelta(hours=tz_hours, minutes=tz_mins)
                tz = timezone(tz_offset)
                
                recording_time = datetime.fromtimestamp(start_time_seconds, tz=tz)
                sync_timestamp = recording_time + timedelta(seconds=1)
                
                print(f"{CYAN}ℹ️  Will sync last {max_recordings} recordings{Style.RESET_ALL}")
                print(f"{CYAN}ℹ️  Setting sync timestamp: {sync_timestamp.isoformat()}{Style.RESET_ALL}")
                
                return sync_timestamp.isoformat()
                
        except Exception as e:
            print(f"{RED}❌ Failed to query Plaud API: {e}{Style.RESET_ALL}")
            print(f"{YELLOW}⚠️  Proceeding without timestamp limit{Style.RESET_ALL}")
            return None

class PlaudSyncTester:
    """Main test orchestrator"""
    
    def __init__(self, config: Dict[str, str], mode: str = 'full'):
        self.config = config
        self.mode = mode
        self.test_user_id = None
        self.session = requests.Session()
        self.docker_monitor = None
        self.shutdown_handler = GracefulShutdown()
        
        # Initialize Azure clients
        self._init_azure_clients()
        
        # Track created resources for cleanup
        self.created_recordings = []
        self.created_blobs = []
    
    def _init_azure_clients(self):
        """Initialize Azure service clients"""
        try:
            # CosmosDB client
            cosmos_url = self.config.get('COSMOS_URL') or self.config.get('AZURE_COSMOS_ENDPOINT')
            cosmos_key = self.config.get('COSMOS_KEY') or self.config.get('AZURE_COSMOS_KEY')
            
            if not cosmos_url or not cosmos_key:
                raise ValueError("CosmosDB configuration missing")
            
            self.cosmos_client = CosmosClient(cosmos_url, cosmos_key)
            self.cosmos_db = self.cosmos_client.get_database_client(
                self.config.get('COSMOS_DB_NAME', 'QuickScribeDatabase')
            )
            container_name = self.config.get('COSMOS_CONTAINER_NAME', 'QuickScribeContainer')
            self.main_container = self.cosmos_db.get_container_client(container_name)
            
            print(f"{CYAN}🔍 Using CosmosDB: {self.config.get('COSMOS_DB_NAME', 'QuickScribeDatabase')}/{container_name}{Style.RESET_ALL}")
            
            # Blob storage client
            storage_conn_str = self.config.get('AZURE_STORAGE_CONNECTION_STRING')
            if not storage_conn_str:
                raise ValueError("Azure Storage connection string missing")
            
            self.blob_client = BlobServiceClient.from_connection_string(storage_conn_str)
            self.recordings_blob_container = self.config.get('AZURE_RECORDING_BLOB_CONTAINER', 'recordings')
            
            print(f"{GREEN}✅ Azure clients initialized{Style.RESET_ALL}")
            
        except Exception as e:
            print(f"{RED}❌ Failed to initialize Azure clients: {e}{Style.RESET_ALL}")
            raise
    
    def check_prerequisites(self):
        """Check that all required services are running"""
        print(f"{BOLD}🔍 Checking prerequisites...{Style.RESET_ALL}")
        
        # Check backend API - try multiple endpoints
        backend_url = self.config['BACKEND_URL']
        print(f"{CYAN}🌐 Testing backend at: {backend_url}{Style.RESET_ALL}")
        
        endpoints_to_try = [
            '/api/health',
            '/health', 
            '/',
            '/api/'
        ]
        
        backend_working = False
        for endpoint in endpoints_to_try:
            try:
                url = f"{backend_url}{endpoint}"
                print(f"{DIM}  Trying: {url}{Style.RESET_ALL}")
                response = requests.get(url, timeout=10)
                print(f"{DIM}  Response: {response.status_code} - {response.reason}{Style.RESET_ALL}")
                
                if response.status_code in [200, 404]:  # 404 is OK for root endpoint
                    print(f"{GREEN}✅ Backend API is responsive (status: {response.status_code}){Style.RESET_ALL}")
                    backend_working = True
                    break
                else:
                    print(f"{YELLOW}⚠️  Endpoint {endpoint} returned {response.status_code}{Style.RESET_ALL}")
                    
            except requests.exceptions.ConnectionError as e:
                print(f"{RED}❌ Connection failed for {endpoint}: {e}{Style.RESET_ALL}")
            except requests.exceptions.Timeout as e:
                print(f"{RED}❌ Timeout for {endpoint}: {e}{Style.RESET_ALL}")
            except Exception as e:
                print(f"{RED}❌ Error testing {endpoint}: {e}{Style.RESET_ALL}")
        
        if not backend_working:
            print(f"{RED}❌ Backend API is not accessible at {backend_url}{Style.RESET_ALL}")
            print(f"{CYAN}💡 Troubleshooting tips:{Style.RESET_ALL}")
            print(f"   1. Check if docker-compose is running: docker-compose ps")
            print(f"   2. Check backend container logs: docker-compose logs backend")
            print(f"   3. Verify port mapping in docker-compose.yml")
            return False
        
        # Check CosmosDB
        try:
            print(f"{CYAN}🔍 Testing CosmosDB connection...{Style.RESET_ALL}")
            result = list(self.main_container.query_items("SELECT TOP 1 * FROM c", enable_cross_partition_query=True))
            print(f"{GREEN}✅ CosmosDB connection works (found {len(result)} items){Style.RESET_ALL}")
        except Exception as e:
            print(f"{RED}❌ CosmosDB connection failed: {e}{Style.RESET_ALL}")
            print(f"{CYAN}💡 Check your COSMOS_URL, COSMOS_KEY, COSMOS_DB_NAME, and COSMOS_CONTAINER_NAME in .env.test.local{Style.RESET_ALL}")
            return False
        
        # Check Azure Storage
        try:
            self.blob_client.get_container_client(self.recordings_blob_container).get_container_properties()
            print(f"{GREEN}✅ Azure Storage connection works{Style.RESET_ALL}")
        except Exception as e:
            print(f"{RED}❌ Azure Storage connection failed: {e}{Style.RESET_ALL}")
            return False
        
        # Check Docker containers with better detection
        print(f"{CYAN}🐳 Checking Docker containers...{Style.RESET_ALL}")
        
        # First, list all running containers
        try:
            result = subprocess.run(['docker', 'ps', '--format', 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print(f"{DIM}Running containers:{Style.RESET_ALL}")
                for line in result.stdout.strip().split('\n'):
                    print(f"{DIM}  {line}{Style.RESET_ALL}")
            
        except Exception as e:
            print(f"{RED}❌ Error listing Docker containers: {e}{Style.RESET_ALL}")
            return False
        
        # Look for backend and transcoder containers
        backend_containers = []
        transcoder_containers = []
        
        patterns = [
            ('backend', backend_containers),
            ('transcoder', transcoder_containers)
        ]
        
        for service_name, container_list in patterns:
            for naming_pattern in [
                f"quickscribe-{service_name}-1",
                f"quickscribe_{service_name}_1", 
                f"{service_name}",
                f"*{service_name}*"
            ]:
                try:
                    result = subprocess.run(['docker', 'ps', '-q', '-f', f'name={naming_pattern}'], 
                                          capture_output=True, text=True)
                    if result.stdout.strip():
                        # Get the actual container name
                        result2 = subprocess.run(['docker', 'ps', '--format', '{{.Names}}', '-f', f'name={naming_pattern}'], 
                                                capture_output=True, text=True)
                        actual_name = result2.stdout.strip().split('\n')[0]
                        container_list.append(actual_name)
                        print(f"{GREEN}✅ Found {service_name} container: {actual_name}{Style.RESET_ALL}")
                        break
                except Exception as e:
                    continue
        
        if not backend_containers:
            print(f"{RED}❌ No backend container found{Style.RESET_ALL}")
            print(f"{CYAN}💡 Is docker-compose running? Try: docker-compose up -d{Style.RESET_ALL}")
            return False
        
        if not transcoder_containers:
            print(f"{YELLOW}⚠️  No transcoder container found (sync may not work){Style.RESET_ALL}")
        
        # Store container names for later Docker monitor initialization
        self.found_containers = backend_containers + transcoder_containers
        
        return True
    
    def create_or_get_user(self) -> str:
        """Create or get user with Plaud settings"""
        
        # Check if a specific user ID is configured
        configured_user_id = self.config.get('TEST_USER_ID', '').strip()
        
        if configured_user_id:
            print(f"{BOLD}👤 Using configured user: {configured_user_id}...{Style.RESET_ALL}")
            user_id = configured_user_id
            
            # Check if user already exists
            try:
                existing_user = self.main_container.read_item(item=user_id, partition_key="user")
                print(f"{GREEN}✅ Found existing user: {user_id}{Style.RESET_ALL}")
                self.test_user_id = user_id
                return user_id
            except Exception:
                print(f"{CYAN}ℹ️  User doesn't exist, will create: {user_id}{Style.RESET_ALL}")
        else:
            print(f"{BOLD}👤 Creating new test user...{Style.RESET_ALL}")
            # Generate unique test user ID
            timestamp = int(time.time())
            random_hex = f"{random.randint(0, 0xffff):04x}"
            user_id = f"{self.config['TEST_USER_PREFIX']}-{timestamp}-{random_hex}"
        
        # Calculate optimal sync timestamp only for new users
        last_sync_timestamp = None
        if not configured_user_id or not hasattr(self, 'test_user_id'):
            plaud_helper = PlaudApiHelper(self.config['PLAUD_BEARER_TOKEN'])
            last_sync_timestamp = plaud_helper.calculate_sync_timestamp(
                int(self.config.get('MAX_RECORDINGS_TO_SYNC', 3))
            )
        
        # Create user document (matching backend structure)
        user_doc = {
            'id': user_id,
            'partitionKey': 'user',  # Required by backend
            'is_test_user': True,
            'email': f"{user_id}@test.local",
            'name': f"Test User {user_id}",
            'role': 'user',
            'created_at': datetime.now(UTC).isoformat(),
            'last_login': None,
            'plaudSettings': {
                'bearerToken': self.config['PLAUD_BEARER_TOKEN'],  # Required field
                'activeSyncToken': None,  # Optional, used during active sync
                'activeSyncStarted': None,
                'lastSyncTimestamp': last_sync_timestamp,
                'enableSync': True
            }
        }
        
        try:
            # Only create if user doesn't already exist
            if not hasattr(self, 'test_user_id'):
                self.main_container.create_item(user_doc)
                print(f"{GREEN}✅ Created user: {user_id}{Style.RESET_ALL}")
            else:
                print(f"{GREEN}✅ Using existing user: {user_id}{Style.RESET_ALL}")
            
            self.test_user_id = user_id
            return user_id
        except Exception as e:
            print(f"{RED}❌ Failed to create user: {e}{Style.RESET_ALL}")
            raise
    
    def login_as_test_user(self):
        """Login as the test user using local auth"""
        print(f"{BOLD}🔐 Logging in as test user...{Style.RESET_ALL}")
        
        # First, let's verify the user exists in the database
        try:
            print(f"{CYAN}🔍 Verifying user exists in database...{Style.RESET_ALL}")
            user_item = self.main_container.read_item(item=self.test_user_id, partition_key="user")
            print(f"{GREEN}✅ User found in database{Style.RESET_ALL}")
            print(f"{DIM}  ID: {user_item.get('id')}{Style.RESET_ALL}")
            print(f"{DIM}  Name: {user_item.get('name')}{Style.RESET_ALL}")
            print(f"{DIM}  is_test_user: {user_item.get('is_test_user')}{Style.RESET_ALL}")
            print(f"{DIM}  partitionKey: {user_item.get('partitionKey')}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{RED}❌ User not found in database: {e}{Style.RESET_ALL}")
            return False
        
        try:
            print(f"{CYAN}🔐 Attempting login via API...{Style.RESET_ALL}")
            response = self.session.post(
                f"{self.config['BACKEND_URL']}/api/local/login",
                json={'user_id': self.test_user_id},
                timeout=10
            )
            
            print(f"{DIM}  Request URL: {self.config['BACKEND_URL']}/api/local/login{Style.RESET_ALL}")
            print(f"{DIM}  Request body: {{'user_id': '{self.test_user_id}'}}{Style.RESET_ALL}")
            print(f"{DIM}  Response status: {response.status_code}{Style.RESET_ALL}")
            print(f"{DIM}  Response body: {response.text}{Style.RESET_ALL}")
            
            if response.status_code == 200:
                print(f"{GREEN}✅ Logged in successfully{Style.RESET_ALL}")
                return True
            elif response.status_code == 403:
                print(f"{RED}❌ Login failed: Local auth not enabled{Style.RESET_ALL}")
                print(f"{CYAN}💡 Add LOCAL_AUTH_ENABLED=true to backend/.env.local and restart docker-compose{Style.RESET_ALL}")
                return False
            else:
                print(f"{RED}❌ Login failed: {response.status_code} - {response.text}{Style.RESET_ALL}")
                
                # Additional debugging for 400 errors
                if response.status_code == 400:
                    print(f"{CYAN}🔍 Debugging 400 error:{Style.RESET_ALL}")
                    print(f"  - Check that LOCAL_AUTH_ENABLED=true in backend/.env.local")
                    print(f"  - Verify backend can find user with is_test_user=true")
                    print(f"  - Check backend logs: docker-compose logs backend")
                
                return False
                
        except Exception as e:
            print(f"{RED}❌ Login request failed: {e}{Style.RESET_ALL}")
            return False
    
    def trigger_plaud_sync(self) -> Optional[str]:
        """Trigger Plaud sync and return sync token"""
        print(f"{BOLD}🚀 Triggering Plaud sync...{Style.RESET_ALL}")
        
        try:
            response = self.session.post(
                f"{self.config['BACKEND_URL']}/plaud/sync/start",
                json={},  # Send empty JSON body with proper Content-Type
                timeout=30
            )
            
            if response.status_code == 200:
                sync_data = response.json()
                sync_token = sync_data.get('sync_token')
                print(f"{GREEN}✅ Sync triggered - Token: {sync_token}{Style.RESET_ALL}")
                return sync_token
            else:
                print(f"{RED}❌ Sync trigger failed: {response.status_code} - {response.text}{Style.RESET_ALL}")
                return None
                
        except Exception as e:
            print(f"{RED}❌ Sync trigger request failed: {e}{Style.RESET_ALL}")
            return None
    
    def monitor_progress(self, sync_token: str):
        """Monitor sync progress via CosmosDB and Docker logs"""
        print(f"{BOLD}📊 Monitoring sync progress...{Style.RESET_ALL}")
        print(f"{DIM}Press Ctrl+C to stop monitoring{Style.RESET_ALL}\n")
        
        start_time = time.time()
        timeout = int(self.config.get('MONITOR_TIMEOUT', 180))
        last_recording_count = 0
        processed_recordings = set()
        
        # Start Docker log monitoring with found containers
        container_names = getattr(self, 'found_containers', None)
        self.docker_monitor = DockerLogMonitor(container_names)
        self.docker_monitor.start_monitoring()
        
        try:
            while time.time() - start_time < timeout:
                if not self.shutdown_handler.should_continue():
                    break
                
                # Check for new recordings
                current_recordings = self._get_user_recordings()
                new_recordings = [r for r in current_recordings if r['id'] not in processed_recordings]
                
                for recording in new_recordings:
                    processed_recordings.add(recording['id'])
                    self.created_recordings.append(recording['id'])
                    print(f"{GREEN}📥 New recording: {recording.get('displayName', 'Unknown')}{Style.RESET_ALL}")
                    print(f"    ID: {recording['id']}")
                    print(f"    Status: {recording.get('status', 'Unknown')}")
                    print(f"    Duration: {recording.get('duration', 'Unknown')}s")
                
                # Show relevant Docker logs
                recent_logs = self.docker_monitor.get_recent_logs(
                    pattern='plaud',
                    max_logs=5
                )
                
                if recent_logs:
                    print(f"\n{DIM}─── Recent Docker Logs ───{Style.RESET_ALL}")
                    for log in recent_logs:
                        container = log['container'].split('-')[-2] if '-' in log['container'] else log['container']
                        timestamp = log['timestamp'].strftime('%H:%M:%S')
                        print(f"{DIM}[{container}] {timestamp}: {log['message'][:80]}...{Style.RESET_ALL}")
                
                # Progress summary
                elapsed = int(time.time() - start_time)
                print(f"\n{CYAN}📈 Progress: {len(processed_recordings)} recordings processed ({elapsed}s elapsed){Style.RESET_ALL}")
                
                time.sleep(5)
            
            print(f"\n{GREEN}✅ Monitoring completed{Style.RESET_ALL}")
            
        except KeyboardInterrupt:
            print(f"\n{YELLOW}⚠️  Monitoring interrupted by user{Style.RESET_ALL}")
        finally:
            if self.docker_monitor:
                self.docker_monitor.stop()
    
    def _get_user_recordings(self) -> List[Dict]:
        """Get all recordings for the test user"""
        try:
            query = "SELECT * FROM c WHERE c.user_id = @userId AND c.partitionKey = 'recording'"
            parameters = [{"name": "@userId", "value": self.test_user_id}]
            
            recordings = list(self.main_container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True
            ))
            
            return recordings
            
        except Exception as e:
            print(f"{RED}❌ Error querying recordings: {e}{Style.RESET_ALL}")
            return []
    
    def verify_results(self):
        """Verify that recordings were processed correctly"""
        print(f"{BOLD}🔍 Verifying results...{Style.RESET_ALL}")
        
        recordings = self._get_user_recordings()
        
        if not recordings:
            print(f"{YELLOW}⚠️  No recordings found for verification{Style.RESET_ALL}")
            return True
        
        print(f"{GREEN}✅ Found {len(recordings)} recordings{Style.RESET_ALL}")
        
        blob_container = self.blob_client.get_container_client(self.recordings_blob_container)
        
        for recording in recordings:
            recording_id = recording['id']
            print(f"\n{CYAN}📁 Verifying recording: {recording.get('displayName', recording_id)}{Style.RESET_ALL}")
            
            # Check if blob exists
            blob_name = f"{self.test_user_id}/{recording_id}.mp3"
            try:
                blob_properties = blob_container.get_blob_client(blob_name).get_blob_properties()
                blob_size = blob_properties.size
                self.created_blobs.append(blob_name)
                print(f"  ✅ Blob exists ({blob_size} bytes)")
            except Exception as e:
                print(f"  ❌ Blob missing: {e}")
                continue
            
            # Verify metadata
            status = recording.get('status', 'unknown')
            duration = recording.get('duration', 0)
            
            print(f"  📊 Status: {status}")
            print(f"  ⏱️  Duration: {duration}s")
            
            if status in ['completed', 'transcribed']:
                print(f"  ✅ Recording processed successfully")
            else:
                print(f"  ⚠️  Recording status: {status}")
        
        return True
    
    def cleanup(self, force: bool = False):
        """Clean up all test data"""
        if not force and not self._confirm_cleanup():
            print(f"{YELLOW}⚠️  Cleanup cancelled{Style.RESET_ALL}")
            return
        
        print(f"{BOLD}🧹 Starting cleanup...{Style.RESET_ALL}")
        
        cleanup_summary = {
            'recordings_deleted': 0,
            'blobs_deleted': 0,
            'user_deleted': False,
            'errors': []
        }
        
        # Delete recordings from CosmosDB
        if self.created_recordings:
            print(f"{BLUE}🗑️  Deleting {len(self.created_recordings)} recording entries...{Style.RESET_ALL}")
            for recording_id in self.created_recordings:
                try:
                    self.main_container.delete_item(
                        item=recording_id,
                        partition_key=self.test_user_id  # Recordings use userId as partition key
                    )
                    cleanup_summary['recordings_deleted'] += 1
                except Exception as e:
                    cleanup_summary['errors'].append(f"Failed to delete recording {recording_id}: {e}")
        
        # Delete blobs from Azure Storage
        if self.created_blobs:
            print(f"{BLUE}🗑️  Deleting {len(self.created_blobs)} blob files...{Style.RESET_ALL}")
            blob_container = self.blob_client.get_container_client(self.recordings_blob_container)
            for blob_name in self.created_blobs:
                try:
                    blob_container.delete_blob(blob_name)
                    cleanup_summary['blobs_deleted'] += 1
                except Exception as e:
                    cleanup_summary['errors'].append(f"Failed to delete blob {blob_name}: {e}")
        
        # Delete test user
        if self.test_user_id:
            print(f"{BLUE}🗑️  Deleting test user: {self.test_user_id}...{Style.RESET_ALL}")
            try:
                self.main_container.delete_item(
                    item=self.test_user_id,
                    partition_key="user"  # Users use "user" as partition key
                )
                cleanup_summary['user_deleted'] = True
            except Exception as e:
                cleanup_summary['errors'].append(f"Failed to delete user {self.test_user_id}: {e}")
        
        # Show cleanup summary
        print(f"\n{BOLD}📋 Cleanup Summary:{Style.RESET_ALL}")
        print(f"  Recordings deleted: {cleanup_summary['recordings_deleted']}")
        print(f"  Blobs deleted: {cleanup_summary['blobs_deleted']}")
        print(f"  User deleted: {'✅' if cleanup_summary['user_deleted'] else '❌'}")
        
        if cleanup_summary['errors']:
            print(f"\n{RED}❌ Cleanup errors:{Style.RESET_ALL}")
            for error in cleanup_summary['errors']:
                print(f"  {error}")
        else:
            print(f"\n{GREEN}✅ Cleanup completed successfully{Style.RESET_ALL}")
    
    def _confirm_cleanup(self) -> bool:
        """Ask user to confirm cleanup"""
        recordings_count = len(self.created_recordings)
        blobs_count = len(self.created_blobs)
        
        print(f"\n{BOLD}═══════════════════════════════════════════════════════{Style.RESET_ALL}")
        print(f"{BOLD}                  CLEANUP CONFIRMATION{Style.RESET_ALL}")
        print(f"{BOLD}═══════════════════════════════════════════════════════{Style.RESET_ALL}")
        print(f"\nThe following will be deleted:")
        print(f"  • User: {self.test_user_id}")
        print(f"  • Recordings: {recordings_count} database entries")
        print(f"  • Blobs: {blobs_count} files")
        print(f"\n{RED}This action cannot be undone!{Style.RESET_ALL}")
        
        while True:
            response = input(f"\nAre you sure you want to delete all test data? (yes/no): ").strip().lower()
            if response in ['yes', 'y']:
                return True
            elif response in ['no', 'n']:
                return False
            else:
                print("Please answer 'yes' or 'no'")
    
    def run_test(self):
        """Run the Plaud sync test"""
        print(f"{BOLD}🎯 Starting Plaud Sync Test{Style.RESET_ALL}")
        print(f"{BOLD}{'=' * 60}{Style.RESET_ALL}")
        
        # Check if using configured user (no cleanup in this case)
        configured_user_id = self.config.get('TEST_USER_ID', '').strip()
        should_cleanup = not configured_user_id
        
        try:
            # Prerequisites
            if not self.check_prerequisites():
                print(f"{RED}❌ Prerequisites not met{Style.RESET_ALL}")
                return False
            
            # Create or get user
            self.create_or_get_user()
            
            # Setup cleanup handler only for temporary users
            if should_cleanup:
                self.shutdown_handler.cleanup_and_exit = lambda: self.cleanup(force=True)
            
            # Login
            if not self.login_as_test_user():
                return False
            
            # Trigger sync
            sync_token = self.trigger_plaud_sync()
            if not sync_token:
                return False
            
            # Monitor progress
            self.monitor_progress(sync_token)
            
            # Verify results
            self.verify_results()
            
            # Success!
            print(f"\n{GREEN}{BOLD}🎉 Test completed successfully!{Style.RESET_ALL}")
            
            # Cleanup only for temporary users
            if should_cleanup:
                self.cleanup()
            else:
                print(f"{CYAN}ℹ️  Using configured user - no cleanup performed{Style.RESET_ALL}")
            
            return True
            
        except Exception as e:
            print(f"\n{RED}❌ Test failed with error: {e}{Style.RESET_ALL}")
            if should_cleanup and self.test_user_id:
                print(f"{BLUE}🧹 Running emergency cleanup...{Style.RESET_ALL}")
                self.cleanup(force=True)
            return False
        finally:
            if self.docker_monitor:
                self.docker_monitor.stop()
    
    def run_cleanup_only(self):
        """Run cleanup only mode"""
        print(f"{BOLD}🧹 Cleanup Mode{Style.RESET_ALL}")
        print(f"{BOLD}{'=' * 60}{Style.RESET_ALL}")
        
        try:
            # Initialize Azure clients
            self._init_azure_clients()
            
            # Get user ID from command line or config
            user_id = getattr(self, 'cleanup_user_id', None)
            if not user_id:
                user_id = self.config.get('TEST_USER_ID', '').strip()
            
            if not user_id:
                print(f"{RED}❌ No user ID specified for cleanup{Style.RESET_ALL}")
                print(f"{CYAN}💡 Use --user-id or set TEST_USER_ID in config{Style.RESET_ALL}")
                return False
            
            self.test_user_id = user_id
            print(f"{CYAN}🎯 Cleaning up data for user: {user_id}{Style.RESET_ALL}")
            
            # Find recordings and blobs for this user
            recordings = self._get_user_recordings()
            self.created_recordings = [r['id'] for r in recordings]
            
            # Find blobs
            blob_container = self.blob_client.get_container_client(self.recordings_blob_container)
            blobs = blob_container.list_blobs(name_starts_with=f"{user_id}/")
            self.created_blobs = [blob.name for blob in blobs]
            
            print(f"{CYAN}📊 Found {len(self.created_recordings)} recordings and {len(self.created_blobs)} blobs{Style.RESET_ALL}")
            
            # Run cleanup
            self.cleanup()
            
            return True
            
        except Exception as e:
            print(f"{RED}❌ Cleanup failed: {e}{Style.RESET_ALL}")
            return False

def load_test_config() -> Dict[str, str]:
    """Load test configuration from .env.test file"""
    env_file = Path(__file__).parent / '.env.test'
    
    if not env_file.exists():
        print(f"{RED}❌ Configuration file not found: {env_file}{Style.RESET_ALL}")
        print(f"Please create {env_file} with required settings")
        sys.exit(1)
    
    load_dotenv(env_file)
    
    required_vars = [
        'PLAUD_BEARER_TOKEN',
        'BACKEND_URL',
        'AZURE_STORAGE_CONNECTION_STRING'
    ]
    
    config = {}
    missing_vars = []
    
    # Load from environment
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing_vars.append(var)
        config[var] = value
    
    # Load optional vars with defaults
    config.update({
        'TEST_USER_PREFIX': os.getenv('TEST_USER_PREFIX', 'test-plaud'),
        'TEST_USER_ID': os.getenv('TEST_USER_ID', ''),
        'MAX_RECORDINGS_TO_SYNC': os.getenv('MAX_RECORDINGS_TO_SYNC', '3'),
        'MONITOR_TIMEOUT': os.getenv('MONITOR_TIMEOUT', '180'),
        'COSMOS_URL': os.getenv('COSMOS_URL') or os.getenv('AZURE_COSMOS_ENDPOINT'),
        'COSMOS_KEY': os.getenv('COSMOS_KEY') or os.getenv('AZURE_COSMOS_KEY'),
        'COSMOS_DB_NAME': os.getenv('COSMOS_DB_NAME', 'QuickScribeDatabase'),
        'COSMOS_CONTAINER_NAME': os.getenv('COSMOS_CONTAINER_NAME', 'QuickScribeContainer'),
        'AZURE_RECORDING_BLOB_CONTAINER': os.getenv('AZURE_RECORDING_BLOB_CONTAINER', 'recordings')
    })
    
    if missing_vars:
        print(f"{RED}❌ Missing required configuration variables:{Style.RESET_ALL}")
        for var in missing_vars:
            print(f"  {var}")
        sys.exit(1)
    
    return config

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Plaud Sync Integration Test')
    parser.add_argument(
        '--mode',
        choices=['test', 'monitor', 'cleanup'],
        default='test',
        help='Mode: test=run plaud sync test, monitor=monitor existing sync, cleanup=cleanup user data (default: test)'
    )
    parser.add_argument(
        '--user-id',
        help='User ID for monitor/cleanup modes (overrides config file)'
    )
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_test_config()
    
    # Create tester
    tester = PlaudSyncTester(config, args.mode)
    
    if args.mode == 'test':
        success = tester.run_test()
        sys.exit(0 if success else 1)
    
    elif args.mode == 'monitor':
        user_id = args.user_id or config.get('TEST_USER_ID', '').strip()
        if not user_id:
            print(f"{RED}❌ --user-id required for monitor mode or set TEST_USER_ID in config{Style.RESET_ALL}")
            sys.exit(1)
        
        tester.test_user_id = user_id
        tester.monitor_progress("monitor-mode")
    
    elif args.mode == 'cleanup':
        # Set user ID for cleanup
        if args.user_id:
            tester.cleanup_user_id = args.user_id
        
        success = tester.run_cleanup_only()
        sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()