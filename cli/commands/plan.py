"""SuperDeploy CLI - Plan command (like terraform plan)"""

import click
from pathlib import Path
from cli.base import ProjectCommand


class PlanCommand(ProjectCommand):
    """Show deployment plan - what will change."""

    def __init__(self, project_name: str, detailed: bool = False, verbose: bool = False):
        super().__init__(project_name, verbose=verbose)
        self.detailed = detailed

    def execute(self) -> None:
        """Execute plan command."""
        self.show_header(
            title="Deployment Plan",
            subtitle="Analyzing configuration changes",
            project=self.project_name,
        )

        # Initialize logger
        logger = self.init_logger(self.project_name, "plan")
        logger.step("Loading current configuration")

        # Load current config
        try:
            config = self.config_service.get_raw_config(self.project_name)
        except FileNotFoundError:
            logger.error(f"Project configuration not found")
            raise SystemExit(1)
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise SystemExit(1)

        logger.success("Configuration loaded")

        # Load state (if exists)
        logger.step("Comparing with deployed state")
        
        try:
            state = self.state_service.load_state()
            has_state = True
            logger.log("Found existing deployment state")
        except:
            state = {"vms": {}, "addons": {}, "apps": {}}
            has_state = False
            logger.log("No previous deployment found (first deployment)")

        # Detect changes
        changes = self._detect_changes(config, state)

        if not changes["has_changes"]:
            logger.success("No changes detected")
            self.console.print("\n[green]✅ Infrastructure is up to date[/green]\n")
            self.console.print("Your deployment matches config.yml\n")
            return

        logger.success(f"Detected {changes['total_changes']} change(s)")

        # Display changes
        self._display_changes(changes, config, state, has_state)

        # Show next steps
        self.console.print("\n[bold]To apply these changes:[/bold]")
        self.console.print(f"  [cyan]superdeploy {self.project_name}:up[/cyan]")
        
        if changes["needs_sync"]:
            self.console.print(f"  [dim]or[/dim]")
            self.console.print(f"  [cyan]superdeploy {self.project_name}:sync[/cyan] [dim](secrets only)[/dim]")
        
        self.console.print()

    def _detect_changes(self, config: dict, state: dict) -> dict:
        """Detect what has changed between config and state."""
        changes = {
            "has_changes": False,
            "total_changes": 0,
            "vms": {"added": [], "removed": [], "modified": []},
            "addons": {"added": [], "removed": [], "modified": []},
            "apps": {"added": [], "removed": [], "modified": []},
            "needs_terraform": False,
            "needs_ansible": False,
            "needs_generate": False,
            "needs_sync": False,
        }

        # Check VMs
        config_vms = set(config.get("vms", {}).keys())
        state_vms = set(state.get("vms", {}).keys())

        changes["vms"]["added"] = list(config_vms - state_vms)
        changes["vms"]["removed"] = list(state_vms - config_vms)

        # Check for modified VMs
        for vm_name in config_vms & state_vms:
            config_vm = config["vms"][vm_name]
            state_vm = state["vms"][vm_name]

            if self._vm_changed(config_vm, state_vm):
                changes["vms"]["modified"].append({
                    "name": vm_name,
                    "old": state_vm,
                    "new": config_vm,
                })

        # Check Addons
        config_addons = self._get_enabled_addons(config)
        state_addons = set(state.get("addons", {}).keys())

        changes["addons"]["added"] = list(config_addons - state_addons)
        changes["addons"]["removed"] = list(state_addons - config_addons)

        # Check for modified addons (config changes)
        for addon_name in config_addons & state_addons:
            addon_config = config.get("addons", {}).get(addon_name, {})
            state_addon = state.get("addons", {}).get(addon_name, {})
            
            if addon_config != state_addon.get("config", {}):
                changes["addons"]["modified"].append({
                    "name": addon_name,
                    "old": state_addon.get("config", {}),
                    "new": addon_config,
                })

        # Check Apps
        config_apps = set(config.get("apps", {}).keys())
        state_apps = set(state.get("apps", {}).keys())

        changes["apps"]["added"] = list(config_apps - state_apps)
        changes["apps"]["removed"] = list(state_apps - config_apps)

        # Check for modified apps
        for app_name in config_apps & state_apps:
            config_app = config["apps"][app_name]
            state_app = state["apps"][app_name]

            if self._app_changed(config_app, state_app):
                changes["apps"]["modified"].append({
                    "name": app_name,
                    "old": state_app,
                    "new": config_app,
                })

        # Check if secrets file changed
        secrets_path = self.project_root / "projects" / self.project_name / "secrets.yml"
        if secrets_path.exists():
            import hashlib
            with open(secrets_path, 'rb') as f:
                current_hash = hashlib.md5(f.read()).hexdigest()
            
            last_sync_hash = state.get("last_sync_hash")
            if current_hash != last_sync_hash:
                changes["needs_sync"] = True

        # Determine what actions are needed
        if changes["vms"]["added"] or changes["vms"]["removed"] or changes["vms"]["modified"]:
            changes["needs_terraform"] = True
            changes["has_changes"] = True
            changes["total_changes"] += len(changes["vms"]["added"]) + len(changes["vms"]["removed"]) + len(changes["vms"]["modified"])

        if changes["addons"]["added"] or changes["addons"]["removed"] or changes["addons"]["modified"]:
            changes["needs_ansible"] = True
            changes["has_changes"] = True
            changes["total_changes"] += len(changes["addons"]["added"]) + len(changes["addons"]["removed"]) + len(changes["addons"]["modified"])

        if changes["apps"]["added"] or changes["apps"]["removed"] or changes["apps"]["modified"]:
            changes["needs_generate"] = True
            changes["needs_ansible"] = True
            changes["has_changes"] = True
            changes["total_changes"] += len(changes["apps"]["added"]) + len(changes["apps"]["removed"]) + len(changes["apps"]["modified"])

        if changes["needs_sync"]:
            changes["has_changes"] = True
            changes["total_changes"] += 1

        return changes

    def _vm_changed(self, config_vm: dict, state_vm: dict) -> bool:
        """Check if VM configuration changed."""
        keys_to_compare = ["machine_type", "disk_size", "services"]
        for key in keys_to_compare:
            if config_vm.get(key) != state_vm.get(key):
                return True
        return False

    def _app_changed(self, config_app: dict, state_app: dict) -> bool:
        """Check if app configuration changed."""
        keys_to_compare = ["path", "vm", "port", "domain"]
        for key in keys_to_compare:
            if config_app.get(key) != state_app.get(key):
                return True
        return False

    def _get_enabled_addons(self, config: dict) -> set:
        """Get list of enabled addons from config."""
        enabled = set()
        addons_config = config.get("addons", {})
        
        for addon_name, addon_conf in addons_config.items():
            if addon_conf and addon_conf.get("enabled", True):
                enabled.add(addon_name)
        
        return enabled

    def _display_changes(self, changes: dict, config: dict, state: dict, has_state: bool):
        """Display detected changes in a beautiful format."""
        self.console.print()

        # VMs
        if changes["vms"]["added"] or changes["vms"]["removed"] or changes["vms"]["modified"]:
            self.console.print("━" * 70)
            self.console.print("[bold cyan]🖥️  VIRTUAL MACHINES[/bold cyan]")
            self.console.print("━" * 70)
            self.console.print()

            # Show unchanged VMs
            if has_state:
                unchanged_vms = set(config.get("vms", {}).keys()) & set(state.get("vms", {}).keys())
                unchanged_vms = unchanged_vms - set(c["name"] for c in changes["vms"]["modified"])
                
                for vm_name in sorted(unchanged_vms):
                    self.console.print(f"  [dim]  {vm_name} (no changes)[/dim]")
                
                if unchanged_vms:
                    self.console.print()

            # Added
            for vm_name in sorted(changes["vms"]["added"]):
                vm_config = config["vms"][vm_name]
                self.console.print(f"  [green]+ {vm_name}[/green] [dim](new VM)[/dim]")
                self.console.print(f"    • Machine: [cyan]{vm_config.get('machine_type', 'e2-small')}[/cyan]")
                self.console.print(f"    • Disk: [cyan]{vm_config.get('disk_size', 20)}GB[/cyan]")
                services = vm_config.get("services", [])
                if services:
                    self.console.print(f"    • Services: [cyan]{', '.join(services)}[/cyan]")
                self.console.print()

            # Modified
            for change in changes["vms"]["modified"]:
                vm_name = change["name"]
                old = change["old"]
                new = change["new"]

                self.console.print(f"  [yellow]~ {vm_name}[/yellow] [dim](modified)[/dim]")

                if old.get("machine_type") != new.get("machine_type"):
                    self.console.print(
                        f"    • Machine: [dim]{old.get('machine_type')}[/dim] → [yellow]{new.get('machine_type')}[/yellow]"
                    )

                if old.get("disk_size") != new.get("disk_size"):
                    self.console.print(
                        f"    • Disk: [dim]{old.get('disk_size')}GB[/dim] → [yellow]{new.get('disk_size')}GB[/yellow]"
                    )

                old_services = set(old.get("services", []))
                new_services = set(new.get("services", []))

                if old_services != new_services:
                    added = new_services - old_services
                    removed = old_services - new_services
                    
                    if added:
                        self.console.print(f"    • Services added: [green]{', '.join(added)}[/green]")
                    if removed:
                        self.console.print(f"    • Services removed: [red]{', '.join(removed)}[/red]")

                self.console.print()

            # Removed
            for vm_name in sorted(changes["vms"]["removed"]):
                self.console.print(f"  [red]- {vm_name}[/red] [dim](will be destroyed)[/dim]")
                self.console.print()

        # Addons
        if changes["addons"]["added"] or changes["addons"]["removed"] or changes["addons"]["modified"]:
            self.console.print("━" * 70)
            self.console.print("[bold cyan]🔌 INFRASTRUCTURE ADDONS[/bold cyan]")
            self.console.print("━" * 70)
            self.console.print()

            # Show unchanged
            if has_state:
                unchanged = (self._get_enabled_addons(config) & set(state.get("addons", {}).keys())) - set(c["name"] for c in changes["addons"]["modified"])
                for addon_name in sorted(unchanged):
                    self.console.print(f"  [dim]  {addon_name} (no changes)[/dim]")
                if unchanged:
                    self.console.print()

            # Added
            for addon_name in sorted(changes["addons"]["added"]):
                self.console.print(f"  [green]+ {addon_name}[/green] [dim](will be installed)[/dim]")

            # Modified
            for change in changes["addons"]["modified"]:
                addon_name = change["name"]
                self.console.print(f"  [yellow]~ {addon_name}[/yellow] [dim](configuration changed)[/dim]")

            # Removed
            for addon_name in sorted(changes["addons"]["removed"]):
                self.console.print(f"  [red]- {addon_name}[/red] [dim](will be removed)[/dim]")

            self.console.print()

        # Apps
        if changes["apps"]["added"] or changes["apps"]["removed"] or changes["apps"]["modified"]:
            self.console.print("━" * 70)
            self.console.print("[bold cyan]📦 APPLICATIONS[/bold cyan]")
            self.console.print("━" * 70)
            self.console.print()

            # Show unchanged
            if has_state:
                unchanged = (set(config.get("apps", {}).keys()) & set(state.get("apps", {}).keys())) - set(c["name"] for c in changes["apps"]["modified"])
                for app_name in sorted(unchanged):
                    self.console.print(f"  [dim]  {app_name} (no changes)[/dim]")
                if unchanged:
                    self.console.print()

            # Added
            for app_name in sorted(changes["apps"]["added"]):
                app_config = config["apps"][app_name]
                self.console.print(f"  [green]+ {app_name}[/green] [dim](new app)[/dim]")
                self.console.print(f"    • VM: [cyan]{app_config.get('vm')}[/cyan]")
                self.console.print(f"    • Port: [cyan]{app_config.get('port')}[/cyan]")
                if app_config.get('domain'):
                    self.console.print(f"    • Domain: [cyan]{app_config.get('domain')}[/cyan]")
                self.console.print(f"    • GitHub workflow will be generated")
                self.console.print()

            # Modified
            for change in changes["apps"]["modified"]:
                app_name = change["name"]
                old = change["old"]
                new = change["new"]

                self.console.print(f"  [yellow]~ {app_name}[/yellow] [dim](modified)[/dim]")

                if old.get("vm") != new.get("vm"):
                    self.console.print(f"    • VM: [dim]{old.get('vm')}[/dim] → [yellow]{new.get('vm')}[/yellow]")

                if old.get("port") != new.get("port"):
                    self.console.print(f"    • Port: [dim]{old.get('port')}[/dim] → [yellow]{new.get('port')}[/yellow]")

                if old.get("domain") != new.get("domain"):
                    self.console.print(f"    • Domain: [dim]{old.get('domain') or 'none'}[/dim] → [yellow]{new.get('domain') or 'none'}[/yellow]")

                self.console.print(f"    • GitHub workflow will be regenerated")
                self.console.print()

            # Removed
            for app_name in sorted(changes["apps"]["removed"]):
                self.console.print(f"  [red]- {app_name}[/red] [dim](removed from config)[/dim]")
                self.console.print()

        # Impact Analysis
        self.console.print("━" * 70)
        self.console.print("[bold cyan]📊 IMPACT ANALYSIS[/bold cyan]")
        self.console.print("━" * 70)
        self.console.print()

        impact = []

        if changes["needs_terraform"]:
            impact.append("• [yellow]Terraform[/yellow] will provision/modify infrastructure")
            if changes["vms"]["modified"]:
                impact.append("  [yellow]⚠  VM modifications may require brief downtime[/yellow]")
            if changes["vms"]["removed"]:
                impact.append("  [red]⚠  VMs will be destroyed (data loss!)[/red]")

        if changes["needs_ansible"]:
            impact.append("• [cyan]Ansible[/cyan] will configure services and deploy apps")

        if changes["needs_generate"]:
            impact.append("• [blue]GitHub workflows[/blue] will be generated/updated")

        if changes["needs_sync"]:
            impact.append("• [magenta]Secrets[/magenta] will be synced to GitHub")

        if not impact:
            impact.append("• [dim]No infrastructure changes required[/dim]")

        for item in impact:
            self.console.print(f"  {item}")

        self.console.print()

        # Downtime estimation
        if changes["vms"]["modified"]:
            self.console.print("  [bold]Estimated downtime:[/bold] [yellow]2-3 minutes[/yellow] (VM restart)")
        elif changes["vms"]["added"]:
            self.console.print("  [bold]Estimated time:[/bold] [cyan]3-5 minutes[/cyan] (VM creation)")
        elif changes["needs_ansible"]:
            self.console.print("  [bold]Estimated time:[/bold] [cyan]1-2 minutes[/cyan] (service configuration)")
        else:
            self.console.print("  [bold]Downtime:[/bold] [green]None[/green]")

        self.console.print()


@click.command()
@click.option("--detailed", is_flag=True, help="Show detailed diff (future feature)")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
def plan(project, detailed, json_output, verbose):
    """
    Show deployment plan - what changes will be applied
    
    Like 'terraform plan', this command analyzes your config.yml
    and compares it with the current deployed state to show:
    - What will be created (VMs, addons, apps)
    - What will be modified
    - What will be destroyed
    - Estimated impact and downtime
    
    Examples:
        superdeploy cheapa:plan                # Show what will change
        superdeploy cheapa:plan --detailed     # Detailed diff (future)
        superdeploy cheapa:plan --json         # JSON output for CI/CD
    """
    
    if json_output:
        # TODO: Implement JSON output
        console = Console()
        console.print("[yellow]JSON output not yet implemented[/yellow]")
        return
    
    cmd = PlanCommand(project, detailed=detailed, verbose=verbose)
    cmd.run()
