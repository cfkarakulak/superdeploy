"""
Project initialization - interactive wizard with secrets management
"""

import secrets
import click
from rich.prompt import Prompt
from cli.base import BaseCommand


class InitCommand(BaseCommand):
    """Initialize new project with secrets.yml."""

    def __init__(self, project_name: str, verbose: bool = False):
        super().__init__(verbose=verbose)
        self.project_name = project_name

    def execute(self) -> None:
        """Execute init command."""
        self.show_header(
            title="Initialize Project",
            project=self.project_name,
            subtitle="Infrastructure + secrets setup",
        )

        project_dir = self.project_root / "projects" / self.project_name

        # Check if project exists
        if project_dir.exists():
            self.console.print(
                f"[yellow]Project exists: {self.project_name}. Overwrite? [y/n][/yellow] [dim](n)[/dim]: ",
                end="",
            )
            answer = input().strip().lower()
            if answer not in ["y", "yes"]:
                self.console.print("[dim]Cancelled[/dim]")
                return

        project_dir.mkdir(parents=True, exist_ok=True)

        # Cloud Provider
        self.console.print("\n[white]Cloud Provider[/white]")
        gcp_project = Prompt.ask("GCP Project ID", default="my-gcp-project")
        gcp_region = Prompt.ask("GCP Region", default="us-central1")

        # GitHub
        self.console.print("\n[white]GitHub[/white]")
        github_org = Prompt.ask("GitHub Organization", default=f"{self.project_name}io")

        # Apps
        self.console.print("\n[white]Applications[/white]")
        self.console.print("[dim]Enter app names (comma-separated)[/dim]")
        apps_input = Prompt.ask("Apps")
        app_names = [a.strip() for a in apps_input.split(",")]

        # App paths
        apps = {}
        for app_name in app_names:
            default_path = f"/path/to/{app_name}"
            app_path = Prompt.ask(f"  Path for {app_name}", default=default_path)
            default_port = "8000"
            app_port = Prompt.ask(f"  Port for {app_name}", default=default_port)

            apps[app_name] = {
                "path": app_path,
                "vm": "app",
                "port": int(app_port),
            }

        # Generate config.yml using stub generator
        project_yml = project_dir / "config.yml"

        # Import generator from stubs using importlib
        import importlib.util

        cli_root = Path(__file__).resolve().parents[1]
        stub_file = cli_root / "stubs" / "configs" / "project_config_generator.py"
        spec = importlib.util.spec_from_file_location(
            "project_config_generator", stub_file
        )
        module = importlib.util.module_from_spec(spec)  # type: ignore
        spec.loader.exec_module(module)  # type: ignore

        config_content = module.generate_project_config(
            project_name=self.project_name,
            gcp_project=gcp_project,
            gcp_region=gcp_region,
            github_org=github_org,
            apps=apps,
        )

        with open(project_yml, "w") as f:
            f.write(config_content)

        self.console.print(
            f"\n[dim]✓ Created: {project_yml.relative_to(self.project_root)}[/dim]"
        )

        # Generate secrets.yml with template
        self.console.print("\n[dim]Generating secrets...[/dim]")

        postgres_password = secrets.token_urlsafe(32)
        rabbitmq_password = secrets.token_urlsafe(32)

        # Import generator from stubs using importlib
        cli_root = Path(__file__).resolve().parents[1]
        stub_file = cli_root / "stubs" / "configs" / "project_secrets_generator.py"
        spec = importlib.util.spec_from_file_location(
            "project_secrets_generator", stub_file
        )
        module = importlib.util.module_from_spec(spec)  # type: ignore
        spec.loader.exec_module(module)  # type: ignore

        secrets_content = module.generate_project_secrets(
            project_name=self.project_name,
            app_names=app_names,
            postgres_password=postgres_password,
            rabbitmq_password=rabbitmq_password,
        )

        # Generate secrets.yml with beautiful formatting
        secrets_yml = project_dir / "secrets.yml"

        with open(secrets_yml, "w") as f:
            f.write(secrets_content)

        # Set restrictive permissions
        secrets_yml.chmod(0o600)

        self.console.print(
            f"[dim]✓ Created: {secrets_yml.relative_to(self.project_root)}[/dim]"
        )
        self.console.print(
            "[dim]  Generated secure passwords for PostgreSQL and RabbitMQ[/dim]"
        )
        self.console.print(
            "[yellow]  ⚠ Fill in Docker, GitHub, and SMTP credentials before deploying![/yellow]"
        )

        # Summary
        self.console.print("\n[white]Next steps:[/white]")
        self.console.print(
            "  [dim]1. Edit secrets: nano projects/{}/secrets.yml[/dim]".format(
                self.project_name
            )
        )
        self.console.print(
            "     [yellow]→ Add DOCKER_ORG, DOCKER_USERNAME, DOCKER_TOKEN (required)[/yellow]"
        )
        self.console.print(
            "     [yellow]→ Add GITHUB_TOKEN (required - with admin:org scope)[/yellow]"
        )
        self.console.print(
            "     [yellow]→ Add SMTP credentials (optional, for email notifications)[/yellow]"
        )
        self.console.print(
            "  [dim]2. Generate deployment files: superdeploy {}:generate[/dim]".format(
                self.project_name
            )
        )
        self.console.print(
            "  [dim]3. Deploy infrastructure: superdeploy {}:up[/dim]\n".format(
                self.project_name
            )
        )


@click.command(name="init")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
def init(project, verbose):
    """
    Initialize new project with secrets.yml

    Creates:
    - config.yml (infrastructure config)
    - secrets.yml (secret management)

    No more .env files!
    """
    cmd = InitCommand(project, verbose=verbose)
    cmd.run()
