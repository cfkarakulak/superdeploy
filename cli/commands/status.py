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
            logger.step("Loading app configuration from database")

        # Get app config from DATABASE
        from cli.database import get_db_session
        from sqlalchemy import text

        db = get_db_session()

        try:
            # Get app details
            result = db.execute(
                text("""
                SELECT a.id, a.name, a.repo, a.owner, v.name as vm_name
                FROM apps a
                JOIN vms v ON a.project_id = v.project_id
                WHERE a.project_id = (SELECT id FROM projects WHERE name = :project)
                AND a.name = :app
                LIMIT 1
            """),
                {"project": self.project_name, "app": self.app_filter},
            )

            app_row = result.fetchone()
            if not app_row:
                if self.json_output:
                    self.output_json(
                        {"error": f"App '{self.app_filter}' not found"}, exit_code=1
                    )
                else:
                    self.print_error(f"App '{self.app_filter}' not found")
                raise SystemExit(1)

            app_id = app_row[0]
            app_vm = app_row[4] if app_row[4] else "app"
            app_repo = app_row[2]
            app_owner = app_row[3]

            # Read process definitions from MARKER FILE (not DB!)
            # Marker file is the source of truth - always up-to-date
            processes_dict = {}
            app_port = None
            total_replicas = 0

            try:
                # Try local path first (if running from code directory)
                config = self.config_service.get_raw_config(self.project_name)
                apps = config.get("apps", {})
                app_config = apps.get(self.app_filter, {})
                app_path = app_config.get("path")

                if app_path:
                    from pathlib import Path
                    from cli.marker_manager import MarkerManager
                    import os

                    # Expand ~ and resolve path
                    expanded_path = (
                        Path(os.path.expanduser(app_path)).expanduser().resolve()
                    )

                    # Load marker from configured path - no fallbacks
                    marker = MarkerManager.load_marker(expanded_path)
                    if marker and marker.processes:
                        for process_name, process_def in marker.processes.items():
                            processes_dict[process_name] = {
                                "command": process_def.command,
                                "replicas": process_def.replicas,
                                "port": process_def.port,
                            }
                            if process_def.port:
                                app_port = process_def.port
                            total_replicas += process_def.replicas

                # If local not found, try VM
                if not processes_dict:
                    vm_service = self.ensure_vm_service()
                    ssh_service = vm_service.get_ssh_service()

                    # Get VM for this app
                    vm_name, vm_ip = self.get_vm_for_app(self.app_filter)

                    # Marker file path on VM
                    marker_path = f"/opt/superdeploy/projects/{self.project_name}/data/{self.app_filter}/superdeploy"

                    # Try to read marker file
                    marker_result = ssh_service.execute_command(
                        vm_ip,
                        f"cat {marker_path} 2>/dev/null || echo ''",
                        timeout=5,
                    )

                    if marker_result.returncode == 0 and marker_result.stdout.strip():
                        # Parse YAML marker file
                        import yaml

                        marker_data = yaml.safe_load(marker_result.stdout)

                        if marker_data and "processes" in marker_data:
                            for process_name, process_config in marker_data[
                                "processes"
                            ].items():
                                processes_dict[process_name] = {
                                    "command": process_config.get("command", ""),
                                    "replicas": process_config.get("replicas", 1),
                                    "port": process_config.get("port"),
                                }
                                if process_config.get("port"):
                                    app_port = process_config.get("port")
                                total_replicas += process_config.get("replicas", 1)

                # If marker file not found on VM, try GitHub (sync)
                if not processes_dict and app_repo and app_owner:
                    try:
                        import os
                        import urllib.request
                        import urllib.error

                        github_token = os.getenv("GITHUB_TOKEN")
                        if github_token:
                            # Try default branch (main/master)
                            for branch in ["main", "master"]:
                                url = f"https://api.github.com/repos/{app_owner}/{app_repo}/contents/superdeploy?ref={branch}"

                                req = urllib.request.Request(url)
                                req.add_header("Authorization", f"token {github_token}")
                                req.add_header(
                                    "Accept", "application/vnd.github.v3.raw"
                                )

                                try:
                                    with urllib.request.urlopen(
                                        req, timeout=5
                                    ) as response:
                                        if response.status == 200:
                                            marker_text = response.read().decode(
                                                "utf-8"
                                            )
                                            marker_data = yaml.safe_load(marker_text)

                                            if (
                                                marker_data
                                                and "processes" in marker_data
                                            ):
                                                for (
                                                    process_name,
                                                    process_config,
                                                ) in marker_data["processes"].items():
                                                    processes_dict[process_name] = {
                                                        "command": process_config.get(
                                                            "command", ""
                                                        ),
                                                        "replicas": process_config.get(
                                                            "replicas", 1
                                                        ),
                                                        "port": process_config.get(
                                                            "port"
                                                        ),
                                                    }
                                                    if process_config.get("port"):
                                                        app_port = process_config.get(
                                                            "port"
                                                        )
                                                    total_replicas += (
                                                        process_config.get(
                                                            "replicas", 1
                                                        )
                                                    )
                                                break
                                except urllib.error.HTTPError:
                                    continue
                                except Exception:
                                    continue
                    except Exception as github_error:
                        if self.verbose:
                            print(
                                f"Warning: Failed to read marker from GitHub: {github_error}"
                            )

            except Exception as marker_error:
                if self.verbose:
                    print(f"Warning: Failed to read marker file: {marker_error}")
                # Fallback: empty processes_dict

            # Determine app type (web if has port, worker otherwise)
            app_type = "web" if app_port else "worker"

            # Build app status data
            app_status = {
                "app": self.app_filter,
                "type": app_type,
                "repo": app_row[2],
                "owner": app_row[3],
                "port": app_port,
                "vm": app_vm,
                "replicas": total_replicas if total_replicas > 0 else 1,
                "addons": [],
                "processes": [],
                "process_definitions": processes_dict,  # Store process definitions
                "resources": {},
                "deployment": {},
            }

        finally:
            db.close()

        # Get addon attachments from DATABASE (aliases table)
        from cli.database import get_db_session
        from sqlalchemy import text

        db = get_db_session()
        seen_addon_refs = set()

        try:
            # Get app VM name
            result = db.execute(
                text("""
                SELECT v.name
                FROM apps a
                JOIN vms v ON a.project_id = v.project_id
                WHERE a.project_id = (SELECT id FROM projects WHERE name = :project)
                AND a.name = :app
                LIMIT 1
            """),
                {"project": self.project_name, "app": self.app_filter},
            )

            vm_row = result.fetchone()
            app_vm = vm_row[0] if vm_row else "app"

            # Get attached addons from aliases (these are explicitly attached)
            result = db.execute(
                text("""
                SELECT DISTINCT target_key
                FROM aliases
                WHERE project_name = :project
                AND app_name = :app
                AND target_source = 'addon'
                ORDER BY target_key
            """),
                {"project": self.project_name, "app": self.app_filter},
            )

            attached_addons = {}
            for row in result.fetchall():
                # Extract addon from target_key (e.g., "postgres.primary.HOST" -> "postgres.primary")
                parts = row[0].split(".")
                if len(parts) >= 2:
                    addon_ref = f"{parts[0]}.{parts[1]}"
                    if addon_ref not in attached_addons:
                        attached_addons[addon_ref] = parts[0]  # Store addon_type

            # Get addon details and add to app_status
            for addon_ref, addon_type in attached_addons.items():
                addon_instance = addon_ref.split(".")[1]

                # Get addon version from addon_secrets
                result = db.execute(
                    text("""
                    SELECT key, value
                    FROM addon_secrets
                    WHERE project_name = :project
                    AND addon_type = :type
                    AND addon_instance = :instance
                    LIMIT 1
                """),
                    {
                        "project": self.project_name,
                        "type": addon_type,
                        "instance": addon_instance,
                    },
                )

                if result.fetchone():
                    app_status["addons"].append(
                        {
                            "reference": addon_ref,
                            "name": addon_instance,
                            "type": addon_type,
                            "category": addon_type,  # Use type as category
                            "version": "latest",
                            "plan": "standard",
                            "as": addon_type.upper(),
                            "access": "default",
                            "status": "unknown",
                            "source": "database",
                        }
                    )
                    seen_addon_refs.add(addon_ref)

            # Always add Caddy for the app's VM (required for reverse proxy)
            # Get Caddy instance for this app's VM
            result = db.execute(
                text("""
                SELECT addon_instance
                FROM addon_secrets
                WHERE project_name = :project
                AND addon_type = 'caddy'
                LIMIT 1
            """),
                {"project": self.project_name},
            )

            caddy_row = result.fetchone()
            if caddy_row:
                caddy_instance = caddy_row[0]
                caddy_ref = f"proxy.{caddy_instance}"

                # Add Caddy if not already in the list
                if caddy_ref not in seen_addon_refs:
                    app_status["addons"].append(
                        {
                            "reference": caddy_ref,
                            "name": caddy_instance,
                            "type": "caddy",
                            "category": "proxy",
                            "version": "2-alpine",
                            "plan": "standard",
                            "as": "CADDY",
                            "access": "default",
                            "status": "unknown",
                            "source": "auto",  # Auto-attached to all apps
                        }
                    )
                    seen_addon_refs.add(caddy_ref)

        finally:
            db.close()

        # Get VM info from DB and generate mock process data
        try:
            from cli.database import get_db_session
            from sqlalchemy import text

            db = get_db_session()
            try:
                # Get VM for this app
                vm_result = db.execute(
                    text("""
                        SELECT v.name, v.external_ip
                        FROM vms v
                        JOIN apps a ON a.project_id = v.project_id
                        WHERE a.project_id = (SELECT id FROM projects WHERE name = :project)
                        AND a.name = :app
                        LIMIT 1
                    """),
                    {"project": self.project_name, "app": self.app_filter},
                )
                vm_row = vm_result.fetchone()
                if vm_row:
                    app_status["vm_name"] = vm_row[0]
                    app_status["vm_ip"] = vm_row[1]

                # Set default statuses for addons
                for addon_entry in app_status["addons"]:
                    addon_type = addon_entry["type"]
                    if addon_type in [
                        "postgres",
                        "rabbitmq",
                        "redis",
                        "mongodb",
                        "elasticsearch",
                        "caddy",
                    ]:
                        addon_entry["status"] = "Up (database)"
                    else:
                        addon_entry["status"] = "Unknown"

                # Generate mock process data from process definitions
                processes = app_status.get("process_definitions", {})
                for process_name, process_config in processes.items():
                    replicas = process_config.get("replicas", 1)
                    for i in range(1, replicas + 1):
                        container_name = f"compose-{self.app_filter}-{process_name}-{i}"
                        app_status["processes"].append(
                            {
                                "container": container_name,
                                "status": "Up (assumed)",
                                "id": f"mock{i:02d}",
                            }
                        )

            except Exception as e:
                app_status["runtime_error"] = str(e)
                if self.verbose and logger:
                    logger.log(f"Error loading app status from DB: {e}")
            finally:
                db.close()

        except Exception as outer_error:
            app_status["runtime_error"] = str(outer_error)

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
