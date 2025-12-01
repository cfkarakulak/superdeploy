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

        # 1. Sync VMs from Terraform state to vms table
        self._sync_vms(logger)

        # 2. Sync orchestrator IP to shared secrets
        self._sync_orchestrator_ip(logger)

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

            # Get apps with their processes
            from cli.database import Process

            apps = db.query(App).filter(App.project_id == project.id).all()
            for app in apps:
                # Get processes for this app
                processes = db.query(Process).filter(Process.app_id == app.id).all()
                processes_data = []
                for proc in processes:
                    processes_data.append(
                        {
                            "name": proc.name,
                            "command": proc.command,
                            "replicas": proc.replicas,
                            "port": proc.port,
                        }
                    )

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
                        "processes": processes_data if processes_data else None,
                    }
                )

            # Get VMs
            vms = db.query(VM).filter(VM.project_id == project.id).all()
            for vm in vms:
                # Normalize VM name: remove project prefix if present
                # Terraform will add it back: ${project_name}-${role}-${index}
                vm_name = vm.name or ""
                if vm_name.startswith(f"{project.name}-"):
                    vm_name = vm_name[
                        len(project.name) + 1 :
                    ]  # Remove "project-" prefix

                export_data["vms"].append(
                    {
                        "name": vm_name,  # Normalized: "app-0" instead of "cheapa-app-0"
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

            # Get orchestrator info (full export including VMs and secrets)
            orchestrator = (
                db.query(Project).filter(Project.name == "orchestrator").first()
            )
            if orchestrator:
                # Get orchestrator VMs
                orch_vms = db.query(VM).filter(VM.project_id == orchestrator.id).all()
                orch_vms_data = []
                for vm in orch_vms:
                    orch_vms_data.append(
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

                # Get orchestrator secrets
                orch_secrets = (
                    db.query(Secret).filter(Secret.project_id == orchestrator.id).all()
                )
                orch_secrets_data = []
                for secret in orch_secrets:
                    orch_secrets_data.append(
                        {
                            "key": secret.key,
                            "value": secret.value,
                            "environment": secret.environment,
                            "source": secret.source,
                            "editable": secret.editable,
                        }
                    )

                # Get orchestrator addons
                orch_addons = (
                    db.query(Addon).filter(Addon.project_id == orchestrator.id).all()
                )
                orch_addons_data = []
                for addon in orch_addons:
                    orch_addons_data.append(
                        {
                            "instance_name": addon.instance_name,
                            "category": addon.category,
                            "type": addon.type,
                            "version": addon.version,
                            "vm": addon.vm,
                            "plan": addon.plan,
                        }
                    )

                export_data["orchestrator"] = {
                    "project": {
                        "name": orchestrator.name,
                        "description": orchestrator.description,
                        "project_type": orchestrator.project_type,
                        "domain": orchestrator.domain,
                        "ssl_email": orchestrator.ssl_email,
                        "gcp_project": orchestrator.gcp_project,
                        "gcp_region": orchestrator.gcp_region,
                        "gcp_zone": orchestrator.gcp_zone,
                        "ssh_key_path": orchestrator.ssh_key_path,
                        "ssh_public_key_path": orchestrator.ssh_public_key_path,
                        "ssh_user": orchestrator.ssh_user,
                        "vpc_subnet": orchestrator.vpc_subnet,
                    },
                    "vms": orch_vms_data,
                    "secrets": orch_secrets_data,
                    "addons": orch_addons_data,
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
            )
            db.add(project)
            db.flush()  # Get project.id

            self.console.print(f"[green]✓[/green] Created project: {project.name}")

            # Create apps - validate required fields
            from cli.database import Process

            app_name_to_id = {}
            process_count = 0
            for app_data in data.get("apps", []):
                # Validate required fields
                required_app_fields = ["name", "repo", "owner", "vm", "type"]
                missing = [f for f in required_app_fields if not app_data.get(f)]
                if missing:
                    raise ValueError(
                        f"App missing required fields: {missing}. App: {app_data.get('name', 'unknown')}"
                    )

                app = App(
                    project_id=project.id,
                    name=app_data["name"],
                    repo=app_data["repo"],  # Required
                    owner=app_data["owner"],  # Required
                    path=app_data.get("path"),  # Optional - local dev path
                    vm=app_data["vm"],  # Required
                    port=app_data.get("port"),  # Optional for workers
                    external_port=app_data.get("external_port"),  # Optional
                    domain=app_data.get("domain"),  # Optional
                    replicas=app_data.get("replicas") or 1,  # Default 1 if not set
                    type=app_data["type"],  # Required: web/worker/backend/frontend
                    services=app_data.get("services"),  # Optional
                )
                db.add(app)
                db.flush()
                app_name_to_id[app.name] = app.id

                # Create processes for this app
                for proc_data in app_data.get("processes") or []:
                    process = Process(
                        app_id=app.id,
                        name=proc_data["name"],
                        command=proc_data["command"],
                        replicas=proc_data.get("replicas") or 1,
                        port=proc_data.get("port"),
                    )
                    db.add(process)
                    process_count += 1

            self.console.print(
                f"[green]✓[/green] Created {len(data.get('apps', []))} apps"
            )
            if process_count > 0:
                self.console.print(
                    f"[green]✓[/green] Created {process_count} processes"
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

            # Create addons - all fields required, no fallbacks
            for addon_data in data.get("addons", []):
                # Validate required fields
                required_addon_fields = [
                    "instance_name",
                    "category",
                    "type",
                    "version",
                    "vm",
                    "plan",
                ]
                missing = [f for f in required_addon_fields if not addon_data.get(f)]
                if missing:
                    raise ValueError(
                        f"Addon missing required fields: {missing}. Addon: {addon_data}"
                    )

                addon = Addon(
                    project_id=project.id,
                    instance_name=addon_data["instance_name"],
                    category=addon_data["category"],
                    type=addon_data["type"],
                    version=addon_data["version"],  # No fallback - must be explicit
                    vm=addon_data["vm"],  # No fallback - must be explicit
                    plan=addon_data["plan"],  # No fallback - must be explicit
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

            # Import orchestrator if present (full import with VMs and secrets)
            # Skip if we're importing orchestrator project itself (already imported above)
            if "orchestrator" in data and self.project_name != "orchestrator":
                orch_data = data["orchestrator"]

                # Support both old format (flat) and new format (nested with project/vms/secrets)
                if "project" in orch_data:
                    # New format
                    orch_project_data = orch_data["project"]
                    orch_vms_data = orch_data.get("vms", [])
                    orch_secrets_data = orch_data.get("secrets", [])
                else:
                    # Old format (backward compatibility)
                    orch_project_data = orch_data
                    orch_vms_data = []
                    orch_secrets_data = []

                existing_orch = (
                    db.query(Project).filter(Project.name == "orchestrator").first()
                )

                if not existing_orch:
                    orchestrator = Project(
                        name="orchestrator",
                        project_type="orchestrator",
                        description=orch_project_data.get("description"),
                        domain=orch_project_data.get("domain"),
                        ssl_email=orch_project_data.get("ssl_email"),
                        gcp_project=orch_project_data.get("gcp_project"),
                        gcp_region=orch_project_data.get("gcp_region"),
                        gcp_zone=orch_project_data.get("gcp_zone"),
                        ssh_key_path=orch_project_data.get("ssh_key_path"),
                        ssh_public_key_path=orch_project_data.get(
                            "ssh_public_key_path"
                        ),
                        ssh_user=orch_project_data.get("ssh_user"),
                        vpc_subnet=orch_project_data.get("vpc_subnet"),
                    )
                    db.add(orchestrator)
                    db.flush()
                    self.console.print("[green]✓[/green] Created orchestrator project")
                elif self.force:
                    # Update existing orchestrator
                    existing_orch.description = orch_project_data.get("description")
                    existing_orch.domain = orch_project_data.get("domain")
                    existing_orch.ssl_email = orch_project_data.get("ssl_email")
                    existing_orch.gcp_project = orch_project_data.get("gcp_project")
                    existing_orch.gcp_region = orch_project_data.get("gcp_region")
                    existing_orch.gcp_zone = orch_project_data.get("gcp_zone")
                    existing_orch.ssh_key_path = orch_project_data.get("ssh_key_path")
                    existing_orch.ssh_public_key_path = orch_project_data.get(
                        "ssh_public_key_path"
                    )
                    existing_orch.ssh_user = orch_project_data.get("ssh_user")
                    existing_orch.vpc_subnet = orch_project_data.get("vpc_subnet")

                    # Delete existing VMs, secrets, and addons for orchestrator
                    db.query(Secret).filter(
                        Secret.project_id == existing_orch.id
                    ).delete()
                    db.query(VM).filter(VM.project_id == existing_orch.id).delete()
                    db.query(Addon).filter(
                        Addon.project_id == existing_orch.id
                    ).delete()

                    orchestrator = existing_orch
                    self.console.print("[green]✓[/green] Updated orchestrator project")
                else:
                    orchestrator = existing_orch

                # Import orchestrator VMs
                if orch_vms_data and (not existing_orch or self.force):
                    for vm_data in orch_vms_data:
                        vm = VM(
                            project_id=orchestrator.id,
                            name=vm_data.get("name"),
                            role=vm_data.get("role", "orchestrator"),
                            external_ip=vm_data.get("external_ip"),
                            internal_ip=vm_data.get("internal_ip"),
                            status=vm_data.get("status"),
                            count=vm_data.get("count", 1),
                            machine_type=vm_data.get("machine_type", "e2-medium"),
                            disk_size=vm_data.get("disk_size", 20),
                        )
                        db.add(vm)
                    self.console.print(
                        f"[green]✓[/green] Created {len(orch_vms_data)} orchestrator VMs"
                    )

                # Import orchestrator secrets
                if orch_secrets_data and (not existing_orch or self.force):
                    for secret_data in orch_secrets_data:
                        secret = Secret(
                            project_id=orchestrator.id,
                            key=secret_data["key"],
                            value=secret_data["value"],
                            environment=secret_data.get("environment", "production"),
                            source=secret_data.get("source", "shared"),
                            editable=secret_data.get("editable", True),
                        )
                        db.add(secret)
                    self.console.print(
                        f"[green]✓[/green] Created {len(orch_secrets_data)} orchestrator secrets"
                    )

                # Import orchestrator addons
                orch_addons_data = orch_data.get("addons", [])
                if orch_addons_data and (not existing_orch or self.force):
                    for addon_data in orch_addons_data:
                        addon = Addon(
                            project_id=orchestrator.id,
                            instance_name=addon_data.get("instance_name", "primary"),
                            category=addon_data.get("category"),
                            type=addon_data.get("type"),
                            version=addon_data.get("version", "latest"),
                            vm=addon_data.get("vm", "main"),
                            plan=addon_data.get("plan") or "standard",
                        )
                        db.add(addon)
                    self.console.print(
                        f"[green]✓[/green] Created {len(orch_addons_data)} orchestrator addons"
                    )

            db.commit()

            self.console.print()
            self.console.print("[bold green]✓ Import complete![/bold green]")
            self.console.print(f"[dim]Imported from: {input_file}[/dim]")
            self.console.print()

            # Post-import: Fix addon HOST secrets to point to core VM internal IP
            self._fix_addon_host_secrets(project.id, db)

        except Exception as e:
            db.rollback()
            self.console.print(f"[red]✗ Import failed: {e}[/red]")
            raise SystemExit(1)
        finally:
            db.close()

    def _fix_addon_host_secrets(self, project_id: int, db) -> None:
        """
        Fix addon HOST secrets to point to the correct core VM internal IP.

        This ensures that after import, all addon HOST values (postgres.primary.HOST,
        redis.primary.HOST, rabbitmq.primary.HOST) point to the core VM where
        the addons are actually running.
        """
        from cli.database import VM, Secret

        # Find the core VM's internal IP
        core_vm = (
            db.query(VM).filter(VM.project_id == project_id, VM.role == "core").first()
        )

        if not core_vm or not core_vm.internal_ip:
            return  # No core VM or no internal IP, skip

        core_internal_ip = core_vm.internal_ip

        # Find all addon HOST secrets and update them
        host_secrets = (
            db.query(Secret)
            .filter(
                Secret.project_id == project_id,
                Secret.key.like("%.HOST"),
                Secret.source == "addon",
            )
            .all()
        )

        updated_count = 0
        for secret in host_secrets:
            if secret.value != core_internal_ip:
                old_value = secret.value
                secret.value = core_internal_ip
                updated_count += 1
                self.console.print(
                    f"[dim]  ↳ Fixed {secret.key}: {old_value} → {core_internal_ip}[/dim]"
                )

        if updated_count > 0:
            db.commit()
            self.console.print(
                f"[green]✓[/green] Fixed {updated_count} addon HOST secrets to use core VM IP"
            )

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
    - Database and infrastructure are out of sync
    - After manual infrastructure changes
    - When dashboard shows incorrect data

    This syncs:
    - VM IPs from Terraform state to vms table
    - ORCHESTRATOR_IP to shared secrets

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
