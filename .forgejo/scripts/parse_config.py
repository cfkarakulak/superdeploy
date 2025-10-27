#!/usr/bin/env python3
"""
Parse project.yml configuration and extract service-specific information.
Usage: python parse_config.py <config_file> <service_name>

Note: Uses simple parsing without PyYAML dependency for faster execution
in CI/CD environments.
"""

import sys
import os


def simple_yaml_parse(file_path: str, service_name: str):
    """
    Simple YAML parser for extracting service port from apps section.
    Only parses the specific structure needed, avoiding external dependencies.
    """
    if not os.path.exists(file_path):
        print(f"ERROR: Configuration file not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    with open(file_path, "r") as f:
        lines = f.readlines()

    # State machine for parsing
    in_apps_section = False
    in_target_service = False
    current_indent = 0
    service_indent = 0
    port = None
    external_port = None
    internal_port = None

    for line in lines:
        # Skip comments and empty lines
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Calculate indentation
        indent = len(line) - len(line.lstrip())

        # Check for apps section
        if line.strip() == "apps:":
            in_apps_section = True
            current_indent = indent
            continue

        if in_apps_section:
            # Check if we've left the apps section (lower or same indent level)
            if indent <= current_indent and not line.startswith(" "):
                in_apps_section = False
                in_target_service = False
                continue

            # Check for target service
            if stripped.startswith(f"{service_name}:"):
                in_target_service = True
                service_indent = indent
                continue

            # Parse service properties
            if in_target_service:
                # Check if we've left the service section
                if indent <= service_indent:
                    in_target_service = False
                    continue

                # Extract port values
                if stripped.startswith("port:"):
                    port = int(stripped.split(":", 1)[1].strip())
                elif stripped.startswith("external_port:"):
                    external_port = int(stripped.split(":", 1)[1].strip())
                elif stripped.startswith("internal_port:"):
                    internal_port = int(stripped.split(":", 1)[1].strip())

    # Check if service was found
    if port is None:
        print(
            f"ERROR: Port configuration not found for service '{service_name}' in {file_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Use defaults if external/internal ports not specified
    if external_port is None:
        external_port = port
    if internal_port is None:
        internal_port = port

    # Output in the format expected by workflow: "EXTERNAL_PORT INTERNAL_PORT"
    print(f"{external_port} {internal_port}")


def parse_config(config_file: str, service_name: str):
    """Parse project.yml and extract port configuration for a service."""
    try:
        simple_yaml_parse(config_file, service_name)
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
