#!/usr/bin/env python3
"""Parse project config.yml and extract port configuration."""

import yaml
import sys

if len(sys.argv) != 3:
    print("8080 8080")
    sys.exit(0)

config_file = sys.argv[1]
service = sys.argv[2]

try:
    with open(config_file, "r") as f:
        config = yaml.safe_load(f)

    ports = config.get("ports", {}).get(service, {})
    external = ports.get("external", 8080)
    internal = ports.get("internal", 8080)

    print(f"{external} {internal}")
except Exception:
    print("8080 8080")
    sys.exit(0)
