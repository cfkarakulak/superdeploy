"""CLI command executor for dashboard."""

import subprocess
import asyncio
from pathlib import Path
from typing import AsyncIterator, Dict
import json


class CLIExecutor:
    """Execute SuperDeploy CLI commands."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.venv_python = project_root / "venv" / "bin" / "python"
        self.cli_path = project_root / "cli" / "main.py"

    async def execute_command(
        self, command: str, stream: bool = False
    ) -> AsyncIterator[str]:
        """
        Execute a CLI command and yield output lines.

        Args:
            command: The CLI command (e.g., "cheapa:init", "cheapa:up")
            stream: Whether to stream output line by line
        """
        # Build the command
        cmd = [str(self.venv_python), str(self.cli_path)] + command.split()

        # Set environment variables
        env = {
            **subprocess.os.environ,
            "FORCE_COLOR": "1",
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
        }

        # Remove NO_COLOR if present
        env.pop("NO_COLOR", None)

        try:
            # Run command with streaming output
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(self.project_root),
                env=env,
            )

            # Stream output line by line
            while True:
                line = await process.stdout.readline()
                if not line:
                    break

                line_text = line.decode("utf-8", errors="replace")

                if stream:
                    # Yield each line as it comes
                    yield (
                        json.dumps({"type": "output", "data": line_text.rstrip("\n")})
                        + "\n"
                    )

            # Wait for process to complete
            await process.wait()

            # Send exit code
            exit_code = process.returncode
            yield json.dumps({"type": "exit", "code": exit_code}) + "\n"

        except Exception as e:
            yield json.dumps({"type": "error", "message": str(e)}) + "\n"

    async def init_project(
        self,
        project_name: str,
        gcp_project: str,
        gcp_region: str,
        github_org: str,
        apps: Dict[str, Dict],
        addons: Dict[str, Dict],
        secrets: Dict[str, str] = {},
    ) -> AsyncIterator[str]:
        """
        Initialize a new project using CLI.

        This creates config.yml and secrets.yml files.
        """
        # For now, we'll execute the init command non-interactively
        # by preparing the config files directly
        from cli.commands.init import ProjectInitializer, ProjectSetupConfig
        import yaml

        try:
            yield (
                json.dumps({"type": "output", "data": "🚀 Initializing project..."})
                + "\n"
            )

            project_dir = self.project_root / "projects" / project_name
            project_dir.mkdir(parents=True, exist_ok=True)

            # Create setup config
            setup_config = ProjectSetupConfig(
                project_name=project_name,
                gcp_project=gcp_project,
                gcp_region=gcp_region,
                github_org=github_org,
                apps=apps,
                addons=addons,
            )

            # Initialize project files
            from rich.console import Console

            console = Console()
            initializer = ProjectInitializer(self.project_root, console)

            # Create config.yml
            yield (
                json.dumps({"type": "output", "data": "📝 Creating config.yml..."})
                + "\n"
            )
            initializer.create_config_file(project_dir, setup_config)
            yield json.dumps({"type": "output", "data": "✓ Created config.yml"}) + "\n"

            # Create secrets.yml
            yield (
                json.dumps({"type": "output", "data": "🔐 Generating secrets..."})
                + "\n"
            )
            app_names = list(apps.keys())
            secrets_file = initializer.create_secrets_file(
                project_dir, project_name, app_names, addons
            )

            # Update secrets.yml with user-provided secrets
            if secrets:
                yield (
                    json.dumps(
                        {
                            "type": "output",
                            "data": "🔑 Updating secrets with user credentials...",
                        }
                    )
                    + "\n"
                )

                # Read existing secrets.yml
                with open(secrets_file, "r") as f:
                    secrets_data = yaml.safe_load(f)

                # Update shared secrets
                if "secrets" not in secrets_data:
                    secrets_data["secrets"] = {}
                if "shared" not in secrets_data["secrets"]:
                    secrets_data["secrets"]["shared"] = {}

                shared = secrets_data["secrets"]["shared"]

                # Docker credentials
                if secrets.get("docker_org"):
                    shared["DOCKER_ORG"] = secrets["docker_org"]
                if secrets.get("docker_username"):
                    shared["DOCKER_USERNAME"] = secrets["docker_username"]
                if secrets.get("docker_token"):
                    shared["DOCKER_TOKEN"] = secrets["docker_token"]

                # GitHub token
                if secrets.get("github_token"):
                    shared["REPOSITORY_TOKEN"] = secrets["github_token"]

                # SMTP credentials (optional)
                if secrets.get("smtp_host"):
                    shared["SMTP_HOST"] = secrets["smtp_host"]
                if secrets.get("smtp_port"):
                    shared["SMTP_PORT"] = secrets["smtp_port"]
                if secrets.get("smtp_user"):
                    shared["SMTP_USER"] = secrets["smtp_user"]
                if secrets.get("smtp_password"):
                    shared["SMTP_PASSWORD"] = secrets["smtp_password"]

                # Write updated secrets back
                with open(secrets_file, "w") as f:
                    yaml.dump(
                        secrets_data, f, default_flow_style=False, sort_keys=False
                    )

                yield (
                    json.dumps({"type": "output", "data": "✓ User credentials added"})
                    + "\n"
                )

            yield json.dumps({"type": "output", "data": "✓ Created secrets.yml"}) + "\n"

            addon_count = (
                sum(len(instances) for instances in addons.values()) if addons else 0
            )
            if addon_count > 0:
                yield (
                    json.dumps(
                        {
                            "type": "output",
                            "data": f"✓ Generated {addon_count} addon credentials",
                        }
                    )
                    + "\n"
                )

            yield (
                json.dumps(
                    {"type": "output", "data": "✅ Project initialized successfully!"}
                )
                + "\n"
            )
            yield json.dumps({"type": "exit", "code": 0}) + "\n"

        except Exception as e:
            yield json.dumps({"type": "error", "message": str(e)}) + "\n"
            yield json.dumps({"type": "exit", "code": 1}) + "\n"

    async def generate_deployment_files(self, project_name: str) -> AsyncIterator[str]:
        """Generate deployment files (GitHub Actions workflows)."""
        command = f"{project_name}:generate"
        async for line in self.execute_command(command, stream=True):
            yield line

    async def deploy_project(self, project_name: str) -> AsyncIterator[str]:
        """Deploy project infrastructure."""
        command = f"{project_name}:up"
        async for line in self.execute_command(command, stream=True):
            yield line

    async def sync_secrets(self, project_name: str) -> AsyncIterator[str]:
        """Sync secrets to GitHub."""
        command = f"{project_name}:sync"
        async for line in self.execute_command(command, stream=True):
            yield line

    async def destroy_project(self, project_name: str) -> AsyncIterator[str]:
        """Destroy project infrastructure."""
        command = f"{project_name}:down"
        async for line in self.execute_command(command, stream=True):
            yield line

    async def get_project_status(self, project_name: str) -> AsyncIterator[str]:
        """Get project status."""
        command = f"{project_name}:ps"
        async for line in self.execute_command(command, stream=True):
            yield line

    def get_available_projects(self) -> list:
        """Get list of available projects from filesystem."""
        projects_dir = self.project_root / "projects"
        if not projects_dir.exists():
            return []

        projects = []
        for project_dir in projects_dir.iterdir():
            if project_dir.is_dir() and not project_dir.name.startswith("."):
                config_file = project_dir / "config.yml"
                if config_file.exists():
                    projects.append(
                        {
                            "name": project_dir.name,
                            "path": str(project_dir),
                            "has_secrets": (project_dir / "secrets.yml").exists(),
                        }
                    )

        return projects
