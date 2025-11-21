"""SuperDeploy CLI - Status command (Refactored)"""

import click
import json
from rich.table import Table
from cli.base import ProjectCommand


class StatusCommand(ProjectCommand):
    """Show infrastructure and application status (Heroku-style)."""

    def __init__(
        self,
        project_name: str,
        app: str = None,
        verbose: bool = False,
        json_output: bool = False,
    ):
        super().__init__(project_name, verbose=verbose, json_output=json_output)
        self.app_filter = app
        self.table = Table(
            title=f"{project_name} - Infrastructure Status",
            title_justify="left",
            padding=(0, 1),
        )
        self.table.add_column("Component", style="cyan", no_wrap=True)
        self.table.add_column("Status", style="green")
        self.table.add_column("Details", style="dim")
        self.table.add_column("Version", style="yellow")

    def execute(self) -> None:
        """Execute status command."""
        # If app filter is provided, show app-specific status (Heroku-style)
        if self.app_filter:
            self._show_app_status()
        else:
            self._show_infrastructure_status()

    def _show_app_status(self) -> None:
        """Show Heroku-style app status with addons, processes, resources."""
        # Initialize logger (skip in JSON mode)
        logger = self.init_logger(self.project_name, f"status-{self.app_filter}")

        if not self.json_output:
            self.show_header(
                title=f"App Status: {self.app_filter}",
                project=self.project_name,
                app=self.app_filter,
            )

        if logger:
            logger.step("Loading app configuration")

        # Get app config
        config = self.config_service.get_raw_config(self.project_name)
        apps = config.get("apps", {})

        if self.app_filter not in apps:
            if self.json_output:
                self.output_json(
                    {"error": f"App '{self.app_filter}' not found"}, exit_code=1
                )
            else:
                self.print_error(f"App '{self.app_filter}' not found")
            raise SystemExit(1)

        app_config = apps[self.app_filter]

        # Build app status data
        app_status = {
            "app": self.app_filter,
            "type": app_config.get(
                "type", "web" if app_config.get("port") else "worker"
            ),
            "repo": app_config.get("repo"),
            "owner": app_config.get("owner"),
            "port": app_config.get("port"),
            "vm": app_config.get("vm", "app"),
            "replicas": app_config.get("replicas", 1),
            "addons": [],
            "processes": [],
            "resources": {},
            "deployment": {},
        }

        # Parse addon attachments from config (if any)
        config_attachments = self.config_service.parse_app_attachments(app_config)
        addon_instances = self.config_service.parse_addons(config)

        # Build addons list from config FIRST (before runtime check)
        # This ensures addons show even if deployment state doesn't exist
        for attachment in config_attachments:
            addon_instance = None
            for instance in addon_instances:
                if instance.full_name == attachment.addon:
                    addon_instance = instance
                    break

            if addon_instance:
                app_status["addons"].append(
                    {
                        "reference": attachment.addon,
                        "name": addon_instance.name,
                        "type": addon_instance.type,
                        "category": addon_instance.category,
                        "version": addon_instance.version,
                        "plan": addon_instance.plan,
                        "as": attachment.as_,
                        "access": attachment.access,
                        "status": "unknown",  # Will be updated if runtime check succeeds
                        "source": "config",
                    }
                )

        # Try to get runtime status from VM
        try:
            # Check if VMs exist in DB (don't require deployment state file)
            from cli.database import get_db_session
            from sqlalchemy import text
            
            db = get_db_session()
            try:
                vm_check = db.execute(
                    text("SELECT COUNT(*) FROM vms WHERE project_id = (SELECT id FROM projects WHERE name = :project)"),
                    {"project": self.project_name}
                )
                vm_count = vm_check.fetchone()[0]
                if vm_count == 0:
                    raise SystemExit("No VMs found in database")
            finally:
                db.close()
            
            vm_service = self.ensure_vm_service()
            ssh_service = vm_service.get_ssh_service()

            # Get VM for this app
            try:
                vm_name, vm_ip = self.get_vm_for_app(self.app_filter)
                app_status["vm_name"] = vm_name
                app_status["vm_ip"] = vm_ip

                # Get ALL containers on ALL VMs to detect addons
                all_vms = vm_service.get_all_vms()
                running_addons = {}

                for vm_name_iter, vm_data in all_vms.items():
                    vm_ip_iter = vm_data["external_ip"]

                    all_containers_result = ssh_service.execute_command(
                        vm_ip_iter,
                        "docker ps --format '{{.Names}}\\t{{.Status}}\\t{{.ID}}'",
                        timeout=5,
                    )

                    # Parse all containers and identify addons
                    if (
                        all_containers_result.returncode == 0
                        and all_containers_result.stdout.strip()
                    ):
                        for line in all_containers_result.stdout.strip().split("\n"):
                            if "\t" in line:
                                parts = line.split("\t")
                                container_name = parts[0]
                                status = parts[1] if len(parts) > 1 else "unknown"

                                # Detect addon containers (project_postgres_*, project_rabbitmq_*, project_caddy_*, etc.)
                                for instance in addon_instances:
                                    addon_container_prefix = (
                                        f"{self.project_name}_{instance.type}_"
                                    )
                                    if container_name.startswith(
                                        addon_container_prefix
                                    ):
                                        running_addons[instance.full_name] = {
                                            "container": container_name,
                                            "status": status,
                                            "instance": instance,
                                            "vm": vm_name_iter,
                                        }

                                # Special handling for Caddy (proxy addon) - only if not already detected
                                if container_name.startswith(
                                    f"{self.project_name}_caddy_"
                                ):
                                    # Extract caddy instance name from container
                                    # Format: cheapa_caddy_core or cheapa_caddy_app
                                    caddy_name = container_name.replace(
                                        f"{self.project_name}_caddy_", ""
                                    )

                                    # Check if this caddy is already detected as proxy.*
                                    proxy_ref = f"proxy.{caddy_name}"
                                    if proxy_ref in running_addons:
                                        # Already detected via addon_instances, skip
                                        continue
                                    
                                    # Create a pseudo-instance for Caddy if not already in addon_instances
                                    caddy_ref = f"caddy.{caddy_name}"
                                    if caddy_ref not in running_addons:
                                        from cli.core.addon_instance import AddonInstance

                                        caddy_instance = AddonInstance(
                                            category="proxy",
                                            name=caddy_name,
                                            type="caddy",
                                            version="latest",
                                            plan="standard",
                                        )
                                        running_addons[caddy_ref] = {
                                            "container": container_name,
                                            "status": status,
                                            "instance": caddy_instance,
                                            "vm": vm_name_iter,
                                        }

                # Update addon status from runtime (addons were already added from config)
                seen_addons = set()

                # Update status for already-added config attachments
                for addon_entry in app_status["addons"]:
                    addon_ref = addon_entry["reference"]
                    if addon_ref in running_addons:
                        addon_entry["status"] = running_addons[addon_ref]["status"]
                    else:
                        addon_entry["status"] = "not running"
                    seen_addons.add(addon_ref)

                # Then, add running addons that aren't in config (auto-detected)
                for addon_ref, addon_info in running_addons.items():
                    if addon_ref not in seen_addons:
                        instance = addon_info["instance"]
                        # Auto-detect "as" prefix
                        as_prefix = instance.type.upper()

                        app_status["addons"].append(
                            {
                                "reference": addon_ref,
                                "name": instance.name,
                                "type": instance.type,
                                "category": instance.category,
                                "version": instance.version,
                                "plan": instance.plan,
                                "as": as_prefix,
                                "access": "auto-detected",
                                "status": addon_info["status"],
                                "source": "runtime",
                            }
                        )

                # Get app container status
                result = ssh_service.execute_command(
                    vm_ip,
                    f"docker ps -a --filter name={self.project_name}-{self.app_filter} --format '{{{{.Names}}}}\\t{{{{.Status}}}}\\t{{{{.ID}}}}'",
                    timeout=5,
                )

                if result.returncode == 0 and result.stdout.strip():
                    for line in result.stdout.strip().split("\n"):
                        if "\t" in line:
                            parts = line.split("\t")
                            container_name = parts[0]
                            status = parts[1] if len(parts) > 1 else "unknown"
                            container_id = parts[2] if len(parts) > 2 else ""

                            app_status["processes"].append(
                                {
                                    "container": container_name,
                                    "status": status,
                                    "id": container_id[:12],
                                }
                            )

                # Get version info
                version_result = ssh_service.execute_command(
                    vm_ip,
                    f"cat /opt/superdeploy/projects/{self.project_name}/versions.json 2>/dev/null || echo '{{}}'",
                    timeout=5,
                )

                if version_result.returncode == 0 and version_result.stdout.strip():
                    versions = json.loads(version_result.stdout)
                    if self.app_filter in versions:
                        app_status["deployment"] = versions[self.app_filter]

                # Get resource usage (memory, cpu)
                if app_status["processes"]:
                    container_ids = " ".join([p["id"] for p in app_status["processes"]])
                    stats_result = ssh_service.execute_command(
                        vm_ip,
                        f"docker stats --no-stream --format '{{{{.Container}}}}\\t{{{{.CPUPerc}}}}\\t{{{{.MemUsage}}}}' {container_ids}",
                        timeout=5,
                    )

                    if stats_result.returncode == 0 and stats_result.stdout.strip():
                        for line in stats_result.stdout.strip().split("\n"):
                            if "\t" in line:
                                parts = line.split("\t")
                                container_id = parts[0]
                                cpu = parts[1] if len(parts) > 1 else "0%"
                                mem = parts[2] if len(parts) > 2 else "0MiB / 0MiB"

                                app_status["resources"][container_id] = {
                                    "cpu": cpu,
                                    "memory": mem,
                                }

            except Exception as e:
                app_status["runtime_error"] = str(e)
                if self.verbose:
                    if logger:
                        logger.log(f"Error getting runtime status: {e}")

        except SystemExit:
            # Not deployed yet
            app_status["deployed"] = False

        if logger:
            logger.success("App status loaded")

        # Output based on mode
        if self.json_output:
            self.output_json(
                {
                    "project": self.project_name,
                    "app_status": app_status,
                }
            )
        else:
            # Beautiful console output
            self._print_app_status_table(app_status)

            if not self.verbose and logger:
                self.console.print(f"\n[dim]Logs saved to:[/dim] {logger.log_path}\n")

    def _print_app_status_table(self, app_status: dict) -> None:
        """Print beautiful Heroku-style app status."""
        from rich.panel import Panel
        from rich.text import Text

        self.console.print()

        # Basic info
        info_text = Text()
        info_text.append("App: ", style="dim")
        info_text.append(f"{app_status['app']}\n", style="bold cyan")
        info_text.append("Type: ", style="dim")
        info_text.append(f"{app_status['type']}\n")
        info_text.append("Replicas: ", style="dim")
        info_text.append(f"{app_status['replicas']}\n")
        if app_status.get("port"):
            info_text.append("Port: ", style="dim")
            info_text.append(f"{app_status['port']}\n")
        info_text.append("VM: ", style="dim")
        info_text.append(f"{app_status['vm']}\n")

        self.console.print(Panel(info_text, title="App Info", border_style="cyan"))

        # Addons
        if app_status["addons"]:
            self.console.print("\n[bold]Add-ons:[/bold]")
            addon_table = Table(show_header=True, padding=(0, 1))
            addon_table.add_column("Type", style="cyan", no_wrap=True)
            addon_table.add_column("Reference", style="white")
            addon_table.add_column("Version", style="dim")
            addon_table.add_column("Status", style="green")

            for addon in app_status["addons"]:
                # Color code status
                status = addon.get("status", "unknown")
                if "Up" in status:
                    status_styled = f"[green]●[/green] {status}"
                elif "not running" in status:
                    status_styled = f"[red]●[/red] {status}"
                else:
                    status_styled = f"[yellow]●[/yellow] {status}"

                addon_table.add_row(
                    addon["type"],
                    addon["reference"],
                    addon["version"],
                    status_styled,
                )

            self.console.print(addon_table)

            # Show connection info
            self.console.print(
                f"\n[dim]Connected add-ons: {len(app_status['addons'])}[/dim]"
            )
        else:
            self.console.print("\n[yellow]⚠ No add-ons detected[/yellow]")
            self.console.print("[dim]Add-ons may need to be attached to this app[/dim]")

        # Processes
        if app_status["processes"]:
            self.console.print("\n[bold]Processes:[/bold]")
            process_table = Table(show_header=True, padding=(0, 1))
            process_table.add_column("Container", style="cyan", no_wrap=True)
            process_table.add_column("Status", style="green")
            process_table.add_column("CPU", style="yellow")
            process_table.add_column("Memory", style="magenta")

            for process in app_status["processes"]:
                resources = app_status["resources"].get(process["id"], {})
                cpu = resources.get("cpu", "-")
                memory = resources.get("memory", "-")

                # Color code status
                status_style = "green" if "Up" in process["status"] else "red"

                process_table.add_row(
                    process["container"],
                    f"[{status_style}]{process['status']}[/{status_style}]",
                    cpu,
                    memory,
                )

            self.console.print(process_table)
        else:
            self.console.print("\n[dim]No running processes[/dim]")

        # Deployment
        if app_status.get("deployment"):
            deployment = app_status["deployment"]
            self.console.print("\n[bold]Deployment:[/bold]")
            self.console.print(
                f"  Version: [cyan]{deployment.get('version', '-')}[/cyan]"
            )
            self.console.print(
                f"  Git SHA: [dim]{deployment.get('git_sha', '-')}[/dim]"
            )
            self.console.print(
                f"  Deployed: [yellow]{deployment.get('deployed_at', '-')}[/yellow]"
            )
            self.console.print(f"  By: [dim]{deployment.get('deployed_by', '-')}[/dim]")

        self.console.print()

    def _show_infrastructure_status(self) -> None:
        """Show infrastructure status (original behavior)."""
        # Initialize logger (skip in JSON mode)
        logger = self.init_logger(self.project_name, "status")

        if not self.json_output:
            self.show_header(title="Infrastructure Status", project=self.project_name)

        if logger:
            logger.step("Loading project configuration")

        # Check if deployed
        try:
            self.require_deployment()
            if logger:
                logger.success("Configuration loaded")
        except SystemExit:
            if logger:
                logger.warning("No deployment state found")
            if logger:
                logger.log(f"Run: [red]superdeploy {self.project_name}:up[/red]")
            raise

        if logger:
            logger.step("Checking VM and container status")

        # Get services
        vm_service = self.ensure_vm_service()
        ssh_service = vm_service.get_ssh_service()

        # Get all VMs
        all_vms = vm_service.get_all_vms()

        # Get apps
        apps = self.list_apps()

        # Prepare data structure for JSON output
        vms_data = []

        # Get version info for all apps from versions.json
        app_versions = {}
        for vm_name in all_vms.keys():
            vm_data = all_vms[vm_name]
            vm_ip = vm_data["external_ip"]

            try:
                result = ssh_service.execute_command(
                    vm_ip,
                    f"cat /opt/superdeploy/projects/{self.project_name}/versions.json 2>/dev/null || echo '{{}}'",
                    timeout=5,
                )

                if result.returncode == 0 and result.stdout.strip():
                    if self.verbose:
                        if logger:
                            logger.log(
                                f"Version data from {vm_ip}: {result.stdout.strip()}"
                            )
                    versions = json.loads(result.stdout)
                    # versions.json format: {"app_name": {"version": "1.0.5", "deployed_at": "...", ...}}
                    for app_name, version_data in versions.items():
                        if app_name not in app_versions or version_data.get(
                            "deployed_at", ""
                        ) > app_versions[app_name].get("deployed_at", ""):
                            app_versions[app_name] = version_data
            except Exception as e:
                if self.verbose:
                    if logger:
                        logger.log(f"Error reading versions from {vm_ip}: {e}")

        # Check each VM and its containers
        for vm_name in sorted(all_vms.keys()):
            vm_data = all_vms[vm_name]
            vm_ip = vm_data["external_ip"]
            role = vm_service.get_vm_role_from_name(vm_name)

            vm_info = {
                "name": vm_name,
                "role": role,
                "ip": vm_ip,
                "status": "unreachable",
                "containers": [],
            }

            # Test SSH connectivity
            if ssh_service.test_connection(vm_ip):
                vm_info["status"] = "running"

                # Get container status
                try:
                    # Try both naming conventions: dash (-) and underscore (_)
                    result = ssh_service.execute_command(
                        vm_ip,
                        f"docker ps --format '{{{{.Names}}}}\\t{{{{.Status}}}}' | grep -E '^{self.project_name}[-_]|^superdeploy-'",
                        timeout=5,
                    )

                    if self.verbose:
                        if logger:
                            logger.log(
                                f"Containers on {vm_ip}: {result.stdout.strip()}"
                            )

                    if result.returncode == 0 and result.stdout.strip():
                        # Parse containers
                        for line in result.stdout.strip().split("\n"):
                            if "\t" in line:
                                container, status = line.split("\t", 1)
                                # Extract app name from container name (handle both - and _ separators)
                                app_name = container
                                if container.startswith(f"{self.project_name}-"):
                                    app_name = container.replace(
                                        f"{self.project_name}-", "", 1
                                    )
                                elif container.startswith(f"{self.project_name}_"):
                                    app_name = container.replace(
                                        f"{self.project_name}_", "", 1
                                    )
                                elif container.startswith("superdeploy-"):
                                    app_name = container.replace("superdeploy-", "", 1)

                                # Get version for this app
                                version = "-"
                                if app_name in app_versions:
                                    version_data = app_versions[app_name]
                                    version = version_data.get("version", "-")

                                vm_info["containers"].append(
                                    {
                                        "name": app_name,
                                        "status": status,
                                        "version": version,
                                    }
                                )

                                if not self.json_output:
                                    # Add to table
                                    if not vm_info.get("_added_to_table"):
                                        self.table.add_row(
                                            f"[bold]{vm_name}[/bold] ({role})",
                                            "[green]Running[/green]",
                                            vm_ip,
                                        )
                                        vm_info["_added_to_table"] = True

                                    self.table.add_row(
                                        f"  └─ {app_name}",
                                        status,
                                        "container",
                                        version,
                                    )

                    if not vm_info["containers"] and not self.json_output:
                        # VM running but no containers
                        self.table.add_row(
                            f"[bold]{vm_name}[/bold] ({role})",
                            "[green]Running[/green]",
                            vm_ip,
                        )
                        self.table.add_row(
                            "  └─ No containers", "[yellow]Empty[/yellow]", ""
                        )
                except Exception as e:
                    vm_info["error"] = str(e)[:30]
                    if not self.json_output:
                        # SSH works but docker command failed
                        self.table.add_row(
                            f"[bold]{vm_name}[/bold] ({role})",
                            "[green]Running[/green]",
                            vm_ip,
                        )
                        self.table.add_row(
                            "  └─ Error", "[red]Failed[/red]", str(e)[:30]
                        )
            else:
                if not self.json_output:
                    # VM not reachable
                    self.table.add_row(
                        f"[bold]{vm_name}[/bold] ({role})",
                        "[red]Unreachable[/red]",
                        vm_ip,
                    )

            vms_data.append(vm_info)

        if logger:
            logger.success("Status check complete")

        # Output based on mode
        if self.json_output:
            self.output_json(
                {
                    "project": self.project_name,
                    "vms": vms_data,
                    "total_vms": len(vms_data),
                    "total_containers": sum(len(vm["containers"]) for vm in vms_data),
                }
            )
        else:
            # Display table
            if not self.verbose:
                self.console.print("\n")
                self.console.print(self.table)
                self.console.print()

                # Show useful commands
                self.console.print("[bold]Useful commands:[/bold]")
                self.console.print("  [cyan]superdeploy logs -a <app> -f[/cyan]")
                self.console.print("  [cyan]superdeploy restart -a <app>[/cyan]")
                self.console.print("  [cyan]superdeploy run <app> <command>[/cyan]")
                self.console.print()

            if not self.verbose and logger:
                self.console.print(f"[dim]Logs saved to:[/dim] {logger.log_path}\n")


@click.command()
@click.option("-a", "--app", help="Show status for specific app (Heroku-style)")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def status(project, app, verbose, json_output):
    """
    Show infrastructure and application status

    Without -a: Shows infrastructure status (VMs, containers)
    With -a: Shows Heroku-style app status (addons, processes, resources)

    Examples:
        superdeploy cheapa:status              # Infrastructure status
        superdeploy cheapa:status -a api       # App-specific status
        superdeploy cheapa:status -a api --json  # JSON output
    """
    cmd = StatusCommand(project, app=app, verbose=verbose, json_output=json_output)
    cmd.run()
