"""
Project initialization - interactive wizard with secrets management
"""

import click
import importlib.util
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List
from rich.prompt import Prompt

from cli.base import BaseCommand


@dataclass
class ProjectSetupConfig:
    """Configuration for new project setup."""

    project_name: str
    gcp_project: str
    gcp_region: str
    github_org: str
    apps: Dict[str, Dict[str, any]]
    addons: Dict[str, Dict[str, Dict[str, any]]]  # category -> instance -> config


class StubModuleLoader:
    """Loads and executes stub generator modules."""

    CLI_ROOT = Path(__file__).resolve().parents[1]

    @classmethod
    def load_generator(cls, stub_name: str):
        """Load generator module from stubs directory."""
        stub_file = cls.CLI_ROOT / "stubs" / "configs" / f"{stub_name}.py"
        spec = importlib.util.spec_from_file_location(stub_name, stub_file)
        module = importlib.util.module_from_spec(spec)  # type: ignore
        spec.loader.exec_module(module)  # type: ignore
        return module


class ProjectInitializer:
    """Handles project initialization workflow."""

    def __init__(self, project_root: Path, console):
        self.project_root = project_root
        self.console = console

    def create_config_file(
        self, project_dir: Path, setup_config: ProjectSetupConfig
    ) -> Path:
        """Generate and save config.yml."""
        config_yml = project_dir / "config.yml"

        generator = StubModuleLoader.load_generator("project_config_generator")
        config_content = generator.generate_project_config(
            project_name=setup_config.project_name,
            gcp_project=setup_config.gcp_project,
            gcp_region=setup_config.gcp_region,
            github_org=setup_config.github_org,
            apps=setup_config.apps,
        )

        config_yml.write_text(config_content)
        return config_yml

    def create_secrets_in_database(
        self, project_name: str, app_names: List[str], addons: dict
    ) -> bool:
        """Generate and save secrets to database (replaces secrets.yml)."""
        from cli.database import get_db_session, Secret
        import yaml

        # Generate secrets content using generator
        generator = StubModuleLoader.load_generator("project_secrets_generator")
        secrets_content = generator.generate_project_secrets(
            project_name=project_name,
            app_names=app_names,
            addons=addons,
        )

        # Parse generated YAML to extract secrets
        secrets_data = yaml.safe_load(secrets_content)
        secrets_dict = secrets_data.get("secrets", {})

        db = get_db_session()
        try:
            # 1. Insert shared secrets
            shared_secrets = secrets_dict.get("shared", {})
            for key, value in shared_secrets.items():
                secret = Secret(
                    project_name=project_name,
                    app_name=None,  # NULL = shared
                    key=key,
                    value=str(value),
                    environment="production",
                    source="shared",
                    editable=True,
                )
                db.add(secret)

            # 2. Insert addon secrets
            addons_data = secrets_dict.get("addons", {})
            for addon_type, instances in addons_data.items():
                for instance_name, credentials in instances.items():
                    for key, value in credentials.items():
                        # Create dotted key: postgres.primary.HOST
                        full_key = f"{addon_type}.{instance_name}.{key}"
                        secret = Secret(
                            project_name=project_name,
                            app_name=None,  # Addons are shared
                            key=full_key,
                            value=str(value),
                            environment="production",
                            source="addon",
                            editable=False,
                        )
                        db.add(secret)

            # 3. Insert app-specific secrets
            apps_data = secrets_dict.get("apps", {})
            for app_name, app_secrets in apps_data.items():
                for key, value in app_secrets.items():
                    secret = Secret(
                        project_name=project_name,
                        app_name=app_name,
                        key=key,
                        value=str(value),
                        environment="production",
                        source="app",
                        editable=True,
                    )
                    db.add(secret)

            db.commit()
            return True

        except Exception as e:
            db.rollback()
            raise Exception(f"Failed to save secrets to database: {e}")
        finally:
            db.close()


