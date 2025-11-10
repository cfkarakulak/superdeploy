#!/usr/bin/env python3
"""Fix Jinja2 template by wrapping GitHub Actions syntax with raw tags."""

import re


def fix_template(input_file, output_file):
    with open(input_file, "r") as f:
        lines = f.readlines()

    # Remove ALL existing raw tags but preserve line structure
    new_lines = []
    for line in lines:
        # Remove raw/endraw tags but keep the line
        line = re.sub(r"{%\s*raw\s*%}", "", line)
        line = re.sub(r"{%\s*endraw\s*%}", "", line)
        new_lines.append(line)

    content = "".join(new_lines)

    # Now wrap all ${{ ... }} with inline raw tags
    # Match ${{ ... }} but preserve surrounding text
    def wrap_github_var(match):
        """Wrap GitHub Actions variable with inline raw tags."""
        var = match.group(0)
        return f"{{% raw %}}{var}{{% endraw %}}"

    # Match ${{ with anything until }} (non-greedy)
    pattern = r"\$\{\{.*?\}\}"
    content = re.sub(pattern, wrap_github_var, content)

    with open(output_file, "w") as f:
        f.write(content)

    print("✅ Fixed! Wrapped all GitHub Actions variables.")
    print(f"   Processed {len(new_lines)} lines")


if __name__ == "__main__":
    fix_template(
        "cli/stubs/workflows/github_workflow_python.yml.j2",
        "cli/stubs/workflows/github_workflow_python.yml.j2",
    )
