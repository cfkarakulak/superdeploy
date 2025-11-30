"""Orchestrator initialization command."""

import click
from dataclasses import dataclass
from rich.prompt import Prompt
import inquirer

from cli.base import BaseCommand


@dataclass
class OrchestratorConfig:
    """Configuration for orchestrator setup."""

    gcp_project: str
    region: str
    zone: str
    ssl_email: str
    docker_subnet: str


class OrchestratorInitCommand(BaseCommand):
    """Initialize orchestrator configuration."""

    def __init__(self, verbose: bool = False, json_output: bool = False):
        super().__init__(verbose=verbose, json_output=json_output)

    def execute(self) -> None:
        """Execute init command."""
        self.show_header(
            title="Orchestrator Setup",
            subtitle="Global monitoring (Prometheus + Grafana)",
            project="orchestrator",
            show_logo=True,
        )

        # Initialize logger
        logger = self.init_logger("orchestrator", "init")

        # Check if orchestrator exists in database
        if logger:
            logger.step("Checking existing configuration")

        if not self._confirm_overwrite_db(logger):
            return

        if logger:
            logger.step("Collecting configuration")

        # Collect configuration
        config = self._collect_configuration()

        if logger:
            logger.step("Saving configuration to database")

        # Save orchestrator to database
        self._create_orchestrator_in_db(config, logger)

        if logger:
            logger.success("Orchestrator configuration saved to database")

        # Display next steps
        self._display_next_steps()

        if not self.verbose:
            self.console.print(f"\n[dim]Logs saved to:[/dim] {logger.log_path}\n")

    def _confirm_overwrite_db(self, logger) -> bool:
        """Confirm overwrite if orchestrator exists in database."""
        from cli.database import get_db_session, Project

        db = get_db_session()
        try:
            existing_project = (
                db.query(Project).filter(Project.name == "orchestrator").first()
            )
            if existing_project:
                if logger:
                    logger.warning("Orchestrator already exists in database")
                self.console.print(
                    "[yellow]Orchestrator exists in database. Overwrite? [y/n][/yellow] [dim](n)[/dim]: ",
                    end="",
                )
                answer = input().strip().lower()
                self.console.print()
                if answer not in ["y", "yes"]:
                    if logger:
                        logger.log("User cancelled initialization")
                    self.console.print("[dim]Cancelled[/dim]")
                    return False
            else:
                if logger:
                    logger.log("No existing orchestrator found in database")
            return True
        finally:
            db.close()

    def _collect_configuration(self) -> OrchestratorConfig:
        """Collect orchestrator configuration from user."""
        from cli.commands.gcp import select_gcp_project, get_gcp_regions

        # GCP Project
        try:
            gcp_project = select_gcp_project(self.console)
        except RuntimeError as e:
            self.console.print(f"\n[red]✗ {str(e)}[/red]")
            raise click.Abort()

        # Region selection with inquirer
        self.console.print()
        regions = get_gcp_regions()[:8]  # Top 8 regions
        region_choices = [
            ("None", None),
        ] + [(r, r) for r in regions]

        questions = [
            inquirer.List(
                "region",
                message="GCP Region",
                choices=[r[0] for r in region_choices if r[0] != "None"] or regions,
                default=regions[0] if regions else "us-central1",
            )
        ]
        answers = inquirer.prompt(questions, raise_keyboard_interrupt=True)
        region = answers["region"] if answers else "us-central1"

        # Zone selection with inquirer
        self.console.print()
        zones = [f"{region}-a", f"{region}-b", f"{region}-c", f"{region}-f"]
        questions = [
            inquirer.List(
                "zone",
                message="GCP Zone",
                choices=zones,
                default=zones[0],
            )
        ]
        answers = inquirer.prompt(questions, raise_keyboard_interrupt=True)
        zone = answers["zone"] if answers else f"{region}-a"

        # SSL Email
        self.console.print()
        ssl_email = Prompt.ask("SSL Email", default="cradexco@gmail.com")

        # Allocate Docker subnet
        docker_subnet = self._allocate_docker_subnet()

        return OrchestratorConfig(
            gcp_project=gcp_project,
            region=region,
            zone=zone,
            ssl_email=ssl_email,
            docker_subnet=docker_subnet,
        )

    def _allocate_docker_subnet(self) -> str:
        """Allocate Docker subnet for orchestrator."""
        self.console.print()
        self.console.print("[dim]Allocating network subnet...[/dim]")

        from cli.subnet_allocator import SubnetAllocator

        allocator = SubnetAllocator()

        if "orchestrator" not in allocator.docker_allocations:
            docker_subnet = SubnetAllocator.ORCHESTRATOR_DOCKER_SUBNET
            allocator.docker_allocations["orchestrator"] = docker_subnet
            allocator.allocations["docker_subnets"] = allocator.docker_allocations
            allocator._save_allocations()
        else:
            docker_subnet = allocator.docker_allocations["orchestrator"]

        self.console.print(f"[dim]✓ Subnet allocated: {docker_subnet}[/dim]")
        return docker_subnet

    def _create_orchestrator_in_db(self, config: OrchestratorConfig, logger) -> None:
        """Create orchestrator project and addons in database."""
        from cli.database import get_db_session, Project, Addon, VM, Secret
        from datetime import datetime

        db = get_db_session()
        try:
            # Check if orchestrator exists
            db_project = (
                db.query(Project).filter(Project.name == "orchestrator").first()
            )

            if db_project:
                # Update existing orchestrator
                if logger:
                    logger.log("Updating existing orchestrator in database...")

                db_project.gcp_project = config.gcp_project
                db_project.gcp_region = config.region
                db_project.gcp_zone = config.zone
                db_project.ssl_email = config.ssl_email
                db_project.docker_subnet = config.docker_subnet
                db_project.updated_at = datetime.utcnow()

                # Delete old VMs, addons, and secrets
                db.query(VM).filter(VM.project_id == db_project.id).delete()
                db.query(Addon).filter(Addon.project_id == db_project.id).delete()
                db.query(Secret).filter(Secret.project_id == db_project.id).delete()
            else:
                # Create new orchestrator project
                if logger:
                    logger.log("Creating orchestrator in database...")

                db_project = Project(
                    name="orchestrator",
                    description="Global monitoring infrastructure (Prometheus + Grafana)",
                    project_type="orchestrator",  # Special type for infrastructure
                    gcp_project=config.gcp_project,
                    gcp_region=config.region,
                    gcp_zone=config.zone,
                    ssl_email=config.ssl_email,
                    ssh_key_path="~/.ssh/superdeploy_deploy",
                    ssh_public_key_path="~/.ssh/superdeploy_deploy.pub",
                    ssh_user="superdeploy",
                    docker_subnet=config.docker_subnet,
                    vpc_subnet="10.200.0.0/16",  # Orchestrator VPC
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                db.add(db_project)
                db.flush()  # Get project ID

            # Create VM record (orchestrator main VM)
            vm = VM(
                project_id=db_project.id,
                role="main",
                count=1,
                machine_type="e2-medium",
                disk_size=50,
                created_at=datetime.utcnow(),
            )
            db.add(vm)

            # Create monitoring addon
            # Note: type must match the addon folder name (addons/monitoring/)
            addon = Addon(
                project_id=db_project.id,
                instance_name="main",
                category="monitoring",
                type="monitoring",  # Must match folder name in addons/
                version="latest",
                vm="main",
                plan="standard",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(addon)

            db.commit()

            # Generate and save secrets to database
            self._generate_secrets_to_db(db, db_project.id, logger)

            # Log activity
            from cli.database import ActivityLog

            activity = ActivityLog(
                project_name="orchestrator",
                action="orchestrator:init",
                actor="cli",
                details={
                    "gcp_project": config.gcp_project,
                    "region": config.region,
                    "zone": config.zone,
                },
                created_at=datetime.utcnow(),
            )
            db.add(activity)
            db.commit()

            if logger:
                logger.log(
                    f"✓ Orchestrator saved to database (project_id: {db_project.id})"
                )

        except Exception as e:
            db.rollback()
            if logger:
                logger.log_error(f"Failed to create orchestrator in database: {e}")
            raise
        finally:
            db.close()

    def _generate_secrets_to_db(self, db, project_id: int, logger) -> None:
        """Generate orchestrator secrets and save to database only (no files)."""
        import secrets as py_secrets
        import string
        from cli.database import Secret
        from datetime import datetime

        def generate_password(length=48):
            alphabet = string.ascii_letters + string.digits + "-_"
            return "".join(py_secrets.choice(alphabet) for _ in range(length))

        grafana_password = generate_password()

        # Add new secrets
        secrets_data = [
            {
                "key": "GRAFANA_ADMIN_PASSWORD",
                "value": grafana_password,
                "editable": False,
            },
            {
                "key": "GRAFANA_ADMIN_USER",
                "value": "admin",
                "editable": True,
            },
            {
                "key": "SMTP_PASSWORD",
                "value": "",
                "editable": True,
            },
        ]

        for secret_data in secrets_data:
            secret = Secret(
                project_id=project_id,
                app_id=None,  # Orchestrator-level secret
                key=secret_data["key"],
                value=secret_data["value"],
                environment="production",
                source="generated",
                editable=secret_data["editable"],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(secret)

        db.commit()

        if logger:
            logger.log(
                f"✓ Secrets generated and saved to database ({len(secrets_data)} secrets)"
            )

    def _display_next_steps(self) -> None:
        """Display next steps after initialization."""
        self.console.print()
        self.console.print("[dim]Next step:[/dim]")
        self.console.print("  superdeploy orchestrator:up")
        self.console.print()


@click.command(name="orchestrator:init")
def orchestrator_init():
    """Initialize orchestrator configuration"""
    cmd = OrchestratorInitCommand()
    cmd.run()
