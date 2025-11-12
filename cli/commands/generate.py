"""
Generate deployment files - GitHub Actions workflows with self-hosted runners
"""

import click
from pathlib import Path
from dataclasses import dataclass
from jinja2 import Template

from cli.base import ProjectCommand
from cli.secret_manager import SecretManager
from cli.marker_manager import MarkerManager
from cli.core.app_type_registry import app_type_registry
from cli.exceptions import ConfigurationError


@dataclass
class WorkflowConfig:
    """Configuration for generating workflow files."""

    project: str
    app: str
    vm_role: str
    app_type: str
    secret_keys: list[str]  # List of secret keys for dynamic injection
    repo_org: str


class WorkflowGenerator:
    """Handles workflow template generation with pluggable app types."""

    CLI_ROOT = Path(__file__).parent.parent

    @classmethod
    def get_or_detect_app_type(cls, app_config: dict, app_path: Path) -> str:
        """
        Get app type from config or auto-detect it.

        Priority:
        1. Explicit 'type' field in config (recommended)
        2. Auto-detection from app path
        3. Default fallback to 'python'

        Args:
            app_config: App configuration dictionary
            app_path: Path to the application directory

        Returns:
            App type name (e.g., "python", "nextjs")

        Raises:
            ConfigurationError: If explicit type is invalid
        """
        # Priority 1: Explicit type in config
        if "type" in app_config:
            app_type = app_config["type"]
            try:
                # Validate it exists in registry
                app_type_registry.get(app_type)
                return app_type
            except ValueError as e:
                raise ConfigurationError(str(e))

        # Priority 2: Auto-detect from path
        detected_type = app_type_registry.detect(app_path)
        if detected_type != "unknown":
            return detected_type

        # Priority 3: Default fallback
        return "python"

    @classmethod
    def load_workflow_template(cls, app_type: str) -> str:
        """
        Load GitHub workflow template from registry.

        Args:
            app_type: The app type (e.g., "python", "nextjs")

        Returns:
            Template file contents

        Raises:
            ValueError: If app type is not supported
            FileNotFoundError: If template file doesn't exist
        """
        stub_dir = cls.CLI_ROOT / "stubs" / "workflows"

        # Get template name from registry
        type_config = app_type_registry.get(app_type)
        stub_file = stub_dir / type_config.workflow_template

        if not stub_file.exists():
            raise FileNotFoundError(f"Template stub not found: {stub_file}")

        return stub_file.read_text(encoding="utf-8")

    @classmethod
    def generate_workflow(cls, config: WorkflowConfig) -> str:
        """Generate GitHub workflow content from template."""
        template_content = cls.load_workflow_template(config.app_type)
        return Template(template_content).render(
            project=config.project,
            app=config.app,
            app_name=config.app,
            vm_role=config.vm_role,
            secret_keys=config.secret_keys,  # Pass as list
            repo_org=config.repo_org,
        )


