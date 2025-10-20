#!/usr/bin/env python3
"""
Partial Pull Script - Pull only specified services
Usage: python partial_pull.py "api,dashboard" '{"api":"abc123","dashboard":"def456"}' "prod"
"""

import sys
import json
import subprocess
import os


def main():
    if len(sys.argv) < 3:
        print("Usage: partial_pull.py <services> <image_tags_json> <environment>")
        sys.exit(1)

    services_str = sys.argv[1]
    image_tags_json = sys.argv[2]
    environment = sys.argv[3] if len(sys.argv) > 3 else "prod"

    # Parse services
    services = [s.strip() for s in services_str.split(",")]

    # Parse image tags
    try:
        image_tags = json.loads(image_tags_json)
    except json.JSONDecodeError:
        print(f"❌ Invalid JSON: {image_tags_json}")
        sys.exit(1)

    print(f"🔍 Services to pull: {services}")
    print(f"📦 Image tags: {image_tags}")
    print(f"🌍 Environment: {environment}")

    # Export image tags as environment variables
    for service, tag in image_tags.items():
        env_var = f"{service.upper()}_IMAGE_TAG"
        os.environ[env_var] = tag
        print(f"  export {env_var}={tag}")

    # Determine compose files
    compose_files = ["-f", "docker-compose.core.yml", "-f", "docker-compose.apps.yml"]
    if environment == "staging":
        compose_files.extend(["-f", "docker-compose.apps.staging.yml"])

    # Pull specified services
    for service in services:
        print(f"\n📥 Pulling {service}...")
        cmd = ["docker", "compose"] + compose_files + ["pull", service]
        result = subprocess.run(cmd, cwd="/opt/superdeploy/compose")
        if result.returncode != 0:
            print(f"⚠️  Failed to pull {service}")

    print("\n✅ Pull complete!")


if __name__ == "__main__":
    main()
