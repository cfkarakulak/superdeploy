#!/usr/bin/env python3
"""
Partial Up Script - Deploy only specified services
Usage: python partial_up.py "api,dashboard" "prod"
"""

import sys
import subprocess

def main():
    if len(sys.argv) < 2:
        print("Usage: partial_up.py <services> <environment>")
        sys.exit(1)
    
    services_str = sys.argv[1]
    environment = sys.argv[2] if len(sys.argv) > 2 else "prod"
    
    # Parse services
    services = [s.strip() for s in services_str.split(',')]
    
    print(f"🚀 Services to deploy: {services}")
    print(f"🌍 Environment: {environment}")
    
    # Determine compose files
    compose_files = ["-f", "docker-compose.core.yml", "-f", "docker-compose.apps.yml"]
    if environment == "staging":
        compose_files.extend(["-f", "docker-compose.apps.staging.yml"])
    
    # Deploy specified services (no-deps = don't restart dependencies)
    cmd = ["docker", "compose"] + compose_files + ["up", "-d", "--no-deps"] + services
    
    print(f"\n🔧 Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd="/opt/superdeploy/compose")
    
    if result.returncode == 0:
        print("\n✅ Deployment complete!")
    else:
        print("\n❌ Deployment failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()

