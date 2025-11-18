"""
Project initialization - interactive wizard with database-backed secrets
"""

import click
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


class ProjectInitializer:
    """Handles project initialization workflow."""

    def __init__(self, project_root: Path, console):
        self.project_root = project_root
        self.console = console

    def create_config_in_database(self, setup_config: ProjectSetupConfig) -> bool:
        """Save project configuration to database (replaces config.yml)."""
        from cli.database import get_db_session
        from sqlalchemy import Table, Column, Integer, String, JSON, DateTime, MetaData
        from datetime import datetime

        # Build VMs configuration (default setup)
        vms_config = {
            "core": {
                "count": 1,
                "machine_type": "e2-medium",
                "disk_size": 20,
                "services": [],
            },
            "app": {
                "count": 1,
                "machine_type": "e2-medium",
                "disk_size": 30,
                "services": [],
            },
        }

        # Determine GCP zone from region
        gcp_zone = (
            f"{setup_config.gcp_region}-a"
            if setup_config.gcp_region
            else "us-central1-a"
        )

        # Build apps configuration
        apps_config = {}
        for app_name, app_data in setup_config.apps.items():
            apps_config[app_name] = {
                "path": app_data.get("path"),
                "vm": app_data.get("vm", "app"),
                "port": app_data.get("port"),
            }

        # Build addons configuration
        addons_config = {}
        for category, instances in setup_config.addons.items():
            addons_config[category] = {}
            for instance_name, instance_config in instances.items():
                addons_config[category][instance_name] = instance_config

        db = get_db_session()
        try:
            # Use raw SQL to insert project (avoid importing full ORM model)
            metadata = MetaData()
            projects_table = Table(
                "projects",
                metadata,
                Column("id", Integer, primary_key=True),
                Column("name", String(100)),
                Column("description", String(500)),
                Column("domain", String(200)),
                Column("ssl_email", String(200)),
                Column("github_org", String(100)),
                Column("gcp_project", String(100)),
                Column("gcp_region", String(50)),
                Column("gcp_zone", String(50)),
                Column("ssh_key_path", String(255)),
                Column("ssh_public_key_path", String(255)),
                Column("ssh_user", String(50)),
                Column("docker_registry", String(200)),
                Column("docker_organization", String(100)),
                Column("vpc_subnet", String(50)),
                Column("docker_subnet", String(50)),
                Column("vms", JSON),
                Column("apps_config", JSON),
                Column("addons_config", JSON),
                Column("created_at", DateTime),
                Column("updated_at", DateTime),
            )

            # Check if project already exists
            result = db.execute(
                projects_table.select().where(
                    projects_table.c.name == setup_config.project_name
                )
            )
            existing = result.fetchone()

            if existing:
                # Update existing project
                db.execute(
                    projects_table.update()
                    .where(projects_table.c.name == setup_config.project_name)
                    .values(
                        description=f"{setup_config.project_name} project",
                        github_org=setup_config.github_org,
                        gcp_project=setup_config.gcp_project,
                        gcp_region=setup_config.gcp_region,
                        gcp_zone=gcp_zone,
                        ssh_key_path="~/.ssh/superdeploy_deploy",
                        ssh_public_key_path="~/.ssh/superdeploy_deploy.pub",
                        ssh_user="superdeploy",
                        docker_registry="docker.io",
                        vpc_subnet="10.1.0.0/16",
                        docker_subnet="172.30.0.0/24",
                        vms=vms_config,
                        apps_config=apps_config,
                        addons_config=addons_config,
                        updated_at=datetime.utcnow(),
                    )
                )
            else:
                # Insert new project
                db.execute(
                    projects_table.insert().values(
                        name=setup_config.project_name,
                        description=f"{setup_config.project_name} project",
                        github_org=setup_config.github_org,
                        gcp_project=setup_config.gcp_project,
                        gcp_region=setup_config.gcp_region,
                        gcp_zone=gcp_zone,
                        ssh_key_path="~/.ssh/superdeploy_deploy",
                        ssh_public_key_path="~/.ssh/superdeploy_deploy.pub",
                        ssh_user="superdeploy",
                        docker_registry="docker.io",
                        vpc_subnet="10.1.0.0/16",
                        docker_subnet="172.30.0.0/24",
                        vms=vms_config,
                        apps_config=apps_config,
                        addons_config=addons_config,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                )

            db.commit()
            return True

        except Exception as e:
            db.rollback()
            raise Exception(f"Failed to save config to database: {e}")
        finally:
            db.close()

    def create_secrets_in_database(
        self, project_name: str, app_names: List[str], addons: dict
    ) -> bool:
        """Generate and save secrets to database (no YAML - direct DB write)."""
        from cli.database import get_db_session, Secret
        import secrets as python_secrets
        import string

        def generate_password(length=32):
            """Generate a secure random password."""
            alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
            return "".join(python_secrets.choice(alphabet) for _ in range(length))

        db = get_db_session()
        try:
            # 1. Create shared secrets (placeholders - user must fill in)
            shared_secrets = {
                "DOCKER_ORG": "CHANGE_ME",
                "DOCKER_USERNAME": "CHANGE_ME",
                "DOCKER_TOKEN": "CHANGE_ME",
                "REPOSITORY_TOKEN": "CHANGE_ME",
            }

            for key, value in shared_secrets.items():
                secret = Secret(
                    project_name=project_name,
                    app_name=None,
                    key=key,
                    value=value,
                    environment="production",
                    source="shared",
                    editable=True,
                )
                db.add(secret)

            # 2. Generate addon secrets based on configuration
            if addons and "databases" in addons:
                for instance_name, config in addons["databases"].items():
                    addon_type = config.get("type")
                    addon_key = f"{addon_type}.{instance_name}"

                    if addon_type == "postgres":
                        addon_secrets = {
                            f"{addon_key}.PORT": "5432",
                            f"{addon_key}.USER": f"{project_name}_user",
                            f"{addon_key}.PASSWORD": generate_password(),
                            f"{addon_key}.DATABASE": f"{project_name}_db",
                        }
                    elif addon_type == "mysql":
                        addon_secrets = {
                            f"{addon_key}.PORT": "3306",
                            f"{addon_key}.USER": f"{project_name}_user",
                            f"{addon_key}.PASSWORD": generate_password(),
                            f"{addon_key}.DATABASE": f"{project_name}_db",
                        }
                    elif addon_type == "mongodb":
                        addon_secrets = {
                            f"{addon_key}.PORT": "27017",
                            f"{addon_key}.USER": f"{project_name}_user",
                            f"{addon_key}.PASSWORD": generate_password(),
                            f"{addon_key}.DATABASE": f"{project_name}_db",
                        }
                    else:
                        continue

                    for key, value in addon_secrets.items():
                        secret = Secret(
                            project_name=project_name,
                            app_name=None,
                            key=key,
                            value=value,
                            environment="production",
                            source="addon",
                            editable=False,
                        )
                        db.add(secret)

            if addons and "queues" in addons:
                for instance_name, config in addons["queues"].items():
                    addon_type = config.get("type")
                    addon_key = f"{addon_type}.{instance_name}"

                    if addon_type == "rabbitmq":
                        addon_secrets = {
                            f"{addon_key}.PORT": "5672",
                            f"{addon_key}.MANAGEMENT_PORT": "15672",
                            f"{addon_key}.USER": f"{project_name}_user",
                            f"{addon_key}.PASSWORD": generate_password(),
                        }

                        for key, value in addon_secrets.items():
                            secret = Secret(
                                project_name=project_name,
                                app_name=None,
                                key=key,
                                value=value,
                                environment="production",
                                source="addon",
                                editable=False,
                            )
                            db.add(secret)

            if addons and "caches" in addons:
                for instance_name, config in addons["caches"].items():
                    addon_type = config.get("type")
                    addon_key = f"{addon_type}.{instance_name}"

                    if addon_type == "redis":
                        addon_secrets = {
                            f"{addon_key}.PORT": "6379",
                            f"{addon_key}.PASSWORD": generate_password(),
                        }
                    elif addon_type == "memcached":
                        addon_secrets = {
                            f"{addon_key}.PORT": "11211",
                        }
                    else:
                        continue

                    for key, value in addon_secrets.items():
                        secret = Secret(
                            project_name=project_name,
                            app_name=None,
                            key=key,
                            value=value,
                            environment="production",
                            source="addon",
                            editable=False,
                        )
                        db.add(secret)

            # 3. App-specific secrets are empty by default
            # User can add them via: superdeploy project:config:set KEY=VALUE --app=appname

            db.commit()
            return True

        except Exception as e:
            db.rollback()
            raise Exception(f"Failed to save secrets to database: {e}")
        finally:
            db.close()


class InitCommand(BaseCommand):
    """Initialize new project with database secrets."""

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

        # Initialize project
        initializer = ProjectInitializer(self.project_root, self.console)

        # Create configuration in database
        self.console.print("\n[dim]Saving configuration to database...[/dim]")
        initializer.create_config_in_database(setup_config)
        self.console.print("[dim]✓ Project configuration saved to database[/dim]")

        # Create secrets in database
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
        # All instances named "primary" for consistency
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
                "primary": {
                    "type": "rabbitmq",
                    "version": "3.12-management-alpine",
                    "plan": "standard",
                    "vm": "core",
                }
            },
            "proxy": {
                "primary": {
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
    Initialize new project with database secrets

    Creates:
    - config.yml (infrastructure config)
    - Secrets in PostgreSQL database

    No more .env files!
    """
    cmd = InitCommand(project, verbose=verbose, json_output=json_output)
    cmd.run()