class InitCommand(BaseCommand):
    """Initialize new project with secrets.yml."""

    def __init__(
        self, project_name: str, verbose: bool = False, json_output: bool = False
    ):
        super().__init__(verbose=verbose, json_output=json_output)
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
        if not self._confirm_overwrite(project_dir):
            return

        project_dir.mkdir(parents=True, exist_ok=True)

        # Collect configuration via interactive prompts
        setup_config = self._collect_project_config()
        app_names = list(setup_config.apps.keys())
        addons = setup_config.addons  # Extract addons dict

        # Initialize project files
        initializer = ProjectInitializer(self.project_root, self.console)

        # Create config.yml
        config_yml = initializer.create_config_file(project_dir, setup_config)
        self.console.print(
            f"\n[dim]✓ Created: {config_yml.relative_to(self.project_root)}[/dim]"
        )

        # Create secrets in database (replaces secrets.yml)
        self.console.print("\n[dim]Generating secrets...[/dim]")
        initializer.create_secrets_in_database(self.project_name, app_names, addons)
        self.console.print("[dim]✓ Secrets saved to database[/dim]")
        addon_count = (
            sum(len(instances) for instances in addons.values()) if addons else 0
        )
        if addon_count > 0:
            self.console.print(
                f"[dim]  Generated secure credentials for {addon_count} addon instance(s)[/dim]"
            )
        else:
            self.console.print(
                "[dim]  No addons configured - add them in config.yml if needed[/dim]"
            )
        self.console.print(
            "[yellow]  ⚠ Fill in Docker, GitHub, and SMTP credentials before deploying![/yellow]"
        )

        # Display next steps
        self._display_next_steps()

    def _confirm_overwrite(self, project_dir: Path) -> bool:
        """Confirm project overwrite if it exists."""
        if project_dir.exists():
            self.console.print(
                f"[yellow]Project exists: {self.project_name}. Overwrite? [y/n][/yellow] [dim](n)[/dim]: ",
                end="",
            )
            answer = input().strip().lower()
            if answer not in ["y", "yes"]:
                self.console.print("[dim]Cancelled[/dim]")
                return False
        return True

    def _collect_project_config(self) -> ProjectSetupConfig:
        """Collect project configuration via interactive prompts."""
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

        # Collect app details
        apps = {}
        for app_name in app_names:
            default_path = f"/path/to/{app_name}"
            app_path = Prompt.ask(f"  Path for {app_name}", default=default_path)
            default_port = "8000"
            app_port = Prompt.ask(f"  Port for {app_name}", default=default_port)

            # Note: 'type' field is optional and auto-detected during generate
            # User can manually add: type: python or type: nextjs
            apps[app_name] = {
                "path": app_path,
                "vm": "app",
                "port": int(app_port),
            }

        # Default addons (postgres + rabbitmq + caddy)
        addons = {
            "databases": {
                "primary": {
                    "type": "postgres",
                    "version": "15-alpine",
                    "plan": "standard",
                    "vm": "core",
                }
            },
            "queues": {
                "main": {
                    "type": "rabbitmq",
                    "version": "3.12-management-alpine",
                    "plan": "standard",
                    "vm": "core",
                }
            },
            "proxy": {
                "main": {
                    "type": "caddy",
                    "version": "2-alpine",
                    "plan": "standard",
                    "vm": "app",
                }
            },
        }

        return ProjectSetupConfig(
            project_name=self.project_name,
            gcp_project=gcp_project,
            gcp_region=gcp_region,
            github_org=github_org,
            apps=apps,
            addons=addons,
        )

    def _display_next_steps(self) -> None:
        """Display next steps after initialization."""
        self.console.print("\n[white]Next steps:[/white]")
        self.console.print(
            f"  [dim]1. Edit secrets: superdeploy {self.project_name}:config:set KEY=VALUE[/dim]"
        )
        self.console.print(
            "     [yellow]→ Add DOCKER_ORG, DOCKER_USERNAME, DOCKER_TOKEN (required)[/yellow]"
        )
        self.console.print(
            "     [yellow]→ Add REPOSITORY_TOKEN (required - with admin:org scope)[/yellow]"
        )
        self.console.print(
            "     [yellow]→ Add SMTP credentials (optional, for email notifications)[/yellow]"
        )
        self.console.print(
            f"  [dim]2. Generate deployment files: superdeploy {self.project_name}:generate[/dim]"
        )
        self.console.print(
            f"  [dim]3. Deploy infrastructure: superdeploy {self.project_name}:up[/dim]\n"
        )


@click.command(name="init")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def init(project, verbose, json_output):
    """
    Initialize new project with secrets.yml

    Creates:
    - config.yml (infrastructure config)
    - secrets.yml (secret management)

    No more .env files!
    """
    cmd = InitCommand(project, verbose=verbose, json_output=json_output)
    cmd.run()
