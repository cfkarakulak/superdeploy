#!/usr/bin/env python3
"""Remove --project/-p parameter from all commands"""

import re
from pathlib import Path

cli_dir = Path("cli/commands")

# Find all Python files
for py_file in cli_dir.glob("*.py"):
    content = py_file.read_text()
    original = content

    # Pattern 1: @click.option("--project", "-p", ...)
    content = re.sub(
        r'@click\.option\(["\']--project["\'],\s*["\']' "-p[\"'],\s*[^\)]+\)\n",
        "",
        content,
    )

    # Pattern 2: @click.option("-p", "--project", ...)
    content = re.sub(
        r'@click\.option\(["\']' "-p[\"'],\s*[\"']--project[\"'],\s*[^\)]+\)\n",
        "",
        content,
    )

    # Add comment to function signature where project parameter exists
    # Find function definitions that have 'project' as first parameter
    def add_comment(match):
        func_def = match.group(0)
        if "project," in func_def or "project)" in func_def:
            # Add comment after project parameter
            func_def = func_def.replace(
                "project,", "project,  # Injected by NamespacedGroup"
            )
            func_def = func_def.replace(
                "project)", "project)  # Injected by NamespacedGroup"
            )
        return func_def

    content = re.sub(r"def\s+\w+\([^)]+\):", add_comment, content)

    if content != original:
        py_file.write_text(content)
        print(f"✅ Updated: {py_file}")
    else:
        print(f"⏭️  Skipped: {py_file}")

print("\n✨ Done!")
