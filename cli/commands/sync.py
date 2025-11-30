"""SuperDeploy CLI - Sync command

Syncs actual infrastructure state with database.
Includes export/import functionality for full project snapshots.
"""

import click
import json
from pathlib import Path
from datetime import datetime
from rich.table import Table
from cli.base import ProjectCommand


class SyncCommand(ProjectCommand):
    """Sync infrastructure state to database."""

    def __init__(
        self,
        project_name: str,
        verbose: bool = False,
        json_output: bool = False,
    ):
        super().__init__(project_name, verbose=verbose, json_output=json_output)
        self.synced_items = []

    def execute(self) -> None:
        """Execute sync command."""
        logger = self.init_logger(self.project_name, "sync")

        if not self.json_output:
            self.show_header(
                title="Sync Infrastructure State",
                project=self.project_name,
            )

        if logger:
            logger.step("Syncing infrastructure state to database")

        # 1. Sync VMs from Terraform state
        self._sync_vms(logger)

        # 2. Sync orchestrator IP to shared secrets
        self._sync_orchestrator_ip(logger)

        # 3. Sync actual_state JSON
        self._sync_actual_state(logger)

        if logger:
            logger.success("Sync complete")

        # Output
        if self.json_output:
            self.output_json(
                {
                    "project": self.project_name,
                    "synced_items": self.synced_items,
                    "status": "success",
                }
            )
        else:
            self._print_summary()

    def _sync_vms(self, logger) -> None:
        """Sync VM IPs from Terraform state to database."""
        from cli.state_manager import StateManager
        from cli.database import get_db_session, Project, VM

        if logger:
            logger.log("Syncing VMs from Terraform state...")

        # Load state from Terraform
        state_mgr = StateManager(self.project_root, self.project_name)
        state = state_mgr.load_state()
        vms_from_state = state.get("vms", {})

        if not vms_from_state:
            if logger:
                logger.log("[yellow]No VMs found in Terraform state[/yellow]")
            return

        db = get_db_session()
        try:
            project = (
                db.query(Project).filter(Project.name == self.project_name).first()
            )
            if not project:
                if logger:
                    logger.log_error(
                        f"Project '{self.project_name}' not found in database"
                    )
                return

            # Update VMs table
            for vm_key, vm_data in vms_from_state.items():
                if "external_ip" not in vm_data:
                    continue  # Skip config entries

                # Parse vm_key: "app-0" -> role="app"
                parts = vm_key.rsplit("-", 1)
                role = parts[0] if len(parts) > 1 else vm_key

                # Find or create VM record
                vm = (
                    db.query(VM)
                    .filter(VM.project_id == project.id, VM.role == role)
                    .first()
                )

                if vm:
                    vm.name = f"{self.project_name}-{vm_key}"
                    vm.external_ip = vm_data.get("external_ip")
                    vm.internal_ip = vm_data.get("internal_ip")
                    vm.status = "running"
                    self.synced_items.append(
                        f"VM {vm_key}: {vm_data.get('external_ip')}"
                    )

            db.commit()

            if logger:
                logger.log(f"✓ Synced {len(self.synced_items)} VMs")

        finally:
            db.close()

    def _sync_orchestrator_ip(self, logger) -> None:
        """Sync ORCHESTRATOR_IP to shared secrets."""
        from cli.core.orchestrator_loader import OrchestratorLoader
        from cli.secret_manager import SecretManager

        if logger:
            logger.log("Syncing orchestrator IP...")

        try:
            # Get orchestrator IP
            orch_loader = OrchestratorLoader(self.project_root / "shared")
            orch_config = orch_loader.load()

            if not orch_config.is_deployed():
                if logger:
                    logger.log("[yellow]Orchestrator not deployed[/yellow]")
                return

            orchestrator_ip = orch_config.get_ip()
            if not orchestrator_ip:
                if logger:
                    logger.log("[yellow]Orchestrator IP not found[/yellow]")
                return

            # Update shared secrets
            secret_mgr = SecretManager(
                self.project_root, self.project_name, "production"
            )
            current_ip = secret_mgr.get_shared_secrets().get("ORCHESTRATOR_IP", "")

            if current_ip != orchestrator_ip:
                secret_mgr.set_shared_secret(
                    "ORCHESTRATOR_IP", orchestrator_ip, source="shared"
                )
                self.synced_items.append(f"ORCHESTRATOR_IP: {orchestrator_ip}")
                if logger:
                    logger.log(f"✓ Updated ORCHESTRATOR_IP: {orchestrator_ip}")
            else:
                if logger:
                    logger.log(f"✓ ORCHESTRATOR_IP already set: {orchestrator_ip}")

        except FileNotFoundError:
            if logger:
                logger.log("[yellow]Orchestrator not configured[/yellow]")
        except Exception as e:
            if logger:
                logger.log(f"[red]Error syncing orchestrator IP: {e}[/red]")

    def _sync_actual_state(self, logger) -> None:
        """Sync actual_state JSON column in projects table."""
        from cli.state_manager import StateManager
        from cli.database import get_db_session, Project
        from sqlalchemy.orm.attributes import flag_modified

        if logger:
            logger.log("Syncing actual_state JSON...")

        # Load state from Terraform
        state_mgr = StateManager(self.project_root, self.project_name)
        state = state_mgr.load_state()
        vms_from_state = state.get("vms", {})

        db = get_db_session()
        try:
            project = (
                db.query(Project).filter(Project.name == self.project_name).first()
            )
            if not project:
                return

            actual_state = project.actual_state or {}

            # Build clean VMs dict (only runtime entries with IPs)
            clean_vms = {}
            for vm_key, vm_data in vms_from_state.items():
                if "external_ip" not in vm_data:
                    continue

                # Parse role from vm_key
                parts = vm_key.rsplit("-", 1)
                role = parts[0] if len(parts) > 1 else vm_key

                clean_vms[vm_key] = {
                    "external_ip": vm_data.get("external_ip"),
                    "internal_ip": vm_data.get("internal_ip"),
                    "role": role,
                    "status": "running",
                    "updated_at": datetime.utcnow().isoformat(),
                }

            if clean_vms:
                actual_state["vms"] = clean_vms
                actual_state["status"] = "running"
                actual_state["last_sync"] = datetime.utcnow().isoformat()

                project.actual_state = actual_state
                flag_modified(project, "actual_state")
                db.commit()

                self.synced_items.append(f"actual_state: {len(clean_vms)} VMs")
                if logger:
                    logger.log(f"✓ Updated actual_state with {len(clean_vms)} VMs")

        finally:
            db.close()

    def _print_summary(self) -> None:
        """Print sync summary."""
        self.console.print()

        if self.synced_items:
            table = Table(title="Synced Items", title_justify="left")
            table.add_column("Item", style="cyan")
            table.add_column("Value", style="green")

            for item in self.synced_items:
                if ":" in item:
                    key, value = item.split(":", 1)
                    table.add_row(key.strip(), value.strip())
                else:
                    table.add_row(item, "✓")

            self.console.print(table)
        else:
            self.console.print(
                "[yellow]No items needed syncing - already up to date[/yellow]"
            )

        self.console.print()
        self.print_success("Sync complete!")
        self.console.print()


