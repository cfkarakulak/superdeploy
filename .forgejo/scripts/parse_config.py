#!/usr/bin/env python3
"""
Parse project.yml configuration and extract service-specific information.
Usage: python parse_config.py <config_file> <service_name>
"""

import sys
import yaml
from pathlib import Path


def parse_config(config_file: str, service_name: str):
    """Parse project.yml and extract port configuration for a service."""
    try:
        config_path = Path(config_file)
        
        if not config_path.exists():
            print(f"ERROR: Configuration file not found: {config_file}", file=sys.stderr)
            sys.exit(1)
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Check if service exists in apps section
        if 'apps' not in config:
            print(f"ERROR: No 'apps' section found in {config_file}", file=sys.stderr)
            sys.exit(1)
        
        if service_name not in config['apps']:
            print(f"ERROR: Port configuration not found for service '{service_name}' in {config_file}", file=sys.stderr)
            sys.exit(1)
        
        service_config = config['apps'][service_name]
        
        # Extract port
        if 'port' not in service_config:
            print(f"ERROR: No 'port' field found for service '{service_name}' in {config_file}", file=sys.stderr)
            sys.exit(1)
        
        port = service_config['port']
        
        # Output ports in the format expected by the workflow
        # EXTERNAL_PORT INTERNAL_PORT (space-separated)
        # In most cases, they're the same value
        external_port = service_config.get('external_port', port)
        internal_port = service_config.get('internal_port', port)
        
        print(f"{external_port} {internal_port}")
        
    except yaml.YAMLError as e:
        print(f"ERROR: Failed to parse YAML file: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python parse_config.py <config_file> <service_name>", file=sys.stderr)
        sys.exit(1)
    
    config_file = sys.argv[1]
    service_name = sys.argv[2]
    
    parse_config(config_file, service_name)

