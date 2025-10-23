#!/usr/bin/env python3
"""Parse project config.yml and extract port configuration using regex (no external deps)."""

import sys
import re

if len(sys.argv) != 3:
    print("8080 8080")
    sys.exit(0)

config_file = sys.argv[1]
service = sys.argv[2]

try:
    with open(config_file, "r") as f:
        content = f.read()

    # Parse YAML using regex (no pyyaml dependency needed)
    # Pattern: ports:\n  service:\n    external: 8000\n    internal: 8000
    pattern = rf"{service}:\s*\n\s+external:\s*(\d+)\s*\n\s+internal:\s*(\d+)"
    match = re.search(pattern, content)

    if match:
        external = match.group(1)
        internal = match.group(2)
        print(f"{external} {internal}")
    else:
        print("8080 8080")
except Exception:
    print("8080 8080")
    sys.exit(0)
