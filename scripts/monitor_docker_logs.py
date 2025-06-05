#!/usr/bin/env python3
"""
Docker Compose Log Monitor with color-coded output and JSON parsing.

Usage:
    ./monitor_docker_logs.py [container_name_filter]
    
Example:
    ./monitor_docker_logs.py          # Monitor all containers
    ./monitor_docker_logs.py backend  # Monitor only backend container
"""

import subprocess
import json
import sys
import re
from datetime import datetime
from collections import defaultdict

# ANSI color codes
COLORS = {
    'backend': '\033[34m',      # Blue
    'transcoder': '\033[32m',   # Green
    'frontend': '\033[36m',     # Cyan
    'default': '\033[37m',      # White
}

LOG_LEVEL_COLORS = {
    'ERROR': '\033[91m',        # Bright Red
    'WARNING': '\033[93m',      # Yellow
    'INFO': '\033[92m',         # Green
    'DEBUG': '\033[94m',        # Blue
}

RESET = '\033[0m'
BOLD = '\033[1m'
DIM = '\033[2m'

# Container name mapping (extract service name from full container name)
container_colors = defaultdict(lambda: COLORS['default'])

def get_container_color(container_name):
    """Get color based on container service name."""
    if 'backend' in container_name:
        return COLORS['backend']
    elif 'transcoder' in container_name:
        return COLORS['transcoder']
    elif 'frontend' in container_name:
        return COLORS['frontend']
    return COLORS['default']

def parse_json_log(log_line):
    """Parse JSON log and extract key fields."""
    try:
        data = json.loads(log_line)
        timestamp = data.get('timestamp', '')
        level = data.get('level', 'INFO')
        message = data.get('message', '')
        module = data.get('module', '')
        
        # Format timestamp to be more readable
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                timestamp = dt.strftime('%H:%M:%S')
            except:
                timestamp = timestamp[:19]  # Just take YYYY-MM-DD HH:MM:SS part
        
        return {
            'timestamp': timestamp,
            'level': level,
            'message': message,
            'module': module,
            'full_data': data,
            'is_json': True
        }
    except json.JSONDecodeError:
        return None

def parse_werkzeug_log(log_line):
    """Parse werkzeug/Flask access logs."""
    # Pattern for werkzeug logs: INFO:werkzeug:172.18.0.4 - - [04/Jun/2025 16:08:09] "GET /api/recordings HTTP/1.1" 200 -
    werkzeug_pattern = r'(INFO|ERROR|WARNING):werkzeug:.*\[(.*?)\]\s+"(.*?)"\s+(\d+)'
    match = re.search(werkzeug_pattern, log_line)
    if match:
        level, timestamp, request, status_code = match.groups()
        return {
            'timestamp': timestamp.split()[1] if ' ' in timestamp else timestamp,
            'level': level,
            'message': f"{request} -> {status_code}",
            'module': 'werkzeug',
            'is_json': False
        }
    return None

def format_log_entry(container_name, log_data):
    """Format a log entry with colors."""
    container_color = get_container_color(container_name)
    
    # Extract container service name (e.g., "backend" from "90e08e2a299d_quickscribe-backend-1")
    service_name = 'unknown'
    if 'backend' in container_name:
        service_name = 'backend'
    elif 'transcoder' in container_name:
        service_name = 'transcoder'
    elif 'frontend' in container_name:
        service_name = 'frontend'
    
    # Format container name (fixed width for alignment)
    formatted_container = f"{container_color}{service_name:12}{RESET}"
    
    # Format log level with color
    level = log_data.get('level', 'INFO')
    level_color = LOG_LEVEL_COLORS.get(level, '')
    formatted_level = f"{level_color}{level:7}{RESET}"
    
    # Format timestamp
    timestamp = log_data.get('timestamp', '')
    formatted_timestamp = f"{DIM}{timestamp}{RESET}"
    
    # Format message
    message = log_data.get('message', '').strip()
    
    # For ERROR level, add additional context
    if level == 'ERROR' and log_data.get('is_json') and log_data.get('full_data'):
        extra_info = []
        full_data = log_data['full_data']
        if 'module' in full_data:
            extra_info.append(f"module: {full_data['module']}")
        if 'function' in full_data:
            extra_info.append(f"func: {full_data['function']}")
        if 'line' in full_data:
            extra_info.append(f"line: {full_data['line']}")
        
        if extra_info:
            message += f" {DIM}[{', '.join(extra_info)}]{RESET}"
    
    return f"{formatted_container} {formatted_timestamp} {formatted_level} {message}"

def process_log_line(line):
    """Process a single log line."""
    # Split container name and log content
    parts = line.split(' | ', 1)
    if len(parts) != 2:
        return None
    
    container_name, log_content = parts
    container_name = container_name.strip()
    log_content = log_content.strip()
    
    # Try to parse as JSON first
    log_data = parse_json_log(log_content)
    
    # If not JSON, try werkzeug format
    if not log_data:
        log_data = parse_werkzeug_log(log_content)
    
    # If still no match, create a simple log entry
    if not log_data:
        # Skip traceback lines
        if line.strip().startswith('Traceback') or line.strip().startswith('File ') or '^^^' in line:
            return None
        
        log_data = {
            'timestamp': '',
            'level': 'INFO',
            'message': log_content,
            'module': '',
            'is_json': False
        }
    
    return container_name, log_data

def main():
    """Main function to monitor docker compose logs."""
    # Check if a container filter is provided
    container_filter = sys.argv[1] if len(sys.argv) > 1 else None
    
    # Build docker compose command
    cmd = ['docker', 'compose', 'logs', '-f', '--tail', '50']
    if container_filter:
        cmd.append(container_filter)
    
    print(f"{BOLD}Starting Docker Compose Log Monitor...{RESET}")
    print(f"{DIM}Press Ctrl+C to stop{RESET}\n")
    
    try:
        # Start the docker compose logs process
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, bufsize=1)
        
        # Process each line as it comes in
        for line in process.stdout:
            line = line.rstrip()
            if not line:
                continue
            
            result = process_log_line(line)
            if result:
                container_name, log_data = result
                formatted_line = format_log_entry(container_name, log_data)
                print(formatted_line)
        
    except KeyboardInterrupt:
        print(f"\n{DIM}Stopped monitoring logs{RESET}")
        sys.exit(0)
    except Exception as e:
        print(f"{LOG_LEVEL_COLORS['ERROR']}Error: {e}{RESET}")
        sys.exit(1)

if __name__ == '__main__':
    main()