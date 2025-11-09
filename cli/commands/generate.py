"""
Generate deployment files - GitHub Actions workflows with self-hosted runners
"""

import click
from pathlib import Path
from jinja2 import Template
from cli.base import ProjectCommand


def _detect_app_type(app_path: Path) -> str:
    """Detect app type from files"""

    # Next.js
    if (app_path / "next.config.js").exists() or (app_path / "next.config.ts").exists():
        return "nextjs"

    # Python/Cara
    if (app_path / "requirements.txt").exists():
        requirements = (app_path / "requirements.txt").read_text()
        if "cara" in requirements.lower():
            return "python"  # Cara framework
        return "python"

    # Default
    return "python"


def _load_github_workflow_template(app_type: str) -> str:
    """Load GitHub workflow template from stub files"""
    # Get project root and use stubs directory
    project_root = Path(__file__).parent.parent.parent
    stub_dir = project_root / "stubs" / "workflows"

    if app_type == "nextjs":
        stub_file = stub_dir / "github_workflow_nextjs.yml.j2"
    else:
        # Default: Python/Cara
        stub_file = stub_dir / "github_workflow_python.yml.j2"

    if not stub_file.exists():
        raise FileNotFoundError(f"Template stub not found: {stub_file}")

    return stub_file.read_text(encoding="utf-8")


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

        from cli.secret_manager import SecretManager
        from cli.marker_manager import MarkerManager

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

            # 1. Detect app type
            app_type = _detect_app_type(app_path)
            self.console.print(f"  Type: {app_type}")

            # 2. Create .superdeploy marker
            vm_role = app_config.get("vm", "app")
            marker = MarkerManager.create_marker(
                app_path, self.project_name, app_name, vm_role
            )
            self.console.print(f"  [green]✓[/green] {marker.name}")

            # 3. Get app secrets (merged)
            app_secrets = secret_mgr.get_app_secrets(app_name)
            secret_count = len(app_secrets)
            self.console.print(f"  Secrets: {secret_count}")

            # 4. Generate GitHub workflow
            secret_var_line = f"              SECRET_VALUE='${{{{ secrets.{app_name.upper()}_ENV_JSON }}}}'"

            github_workflow_template = _load_github_workflow_template(app_type)
            github_workflow = Template(github_workflow_template).render(
                project=self.project_name,
                app=app_name,
                vm_role=vm_role,
                secret_var_line=secret_var_line,
            )
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
        self.console.print("   [dim]git add .superdeploy .github/[/dim]")
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
