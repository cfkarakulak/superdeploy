"""
Project initialization - interactive wizard with database-backed secrets
"""

import click
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List
from rich.prompt import Prompt
import inquirer

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
        """Save project configuration to database (normalized)."""
        from cli.database import get_db_session, Project, App, Addon, VM
        from datetime import datetime

        # Determine GCP zone from region
        gcp_zone = (
            f"{setup_config.gcp_region}-a"
            if setup_config.gcp_region
            else "us-central1-a"
        )

        db = get_db_session()
        try:
            # Check if project already exists
            existing = (
                db.query(Project)
                .filter(Project.name == setup_config.project_name)
                .first()
            )

            if existing:
                # Update existing project
                db_project = existing
                db_project.description = f"{setup_config.project_name} project"
                db_project.github_org = setup_config.github_org
                db_project.gcp_project = setup_config.gcp_project
                db_project.gcp_region = setup_config.gcp_region
                db_project.gcp_zone = gcp_zone
                db_project.ssh_key_path = "~/.ssh/superdeploy_deploy"
                db_project.ssh_public_key_path = "~/.ssh/superdeploy_deploy.pub"
                db_project.ssh_user = "superdeploy"
                db_project.docker_registry = "docker.io"
                db_project.vpc_subnet = "10.1.0.0/16"
                db_project.docker_subnet = "172.30.0.0/24"
                db_project.updated_at = datetime.utcnow()

                # Delete old VMs, Apps, Addons
                db.query(VM).filter(VM.project_id == db_project.id).delete()
                db.query(App).filter(App.project_id == db_project.id).delete()
                db.query(Addon).filter(Addon.project_id == db_project.id).delete()
            else:
                # Insert new project
                db_project = Project(
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
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                db.add(db_project)
                db.flush()  # Get project ID

            # Create VMs
            vms_data = [
                {
                    "role": "core",
                    "count": 1,
                    "machine_type": "e2-medium",
                    "disk_size": 20,
                },
                {
                    "role": "app",
                    "count": 1,
                    "machine_type": "e2-medium",
                    "disk_size": 30,
                },
            ]
            for vm_data in vms_data:
                vm = VM(project_id=db_project.id, **vm_data)
                db.add(vm)

            # Create Apps
            for app_name, app_data in setup_config.apps.items():
                app = App(
                    project_id=db_project.id,
                    name=app_name,
                    type=app_data.get("type"),
                    repo=app_data.get("repo"),
                    owner=app_data.get("owner"),
                    path=app_data.get("path"),
                    vm=app_data.get("vm", "app"),
                    port=app_data.get("port"),
                    external_port=app_data.get("external_port"),
                    services=app_data.get("services", ["web"]),
                )
                db.add(app)

            # Create Addons
            for category, instances in setup_config.addons.items():
                for instance_name, instance_config in instances.items():
                    addon = Addon(
                        project_id=db_project.id,
                        instance_name=instance_name,
                        category=category,
                        type=instance_config.get("type"),
                        version=instance_config.get("version", "latest"),
                        vm=instance_config.get("vm", "core"),
                        plan=instance_config.get("plan"),
                    )
                    db.add(addon)

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
            """Generate a secure random password.

            Note: Excludes $ character because docker-compose interprets it as variable.
            """
            alphabet = string.ascii_letters + string.digits + "!@#%^&*"
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

            # 3. App-specific secrets and aliases are NOT created here
            # Aliases are app-specific (each framework uses different ENV names)
            # User should define aliases via:
            #   - Dashboard UI
            #   - CLI: superdeploy project:alias:set DB_PASSWORD=postgres.primary.PASSWORD --app=api
            #   - Marker file: aliases section in superdeploy marker

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

        # Check if project exists in database
        if not self._confirm_overwrite():
            return

        project_dir.mkdir(parents=True, exist_ok=True)

        # Collect configuration via interactive prompts
        setup_config = self._collect_project_config()
        app_names = list(setup_config.apps.keys())
        addons = setup_config.addons  # Extract addons dict

        # Initialize project
        initializer = ProjectInitializer(self.project_root, self.console)

        # Create configuration in database
        self.console.print()
        initializer.create_config_in_database(setup_config)
        self.console.print("✓ Configuration saved")

        # Create secrets in database
        initializer.create_secrets_in_database(self.project_name, app_names, addons)
        addon_count = (
            sum(len(instances) for instances in addons.values()) if addons else 0
        )
        self.console.print(f"✓ Generated {addon_count} addon credentials")
        self.console.print("⚠ Set Docker/GitHub credentials before deploying")

        # Display next steps
        self._display_next_steps()

    def _confirm_overwrite(self) -> bool:
        """Confirm project overwrite if it exists in database."""
        from cli.database import get_db_session, Project
        from rich.prompt import Confirm

        db = get_db_session()
        try:
            existing = (
                db.query(Project).filter(Project.name == self.project_name).first()
            )

            if existing:
                overwrite = Confirm.ask(
                    f"Project exists in database: [cyan]{self.project_name}[/cyan]. Overwrite?",
                    default=False,
                )

                if not overwrite:
                    self.console.print("[dim]Cancelled[/dim]")
                    return False

            return True
        finally:
            db.close()

    def _collect_project_config(self) -> ProjectSetupConfig:
        """Collect project configuration via interactive prompts."""
        from cli.commands.gcp import select_gcp_project, get_gcp_regions

        # Cloud Provider
        try:
            gcp_project = select_gcp_project(self.console)
        except RuntimeError as e:
            self.console.print(f"\n[red]✗ {str(e)}[/red]")
            raise click.Abort()

        # Region selection (interactive)
        regions = get_gcp_regions()
        common_regions = regions[:8]

        self.console.print()
        questions = [
            inquirer.List(
                "region",
                message="GCP Region",
                choices=common_regions,
                default="us-central1",
                carousel=True,
            )
        ]
        answers = inquirer.prompt(questions, raise_keyboard_interrupt=True)
        gcp_region = answers["region"] if answers else "us-central1"

        # GitHub
        github_org = Prompt.ask(
            "[?] GitHub Organization", default=f"{self.project_name}io"
        )

        # Number of Apps (interactive)
        self.console.print()
        questions = [
            inquirer.List(
                "num_apps",
                message="Number of Apps",
                choices=["1", "2", "3", "4", "5"],
                default="1",
                carousel=True,
            )
        ]
        answers = inquirer.prompt(questions, raise_keyboard_interrupt=True)
        num_apps = int(answers["num_apps"]) if answers else 1

        apps = {}
        for i in range(num_apps):
            self.console.print()
            if num_apps > 1:
                self.console.print(f"[bold]App {i + 1}/{num_apps}[/bold]")

            app_name = Prompt.ask(
                "[?] Name", default="api" if i == 0 else f"app{i + 1}"
            )

            app_repo = Prompt.ask("[?] Repo", default=app_name)
            app_path = Prompt.ask("[?] Path", default=f"/{app_name}")

            # Port is optional (for background workers, leave empty)
            port_input = Prompt.ask(
                "[?] Port [dim](empty for bg worker)[/dim]",
                default="8000",
            )
            app_port = int(port_input) if port_input and port_input != "none" else None

            # Apps always go to "app" VM (not core)
            app_vm = "app"

            # External port only if internal port exists
            if app_port:
                app_external_port = 80 if i == 0 else (8080 + i)
            else:
                app_external_port = None

            # Services default to "web" if port exists, else empty
            services = ["web"] if app_port else []

            apps[app_name] = {
                "repo": app_repo,
                "owner": github_org,
                "path": app_path,
                "port": app_port,
                "external_port": app_external_port,
                "services": services,
                "vm": app_vm,
            }

        # Addons (interactive selection with arrow keys)
        self.console.print()
        self.console.print("[bold]Addons[/bold]")
        addons = {}

        # Database
        questions = [
            inquirer.List(
                "database",
                message="Database",
                choices=["None", "PostgreSQL", "MySQL", "MongoDB"],
                default="PostgreSQL",
                carousel=True,
            )
        ]
        answers = inquirer.prompt(questions, raise_keyboard_interrupt=True)
        db_choice = answers["database"] if answers else "PostgreSQL"

        db_map = {
            "PostgreSQL": "postgres",
            "MySQL": "mysql",
            "MongoDB": "mongodb",
            "None": "none",
        }
        db_type = db_map.get(db_choice, "postgres")

        if db_type != "none":
            addons["databases"] = {
                "primary": {
                    "type": db_type,
                    "version": "15-alpine"
                    if db_type == "postgres"
                    else "8-alpine"
                    if db_type == "mysql"
                    else "7",
                    "plan": "standard",
                    "vm": "core",
                }
            }

        # Cache
        questions = [
            inquirer.List(
                "cache",
                message="Cache",
                choices=["None", "Redis", "Memcached"],
                default="Redis",
                carousel=True,
            )
        ]
        answers = inquirer.prompt(questions, raise_keyboard_interrupt=True)
        cache_choice = answers["cache"] if answers else "Redis"

        cache_map = {"Redis": "redis", "Memcached": "memcached", "None": "none"}
        cache_type = cache_map.get(cache_choice, "redis")

        if cache_type != "none":
            addons["caches"] = {
                "primary": {
                    "type": cache_type,
                    "version": "7-alpine" if cache_type == "redis" else "1.6-alpine",
                    "plan": "standard",
                    "vm": "core",
                }
            }

        # Queue
        questions = [
            inquirer.List(
                "queue",
                message="Queue",
                choices=["None", "RabbitMQ"],
                default="RabbitMQ",
                carousel=True,
            )
        ]
        answers = inquirer.prompt(questions, raise_keyboard_interrupt=True)
        queue_choice = answers["queue"] if answers else "RabbitMQ"

        queue_map = {"RabbitMQ": "rabbitmq", "None": "none"}
        queue_type = queue_map.get(queue_choice, "rabbitmq")

        if queue_type != "none":
            addons["queues"] = {
                "primary": {
                    "type": queue_type,
                    "version": "3.12-management-alpine",
                    "plan": "standard",
                    "vm": "core",
                }
            }

        # Proxy (always Caddy)
        addons["proxy"] = {
            "primary": {
                "type": "caddy",
                "version": "2-alpine",
                "plan": "standard",
                "vm": "core",
            }
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
        self.console.print("\n[dim]Next steps:[/dim]")
        self.console.print(f"  [dim]superdeploy {self.project_name}:generate[/dim]")
        self.console.print(f"  [dim]superdeploy {self.project_name}:up[/dim]\n")


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