class SyncExportCommand(ProjectCommand):
    """Export full project snapshot to JSON file."""

    def __init__(
        self,
        project_name: str,
        output_path: str = None,
        verbose: bool = False,
        json_output: bool = False,
    ):
        super().__init__(project_name, verbose=verbose, json_output=json_output)
        self.output_path = output_path

    def execute(self) -> None:
        """Execute export command."""
        from cli.database import (
            get_db_session,
            Project,
            App,
            VM,
            Addon,
            Secret,
            SecretAlias,
        )

        if not self.json_output:
            self.show_header(
                title="Export Project Snapshot",
                project=self.project_name,
            )

        self.console.print("[dim]Collecting project data...[/dim]\n")

        db = get_db_session()
        try:
            # Get project
            project = (
                db.query(Project).filter(Project.name == self.project_name).first()
            )
            if not project:
                self.print_error(f"Project '{self.project_name}' not found")
                raise SystemExit(1)

            # Build export data
            export_data = {
                "version": "1.0",
                "exported_at": datetime.utcnow().isoformat(),
                "project": {
                    "name": project.name,
                    "description": project.description,
                    "project_type": project.project_type,
                    "domain": project.domain,
                    "ssl_email": project.ssl_email,
                    "github_org": project.github_org,
                    "gcp_project": project.gcp_project,
                    "gcp_region": project.gcp_region,
                    "gcp_zone": project.gcp_zone,
                    "ssh_key_path": project.ssh_key_path,
                    "ssh_public_key_path": project.ssh_public_key_path,
                    "ssh_user": project.ssh_user,
                    "docker_registry": project.docker_registry,
                    "docker_organization": project.docker_organization,
                    "vpc_subnet": project.vpc_subnet,
                    "docker_subnet": project.docker_subnet,
                    "actual_state": project.actual_state,
                },
                "apps": [],
                "vms": [],
                "addons": [],
                "secrets": {
                    "shared": [],
                    "app": [],
                    "addon": [],
                },
                "aliases": [],
            }

            # Get apps
            apps = db.query(App).filter(App.project_id == project.id).all()
            for app in apps:
                export_data["apps"].append(
                    {
                        "name": app.name,
                        "repo": app.repo,
                        "owner": app.owner,
                        "path": app.path,
                        "vm": app.vm,
                        "port": app.port,
                        "external_port": app.external_port,
                        "domain": app.domain,
                        "replicas": app.replicas,
                        "type": app.type,
                        "services": app.services,
                    }
                )

            # Get VMs
            vms = db.query(VM).filter(VM.project_id == project.id).all()
            for vm in vms:
                export_data["vms"].append(
                    {
                        "name": vm.name,
                        "role": vm.role,
                        "external_ip": vm.external_ip,
                        "internal_ip": vm.internal_ip,
                        "status": vm.status,
                        "count": vm.count,
                        "machine_type": vm.machine_type,
                        "disk_size": vm.disk_size,
                    }
                )

            # Get addons
            addons = db.query(Addon).filter(Addon.project_id == project.id).all()
            for addon in addons:
                export_data["addons"].append(
                    {
                        "instance_name": addon.instance_name,
                        "category": addon.category,
                        "type": addon.type,
                        "version": addon.version,
                        "vm": addon.vm,
                        "plan": addon.plan,
                    }
                )

            # Get secrets (grouped by source)
            secrets = db.query(Secret).filter(Secret.project_id == project.id).all()

            # Build app id to name mapping
            app_id_to_name = {app.id: app.name for app in apps}

            for secret in secrets:
                secret_data = {
                    "key": secret.key,
                    "value": secret.value,
                    "environment": secret.environment,
                    "source": secret.source,
                    "editable": secret.editable,
                }

                if secret.app_id:
                    secret_data["app_name"] = app_id_to_name.get(secret.app_id)
                    export_data["secrets"]["app"].append(secret_data)
                elif secret.source == "addon":
                    export_data["secrets"]["addon"].append(secret_data)
                else:
                    export_data["secrets"]["shared"].append(secret_data)

            # Get aliases
            aliases = (
                db.query(SecretAlias).filter(SecretAlias.project_id == project.id).all()
            )
            for alias in aliases:
                alias_data = {
                    "alias_key": alias.alias_key,
                    "target_key": alias.target_key,
                }
                if alias.app_id:
                    alias_data["app_name"] = app_id_to_name.get(alias.app_id)
                export_data["aliases"].append(alias_data)

            # Get orchestrator info
            orchestrator = (
                db.query(Project).filter(Project.name == "orchestrator").first()
            )
            if orchestrator:
                export_data["orchestrator"] = {
                    "gcp_project": orchestrator.gcp_project,
                    "gcp_region": orchestrator.gcp_region,
                    "gcp_zone": orchestrator.gcp_zone,
                    "actual_state": orchestrator.actual_state,
                }

        finally:
            db.close()

        # Determine output path
        if self.output_path:
            output_file = Path(self.output_path)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = (
                self.project_root / f"{self.project_name}_snapshot_{timestamp}.json"
            )

        # Write to file
        with open(output_file, "w") as f:
            json.dump(export_data, f, indent=2, default=str)

        # Summary
        self.console.print(f"[green]✓[/green] Project: {project.name}")
        self.console.print(f"[green]✓[/green] Apps: {len(export_data['apps'])}")
        self.console.print(f"[green]✓[/green] VMs: {len(export_data['vms'])}")
        self.console.print(f"[green]✓[/green] Addons: {len(export_data['addons'])}")
        self.console.print(
            f"[green]✓[/green] Secrets: {len(export_data['secrets']['shared'])} shared, {len(export_data['secrets']['app'])} app, {len(export_data['secrets']['addon'])} addon"
        )
        self.console.print(f"[green]✓[/green] Aliases: {len(export_data['aliases'])}")
        self.console.print()
        self.console.print(f"[bold green]✓ Exported to:[/bold green] {output_file}")
        self.console.print()

        if self.json_output:
            self.output_json(
                {
                    "status": "success",
                    "output_file": str(output_file),
                    "stats": {
                        "apps": len(export_data["apps"]),
                        "vms": len(export_data["vms"]),
                        "addons": len(export_data["addons"]),
                        "secrets": {
                            "shared": len(export_data["secrets"]["shared"]),
                            "app": len(export_data["secrets"]["app"]),
                            "addon": len(export_data["secrets"]["addon"]),
                        },
                        "aliases": len(export_data["aliases"]),
                    },
                }
            )