class GenerateCommand(ProjectCommand):
    """Generate deployment files with GitHub Actions workflows."""

    def __init__(self, project_name: str, app: str = None, verbose: bool = False):
        super().__init__(project_name, verbose=verbose)
        self.app = app

    def execute(self) -> None:
        """Execute generate command."""
        self.show_header(
            title="Generate Deployment Files",
            project=self.project_name,
            subtitle="GitHub Actions workflows + Self-hosted runners",
        )

        project_root = self.project_root
        projects_dir = project_root / "projects"
        project_dir = projects_dir / self.project_name

        # Load config
        try:
            project_config = self.config_service.load_project_config(self.project_name)
            self.console.print(f"[dim]✓ Loaded config: {project_dir}/config.yml[/dim]")
        except FileNotFoundError as e:
            self.console.print(f"[red]❌ {e}[/red]")
            return
        except ValueError as e:
            self.console.print(f"[red]❌ Invalid configuration: {e}[/red]")
            return

        config = project_config.raw_config

        # Validate apps
        if not config.get("apps"):
            self.console.print("[red]❌ No apps defined in config![/red]")
            return

        # Initialize secret manager
        secret_mgr = SecretManager(self.project_root, self.project_name)

        # Check if secrets.yml exists
        if not secret_mgr.secrets_file.exists():
            self.console.print("\n[red]❌ No secrets.yml found![/red]")
            self.console.print(
                f"[yellow]Run first:[/yellow] superdeploy {self.project_name}:init"
            )
            self.console.print("[dim]Or create manually with structure:[/dim]")
            self.console.print("[dim]secrets:[/dim]")
            self.console.print("[dim]  shared: {}[/dim]")
            self.console.print("[dim]  api: {}[/dim]")
            return

        # Load secrets
        all_secrets = secret_mgr.load_secrets()
        self.console.print("\n[dim]✓ Loaded secrets from secrets.yml[/dim]")

        # Filter apps
        apps_to_generate = config["apps"]
        if self.app:
            if self.app not in apps_to_generate:
                self.console.print(f"[red]❌ App not found: {self.app}[/red]")
                return
            apps_to_generate = {self.app: apps_to_generate[self.app]}

        self.console.print(
            f"\n[bold cyan]📝 Generating for {len(apps_to_generate)} app(s)...[/bold cyan]\n"
        )

        # Get GitHub org
        github_org = config.get("github", {}).get(
            "organization", f"{self.project_name}io"
        )

        # Generate for each app
        for app_name, app_config in apps_to_generate.items():
            app_path = Path(app_config["path"]).expanduser().resolve()

            if not app_path.exists():
                self.console.print(
                    f"  [yellow]⚠[/yellow] {app_name}: Path not found: {app_path}"
                )
                continue

            self.console.print(f"[cyan]{app_name}:[/cyan]")

            # 1. Get or detect app type
            app_type = WorkflowGenerator.get_or_detect_app_type(app_config, app_path)
            type_source = "explicit" if "type" in app_config else "detected"
            self.console.print(f"  Type: {app_type} [dim]({type_source})[/dim]")

            # 2. Create superdeploy marker (multi-process mode)
            vm_role = app_config.get("vm", "app")

            # Get processes from config or create default
            processes = app_config.get("processes")
            if not processes:
                # Auto-create default process based on app type
                port = app_config.get("port")

                if app_type == "nextjs":
                    default_cmd = "npm start"
                    default_name = "web"
                elif app_type == "python":
                    if port:
                        # Web service
                        default_cmd = f"python craft serve --host 0.0.0.0 --port {port}"
                        default_name = "web"
                    else:
                        # Worker service (no --tries parameter, not supported by all frameworks)
                        default_cmd = "python craft queue:work"
                        default_name = "worker"
                else:
                    # Generic default
                    default_cmd = "npm start" if port else "python main.py"
                    default_name = "web" if port else "worker"

                process_def = {"command": default_cmd, "replicas": 1}
                if port:
                    process_def["port"] = port
                processes = {default_name: process_def}

                self.console.print(
                    f"  [dim]Using default process: {default_name} (replicas: 1)[/dim]"
                )
            else:
                # Ensure all processes have replicas field
                for proc_name, proc_config in processes.items():
                    if "replicas" not in proc_config:
                        proc_config["replicas"] = 1

            marker = MarkerManager.create_marker(
                app_path,
                self.project_name,
                app_name,
                vm_role,
                processes=processes,
            )

            # Show marker creation with process info
            proc_names = ", ".join(processes.keys())
            self.console.print(
                f"  [green]✓[/green] {marker.name} [dim]({proc_names})[/dim]"
            )

            # 3. Get app secrets (merged)
            app_secrets = secret_mgr.get_app_secrets(app_name)
            secret_count = len(app_secrets)
            self.console.print(f"  Secrets: {secret_count}")

            # 4. Generate GitHub workflow with dynamic secret injection
            # Send secret keys as list to avoid Jinja2 parsing issues
            secret_keys = sorted(app_secrets.keys())
            
            # Debug: Print first 3 keys
            if secret_keys:
                self.console.print(f"  [dim]Sample secrets (first 3): {', '.join(secret_keys[:3])}[/dim]")

            workflow_config = WorkflowConfig(
                project=self.project_name,
                app=app_name,
                vm_role=vm_role,
                app_type=app_type,
                secret_keys=secret_keys,  # Send as list instead of pre-rendered block
                repo_org=config.get("github", {}).get("organization", "GITHUB_ORG"),
            )

            github_workflow = WorkflowGenerator.generate_workflow(workflow_config)
            github_dir = app_path / ".github" / "workflows"
            github_dir.mkdir(parents=True, exist_ok=True)
            (github_dir / "deploy.yml").write_text(github_workflow)
            self.console.print("  [green]✓[/green] .github/workflows/deploy.yml")

            self.console.print()

        # Summary
        self.console.print("\n[green]✅ Generation complete![/green]")
        self.console.print("\n[bold]📝 Next steps:[/bold]")
        self.console.print("\n1. Setup GitHub runners on VMs:")
        self.console.print(f"   [red]superdeploy {self.project_name}:up[/red]")
        self.console.print("\n2. Commit to app repos:")
        self.console.print("   [dim]cd <app-repo>[/dim]")
        self.console.print("   [dim]git add superdeploy .github/[/dim]")
        self.console.print('   [dim]git commit -m "Add SuperDeploy config"[/dim]')
        self.console.print("   [dim]git push origin production[/dim]")
        self.console.print("\n3. GitHub Actions will automatically deploy!")


@click.command(name="generate")
@click.option("--app", help="Generate for specific app only")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
def generate(project, app, verbose):
    """
    Generate deployment files with GitHub Actions workflows

    Features:
    - Secret hierarchy (shared + app-specific)
    - GitHub self-hosted runners
    - .superdeploy marker files
    - Smart VM selection based on labels

    Example:
        superdeploy cheapa:generate
        superdeploy cheapa:generate --app api
    """
    cmd = GenerateCommand(project, app=app, verbose=verbose)
    cmd.run()