class SyncImportCommand:
    """Import project snapshot from JSON file."""

    def __init__(
        self,
        input_path: str,
        verbose: bool = False,
        json_output: bool = False,
        force: bool = False,
    ):
        from rich.console import Console

        self.input_path = input_path
        self.force = force
        self.verbose = verbose
        self.json_output = json_output
        self.console = Console()
        self.project_name = None  # Will be read from JSON

    def run(self) -> None:
        """Run the import command."""
        self.execute()

    def execute(self) -> None:
        """Execute import command."""
        from cli.database import (
            get_db_session,
            Project,
            App,
            VM,
            Addon,
            Secret,
            SecretAlias,
        )

        input_file = Path(self.input_path)
        if not input_file.exists():
            self.console.print(f"[red]✗ File not found: {input_file}[/red]")
            raise SystemExit(1)

        # Load JSON
        self.console.print(f"[dim]Loading snapshot from {input_file}...[/dim]\n")

        with open(input_file, "r") as f:
            data = json.load(f)

        # Validate version
        if data.get("version") != "1.0":
            self.console.print(
                f"[red]✗ Unsupported snapshot version: {data.get('version')}[/red]"
            )
            raise SystemExit(1)

        # Get project name from JSON
        project_data = data.get("project", {})
        self.project_name = project_data.get("name")

        if not self.project_name:
            self.console.print("[red]✗ No project name found in snapshot[/red]")
            raise SystemExit(1)

        if not self.json_output:
            self.console.print(
                "[bold cyan] superdeploy [/bold cyan]› Import Project Snapshot"
            )
            self.console.print(
                f"[bold cyan] superdeploy [/bold cyan]› Project: {self.project_name}\n"
            )

        db = get_db_session()
        try:
            # Check if project exists
            existing_project = (
                db.query(Project).filter(Project.name == self.project_name).first()
            )

            if existing_project and not self.force:
                self.console.print(
                    f"[red]✗ Project '{self.project_name}' already exists. Use --force to overwrite.[/red]"
                )
                raise SystemExit(1)

            # If force and exists, delete existing data
            if existing_project and self.force:
                self.console.print(
                    "[yellow]⚠️  Deleting existing project data...[/yellow]"
                )
                # Delete in correct order (foreign keys)
                db.query(SecretAlias).filter(
                    SecretAlias.project_id == existing_project.id
                ).delete()
                db.query(Secret).filter(
                    Secret.project_id == existing_project.id
                ).delete()
                db.query(Addon).filter(Addon.project_id == existing_project.id).delete()
                db.query(VM).filter(VM.project_id == existing_project.id).delete()
                db.query(App).filter(App.project_id == existing_project.id).delete()
                db.delete(existing_project)
                db.commit()

            # Create project
            project_data = data["project"]
            project = Project(
                name=project_data["name"],
                description=project_data.get("description"),
                project_type=project_data.get("project_type", "application"),
                domain=project_data.get("domain"),
                ssl_email=project_data.get("ssl_email"),
                github_org=project_data.get("github_org"),
                gcp_project=project_data.get("gcp_project"),
                gcp_region=project_data.get("gcp_region"),
                gcp_zone=project_data.get("gcp_zone"),
                ssh_key_path=project_data.get("ssh_key_path"),
                ssh_public_key_path=project_data.get("ssh_public_key_path"),
                ssh_user=project_data.get("ssh_user"),
                docker_registry=project_data.get("docker_registry"),
                docker_organization=project_data.get("docker_organization"),
                vpc_subnet=project_data.get("vpc_subnet"),
                docker_subnet=project_data.get("docker_subnet"),
                actual_state=project_data.get("actual_state"),
            )
            db.add(project)
            db.flush()  # Get project.id

            self.console.print(f"[green]✓[/green] Created project: {project.name}")

            # Create apps
            app_name_to_id = {}
            for app_data in data.get("apps", []):
                app = App(
                    project_id=project.id,
                    name=app_data["name"],
                    repo=app_data.get("repo"),
                    owner=app_data.get("owner"),
                    path=app_data.get("path"),
                    vm=app_data.get("vm"),
                    port=app_data.get("port"),
                    external_port=app_data.get("external_port"),
                    domain=app_data.get("domain"),
                    replicas=app_data.get("replicas", 1),
                    type=app_data.get("type"),
                    services=app_data.get("services"),
                )
                db.add(app)
                db.flush()
                app_name_to_id[app.name] = app.id

            self.console.print(
                f"[green]✓[/green] Created {len(data.get('apps', []))} apps"
            )

            # Create VMs
            for vm_data in data.get("vms", []):
                vm = VM(
                    project_id=project.id,
                    name=vm_data.get("name"),
                    role=vm_data["role"],
                    external_ip=vm_data.get("external_ip"),
                    internal_ip=vm_data.get("internal_ip"),
                    status=vm_data.get("status"),
                    count=vm_data.get("count", 1),
                    machine_type=vm_data.get("machine_type", "e2-medium"),
                    disk_size=vm_data.get("disk_size", 20),
                )
                db.add(vm)

            self.console.print(
                f"[green]✓[/green] Created {len(data.get('vms', []))} VMs"
            )

            # Create addons
            for addon_data in data.get("addons", []):
                addon = Addon(
                    project_id=project.id,
                    instance_name=addon_data["instance_name"],
                    category=addon_data["category"],
                    type=addon_data["type"],
                    version=addon_data.get("version", "latest"),
                    vm=addon_data.get("vm", "core"),
                    plan=addon_data.get("plan"),
                )
                db.add(addon)

            self.console.print(
                f"[green]✓[/green] Created {len(data.get('addons', []))} addons"
            )

            # Create secrets
            secrets_data = data.get("secrets", {})
            secret_count = 0

            # Shared secrets
            for secret_data in secrets_data.get("shared", []):
                secret = Secret(
                    project_id=project.id,
                    app_id=None,
                    key=secret_data["key"],
                    value=secret_data["value"],
                    environment=secret_data.get("environment", "production"),
                    source=secret_data.get("source", "shared"),
                    editable=secret_data.get("editable", True),
                )
                db.add(secret)
                secret_count += 1

            # Addon secrets
            for secret_data in secrets_data.get("addon", []):
                secret = Secret(
                    project_id=project.id,
                    app_id=None,
                    key=secret_data["key"],
                    value=secret_data["value"],
                    environment=secret_data.get("environment", "production"),
                    source="addon",
                    editable=secret_data.get("editable", False),
                )
                db.add(secret)
                secret_count += 1

            # App secrets
            for secret_data in secrets_data.get("app", []):
                app_id = app_name_to_id.get(secret_data.get("app_name"))
                secret = Secret(
                    project_id=project.id,
                    app_id=app_id,
                    key=secret_data["key"],
                    value=secret_data["value"],
                    environment=secret_data.get("environment", "production"),
                    source="app",
                    editable=secret_data.get("editable", True),
                )
                db.add(secret)
                secret_count += 1

            self.console.print(f"[green]✓[/green] Created {secret_count} secrets")

            # Create aliases
            for alias_data in data.get("aliases", []):
                app_id = app_name_to_id.get(alias_data.get("app_name"))
                if app_id:  # Aliases require app_id
                    alias = SecretAlias(
                        project_id=project.id,
                        app_id=app_id,
                        alias_key=alias_data["alias_key"],
                        target_key=alias_data["target_key"],
                    )
                    db.add(alias)

            self.console.print(
                f"[green]✓[/green] Created {len(data.get('aliases', []))} aliases"
            )

            # Import orchestrator if present
            if "orchestrator" in data:
                orch_data = data["orchestrator"]
                existing_orch = (
                    db.query(Project).filter(Project.name == "orchestrator").first()
                )

                if not existing_orch:
                    orchestrator = Project(
                        name="orchestrator",
                        project_type="orchestrator",
                        gcp_project=orch_data.get("gcp_project"),
                        gcp_region=orch_data.get("gcp_region"),
                        gcp_zone=orch_data.get("gcp_zone"),
                        actual_state=orch_data.get("actual_state"),
                    )
                    db.add(orchestrator)
                    self.console.print("[green]✓[/green] Created orchestrator entry")
                elif self.force:
                    existing_orch.gcp_project = orch_data.get("gcp_project")
                    existing_orch.gcp_region = orch_data.get("gcp_region")
                    existing_orch.gcp_zone = orch_data.get("gcp_zone")
                    existing_orch.actual_state = orch_data.get("actual_state")
                    self.console.print("[green]✓[/green] Updated orchestrator entry")

            db.commit()

            self.console.print()
            self.console.print("[bold green]✓ Import complete![/bold green]")
            self.console.print(f"[dim]Imported from: {input_file}[/dim]")
            self.console.print()

        except Exception as e:
            db.rollback()
            self.console.print(f"[red]✗ Import failed: {e}[/red]")
            raise SystemExit(1)
        finally:
            db.close()

        if self.json_output:
            import json as json_module

            self.console.print(
                json_module.dumps(
                    {
                        "status": "success",
                        "project": self.project_name,
                        "imported_from": str(input_file),
                    },
                    indent=2,
                )
            )


@click.command()
@click.option("--verbose", "-v", is_flag=True, help="Show verbose output")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def sync(project, verbose, json_output):
    """
    Sync infrastructure state to database

    Use this command when:
    - Database and actual state are out of sync
    - After manual infrastructure changes
    - When dashboard shows incorrect data

    This syncs:
    - VM IPs from Terraform state
    - ORCHESTRATOR_IP to shared secrets
    - actual_state JSON column

    Examples:
        superdeploy cheapa:sync
        superdeploy cheapa:sync -v
        superdeploy cheapa:sync --json
    """
    cmd = SyncCommand(project, verbose=verbose, json_output=json_output)
    cmd.run()


@click.command("sync:export")
@click.argument("project_name")
@click.option(
    "-o",
    "--output",
    "output_path",
    help="Output file path (default: PROJECT_snapshot_TIMESTAMP.json)",
)
@click.option("--verbose", "-v", is_flag=True, help="Show verbose output")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def sync_export(project_name, output_path, verbose, json_output):
    """
    Export full project snapshot to JSON file

    Exports everything:
    - Project configuration
    - Apps, VMs, Addons
    - All secrets (shared, app, addon)
    - Secret aliases
    - Orchestrator info

    Examples:
        superdeploy sync:export cheapa
        superdeploy sync:export cheapa -o backup.json
    """
    cmd = SyncExportCommand(
        project_name, output_path=output_path, verbose=verbose, json_output=json_output
    )
    cmd.run()


@click.command("sync:import")
@click.argument("input_path")
@click.option("--force", is_flag=True, help="Overwrite existing project data")
@click.option("--verbose", "-v", is_flag=True, help="Show verbose output")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def sync_import(input_path, force, verbose, json_output):
    """
    Import project snapshot from JSON file

    Project name is read from the JSON file automatically.

    Imports everything into correct tables:
    - projects, apps, vms, addons
    - secrets (shared, app, addon)
    - secret_aliases

    Examples:
        superdeploy sync:import backup.json
        superdeploy sync:import backup.json --force
    """
    cmd = SyncImportCommand(
        input_path=input_path,
        force=force,
        verbose=verbose,
        json_output=json_output,
    )
    cmd.run()
