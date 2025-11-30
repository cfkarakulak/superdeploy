"""
Addon Management Commands

Heroku-style addon management with named instances and attachments.
"""

import click
import subprocess
from rich.table import Table
from cli.base import ProjectCommand
from cli.secret_manager import SecretManager
from cli.logger import DeployLogger


class AddonsListCommand(ProjectCommand):
    """List all addon instances for project."""

    def execute(self) -> None:
        # Read addons from DATABASE (not config)
        from cli.database import get_db_session
        from sqlalchemy import text

        db = get_db_session()

        try:
            # Get unique addon instances from addon_secrets table
            result = db.execute(
                text("""
                    SELECT DISTINCT addon_type, addon_instance
                    FROM addon_secrets
                    WHERE project_name = :project_name
                    ORDER BY addon_type, addon_instance
                """),
                {"project_name": self.project_name},
            )

            addon_rows = result.fetchall()

            # Build addon instances list
            from dataclasses import dataclass

            @dataclass
            class AddonInstance:
                type: str
                name: str
                category: str
                version: str = "latest"
                plan: str = "standard"

                @property
                def full_name(self):
                    return f"{self.category}.{self.name}"

            instances = []
            seen_caddy = False  # Track if we've already added Caddy

            for row in addon_rows:
                addon_type = row[0]
                addon_name = row[1]

                # For Caddy, only show once (even if multiple instances exist)
                if addon_type == "caddy":
                    if seen_caddy:
                        continue  # Skip duplicate Caddy instances
                    seen_caddy = True

                # Map type to category
                category_map = {
                    "postgres": "databases",
                    "redis": "caches",
                    "rabbitmq": "queues",
                    "mongodb": "databases",
                    "elasticsearch": "search",
                    "caddy": "proxy",
                }
                category = category_map.get(addon_type, addon_type)

                instances.append(
                    AddonInstance(
                        type=addon_type,
                        name=addon_name,
                        category=category,
                        version="latest",
                        plan="standard",
                    )
                )

            # Get app attachments from aliases table
            result = db.execute(
                text("""
                    SELECT DISTINCT target_key, app_name
                    FROM aliases
                    WHERE project_name = :project_name
                    AND target_source = 'addon'
                    ORDER BY target_key, app_name
                """),
                {"project_name": self.project_name},
            )

            attachment_rows = result.fetchall()

            # Build attachment map: "category.name" → ["app1", "app2"]
            attachment_map = {}
            for row in attachment_rows:
                target_key = row[0]  # e.g., "postgres.primary.HOST"
                app_name = row[1]

                # Extract addon reference: "postgres.primary"
                parts = target_key.split(".")
                if len(parts) >= 2:
                    addon_type = parts[0]
                    addon_name = parts[1]

                    # Map to category
                    category_map = {
                        "postgres": "databases",
                        "redis": "caches",
                        "rabbitmq": "queues",
                        "mongodb": "databases",
                        "elasticsearch": "search",
                        "caddy": "proxy",
                    }
                    category = category_map.get(addon_type, addon_type)
                    full_name = f"{category}.{addon_name}"

                    if full_name not in attachment_map:
                        attachment_map[full_name] = []

                    if app_name not in attachment_map[full_name]:
                        attachment_map[full_name].append(app_name)

        finally:
            db.close()

        # JSON output mode
        if self.json_output:
            addons_data = []
            for instance in sorted(instances, key=lambda x: (x.category, x.name)):
                full_name = instance.full_name
                attached_apps = attachment_map.get(full_name, [])
                addons_data.append(
                    {
                        "name": full_name,
                        "type": instance.type,
                        "version": instance.version,
                        "plan": instance.plan,
                        "category": instance.category,
                        "attached_to": attached_apps if attached_apps else [],
                    }
                )

            self.output_json(
                {
                    "project": self.project_name,
                    "addons": addons_data,
                    "total": len(instances),
                }
            )
            return

        self.show_header(
            title="Addons",
            project=self.project_name,
            subtitle="Managed addon instances",
        )

        if not instances:
            self.console.print("[yellow]No addons configured[/yellow]")
            self.console.print("\n[dim]Add an addon with:[/dim]")
            self.console.print(
                f"  [cyan]superdeploy {self.project_name}:addons:add <type> --name <name>[/cyan]"
            )
            return

        # Create table
        table = Table(
            title=f"Addon Instances - {self.project_name}",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Type", style="white")
        table.add_column("Version", style="dim")
        table.add_column("Plan", style="yellow")
        table.add_column("Attached To", style="magenta")

        for instance in sorted(instances, key=lambda x: (x.category, x.name)):
            full_name = instance.full_name
            attached_apps = ", ".join(attachment_map.get(full_name, ["-"]))

            table.add_row(
                full_name, instance.type, instance.version, instance.plan, attached_apps
            )

        self.console.print(table)

        # Summary
        self.console.print(f"\n[dim]Total: {len(instances)} addon instances[/dim]")
        self.console.print(
            f"\n[dim]View details: superdeploy {self.project_name}:addons:info <addon>[/dim]"
        )


class AddonsInfoCommand(ProjectCommand):
    """Show detailed info about addon instance."""

    def __init__(
        self,
        project_name: str,
        addon: str,
        verbose: bool = False,
        json_output: bool = False,
    ):
        super().__init__(project_name, verbose=verbose, json_output=json_output)
        self.addon = addon  # e.g., "databases.primary"

    def execute(self) -> None:
        # Parse addon reference
        if "." not in self.addon:
            self.console.print("[red]Invalid addon format. Use: category.name[/red]")
            self.console.print("[dim]Example: databases.primary[/dim]")
            return

        category, instance_name = self.addon.split(".", 1)

        # Load config
        config = self.config_service.get_raw_config(self.project_name)

        # Find instance
        instance = self.config_service.get_addon_instance(
            self.project_name, category, instance_name
        )

        if not instance:
            self.console.print(f"[red]Addon not found: {self.addon}[/red]")
            self.console.print("\n[dim]Available addons:[/dim]")
            instances = self.config_service.parse_addons(config)
            for inst in instances:
                self.console.print(f"  • {inst.full_name}")
            return

        # Show header
        self.show_header(title=f"Addon Info: {self.addon}", project=self.project_name)

        # Basic info
        self.console.print("[bold]Basic Information[/bold]")
        self.console.print(f"  Name: {instance.full_name}")
        self.console.print(f"  Type: {instance.type}")
        self.console.print(f"  Version: {instance.version}")
        self.console.print(f"  Plan: {instance.plan}")

        # Credentials (from database)
        secret_mgr = SecretManager(self.project_root, self.project_name, "production")
        secrets_obj = secret_mgr.load_secrets()

        # Convert to dict if it's a SecretConfig object
        secrets = (
            secrets_obj.to_dict() if hasattr(secrets_obj, "to_dict") else secrets_obj
        )

        # Get connection details from secrets structure
        addon_secrets = (
            secrets.get("secrets", {})
            .get("addons", {})
            .get(instance.type, {})
            .get(instance_name, {})
        )

        if addon_secrets or config.get("addons", {}).get(category, {}).get(
            instance_name
        ):
            self.console.print("\n[bold]Connection Details[/bold]")

            # HOST is determined at runtime (VM IP)
            # For now, show that it will be auto-configured
            self.console.print("  Host: [dim](auto-configured on deployment)[/dim]")

            # PORT comes from config.yml
            instance_config = (
                config.get("addons", {}).get(category, {}).get(instance_name, {})
            )
            port = instance_config.get("port") or instance_config.get("http_port")
            if port:
                self.console.print(f"  Port: {port}")

            # Type-specific details
            if instance.type == "postgres":
                user = addon_secrets.get("USER")
                password = addon_secrets.get("PASSWORD")
                database = addon_secrets.get("DATABASE")

                if user:
                    # Masked password
                    masked_password = (
                        password[:4] + "***" + password[-4:] if password else "***"
                    )

                    self.console.print(f"  User: {user}")
                    self.console.print(f"  Password: {masked_password}")
                    self.console.print(f"  Database: {database}")
                    self.console.print(
                        "\n  [dim]Connection URL (use $HOST at runtime):[/dim]"
                    )
                    self.console.print(
                        f"    postgresql://{user}:{masked_password}@$HOST:{port}/{database}"
                    )

            elif instance.type == "redis":
                password = addon_secrets.get("PASSWORD", "")
                if password:
                    masked_password = (
                        password[:4] + "***" + password[-4:]
                        if len(password) > 8
                        else "***"
                    )
                    self.console.print(f"  Password: {masked_password}")
                    self.console.print(
                        "\n  [dim]Connection URL (use $HOST at runtime):[/dim]"
                    )
                    self.console.print(
                        f"    redis://default:{masked_password}@$HOST:{port}"
                    )
                else:
                    self.console.print(
                        "\n  [dim]Connection URL (use $HOST at runtime):[/dim]"
                    )
                    self.console.print(f"    redis://$HOST:{port}")

            elif instance.type == "rabbitmq":
                user = addon_secrets.get("USER")
                password = addon_secrets.get("PASSWORD")
                vhost = addon_secrets.get("VHOST", "/")

                if user:
                    masked_password = (
                        password[:4] + "***" + password[-4:] if password else "***"
                    )

                    self.console.print(f"  User: {user}")
                    self.console.print(f"  Password: {masked_password}")
                    self.console.print(f"  VHost: {vhost}")

                    # Show both AMQP and Management URLs
                    management_port = instance_config.get("management_port")
                    self.console.print(
                        "\n  [dim]Connection URLs (use $HOST at runtime):[/dim]"
                    )
                    self.console.print(
                        f"    AMQP:       amqp://{user}:{masked_password}@$HOST:{port}{vhost}"
                    )
                    if management_port:
                        self.console.print(
                            f"    Management: http://$HOST:{management_port}"
                        )

        # Attachments - check from secret_aliases table
        from cli.database import get_db_session
        from sqlalchemy import text

        db = get_db_session()
        attachments = []

        try:
            # Get all apps that have aliases pointing to this addon
            result = db.execute(
                text("""
                    SELECT DISTINCT app_name
                    FROM secret_aliases
                    WHERE project_name = :project
                    AND target_key LIKE :pattern
                """),
                {
                    "project": self.project_name,
                    "pattern": f"{instance.type}.{instance_name}.%",
                },
            )

            for row in result.fetchall():
                app_name = row[0]
                # Create a simple attachment object
                from collections import namedtuple

                Attachment = namedtuple("Attachment", ["addon", "as_", "access"])
                attachment = Attachment(
                    addon=self.addon, as_=instance.type.upper(), access="default"
                )
                attachments.append((app_name, attachment))
        finally:
            db.close()

        if attachments:
            self.console.print("\n[bold]Attached To[/bold]")
            for app_name, attachment in attachments:
                self.console.print(f"  • {app_name}")
                self.console.print(f"      As: {attachment.as_}")
                self.console.print(f"      Access: {attachment.access}")
        else:
            self.console.print("\n[yellow]⚠️  Not attached to any apps[/yellow]")
            self.console.print("\n[dim]Attach to app with:[/dim]")
            self.console.print(
                f"  [cyan]superdeploy {self.project_name}:addons:attach {self.addon} --app <app-name>[/cyan]"
            )


class AddonsAddCommand(ProjectCommand):
    """Add new addon instance to config.yml."""

    def __init__(
        self,
        project_name: str,
        addon_type: str,
        name: str,
        version: str = None,
        plan: str = "standard",
        verbose: bool = False,
        json_output: bool = False,
    ):
        super().__init__(project_name, verbose=verbose, json_output=json_output)
        self.addon_type = addon_type
        self.name = name
        self.version = version
        self.plan = plan

    def execute(self) -> None:
        self.show_header(
            title="Add Addon",
            project=self.project_name,
            subtitle=f"Adding {self.addon_type}",
        )

        # Load config
        from cli.database import get_db_session
        from sqlalchemy import Table, Column, Integer, String, JSON, MetaData

        # Determine category from type
        category_map = {
            "postgres": "databases",
            "redis": "caches",
            "rabbitmq": "queues",
            "caddy": "proxy",
            "elasticsearch": "search",
            "mongodb": "databases",
        }

        category = category_map.get(self.addon_type)
        if not category:
            self.console.print(f"[red]Unknown addon type: {self.addon_type}[/red]")
            self.console.print("\n[dim]Supported types:[/dim]")
            for type_name in category_map.keys():
                self.console.print(f"  • {type_name}")
            return

        # Default versions
        default_versions = {
            "postgres": "15-alpine",
            "redis": "7-alpine",
            "rabbitmq": "3.12-management-alpine",
            "caddy": "2-alpine",
            "elasticsearch": "8.11.0",
            "mongodb": "7.0",
        }

        version = self.version or default_versions.get(self.addon_type, "latest")

        # Determine default ports based on addon type
        port_map = {
            "postgres": {"port": 5432},
            "redis": {"port": 6379},
            "rabbitmq": {"port": 5672, "management_port": 15672},
            "mongodb": {"port": 27017},
            "elasticsearch": {"port": 9200},
            "caddy": {"http_port": 80, "https_port": 443, "admin_port": 2019},
        }

        # Add addon with port configuration
        addon_config = {
            "type": self.addon_type,
            "version": version,
            "plan": self.plan,
        }

        # Add type-specific ports
        if self.addon_type in port_map:
            addon_config.update(port_map[self.addon_type])

        addon_config["options"] = {}

        # Update database
        db = get_db_session()
        try:
            metadata = MetaData()
            projects_table = Table(
                "projects",
                metadata,
                Column("id", Integer, primary_key=True),
                Column("name", String(100)),
                Column("addons_config", JSON),
            )

            result = db.execute(
                projects_table.select().where(
                    projects_table.c.name == self.project_name
                )
            )
            row = result.fetchone()

            if not row:
                self.console.print(
                    f"[red]✗ Project '{self.project_name}' not found in database[/red]"
                )
                return

            # Check if already exists
            from cli.database import Addon as AddonModel

            existing = (
                db.query(AddonModel)
                .filter(
                    AddonModel.project_id == row.id,
                    AddonModel.category == category,
                    AddonModel.instance_name == self.name,
                )
                .first()
            )

            if existing:
                self.console.print(
                    f"[yellow]Addon already exists: {category}.{self.name}[/yellow]"
                )
                return

            # Create new addon
            new_addon = AddonModel(
                project_id=row.id,
                instance_name=self.name,
                category=category,
                type=self.addon_type,
                version=version,
                vm="core",  # Default VM
                plan=self.plan,
            )
            db.add(new_addon)
            db.commit()

            self.console.print(
                f"[green]✓[/green] Added addon: [cyan]{category}.{self.name}[/cyan]"
            )
            self.console.print(f"  Type: {self.addon_type}")
            self.console.print(f"  Version: {version}")
            self.console.print(f"  Plan: {self.plan}")

            self.console.print("\n[bold]Next steps:[/bold]")
            self.console.print(
                f"  1. Deploy: [cyan]superdeploy {self.project_name}:up --addon {category}.{self.name}[/cyan]"
            )
            self.console.print(
                f"  2. Attach: [cyan]superdeploy {self.project_name}:addons:attach {category}.{self.name} --app <app-name>[/cyan]"
            )

        finally:
            db.close()


class AddonsRemoveCommand(ProjectCommand):
    """Remove addon instance from config.yml."""

    def __init__(
        self,
        project_name: str,
        addon: str,
        verbose: bool = False,
        json_output: bool = False,
    ):
        super().__init__(project_name, verbose=verbose, json_output=json_output)
        self.addon = addon

    def execute(self) -> None:
        if "." not in self.addon:
            self.console.print("[red]Invalid addon format. Use: category.name[/red]")
            return

        category, name = self.addon.split(".", 1)

        self.show_header(
            title="Remove Addon",
            project=self.project_name,
            subtitle=f"Removing {self.addon}",
        )

        # Load from database
        from cli.database import get_db_session, Addon as AddonModel, Project
        from sqlalchemy import text

        db = get_db_session()
        try:
            # Get project
            project = (
                db.query(Project).filter(Project.name == self.project_name).first()
            )
            if not project:
                self.console.print(
                    f"[red]✗ Project '{self.project_name}' not found in database[/red]"
                )
                return

            # Check if addon exists
            addon = (
                db.query(AddonModel)
                .filter(
                    AddonModel.project_id == project.id,
                    AddonModel.category == category,
                    AddonModel.instance_name == name,
                )
                .first()
            )

            if not addon:
                self.console.print(f"[red]Addon not found: {self.addon}[/red]")
                return

            # Check if attached to any apps (via secret_aliases)
            result = db.execute(
                text("""
                    SELECT DISTINCT app_name
                    FROM secret_aliases
                    WHERE project_name = :project
                    AND target_key LIKE :pattern
                """),
                {"project": self.project_name, "pattern": f"{addon.type}.{name}.%"},
            )
            attached_apps = [row[0] for row in result.fetchall()]

            if attached_apps:
                self.console.print(
                    "[yellow]Warning: Addon is attached to apps:[/yellow]"
                )
                for app in attached_apps:
                    self.console.print(f"  • {app}")
                self.console.print(
                    "\n[dim]Detach first with:[/dim] [cyan]superdeploy PROJECT:addons:detach ADDON --app APP[/cyan]"
                )

                if not click.confirm("\nRemove anyway?"):
                    self.console.print("[yellow]Cancelled[/yellow]")
                    return

            # Remove addon from database
            db.delete(addon)
            db.commit()

            self.console.print(
                f"[green]✓[/green] Removed addon: [cyan]{self.addon}[/cyan]"
            )

            if attached_apps:
                self.console.print(
                    "\n[yellow]Note: Apps still reference this addon in their aliases![/yellow]"
                )
                self.console.print("[dim]They will fail to start until updated.[/dim]")

            self.console.print(
                f"\n[dim]Run:[/dim] [cyan]superdeploy {self.project_name}:up[/cyan] [dim]to apply changes[/dim]"
            )

        finally:
            db.close()


class AddonsAttachCommand(ProjectCommand):
    """Attach addon to app in config.yml."""

    def __init__(
        self,
        project_name: str,
        addon: str,
        app: str,
        as_var: str = None,
        access: str = "readwrite",
        verbose: bool = False,
        json_output: bool = False,
    ):
        super().__init__(project_name, verbose=verbose, json_output=json_output)
        self.addon = addon
        self.app = app
        self.as_var = as_var
        self.access = access

    def execute(self) -> None:
        if "." not in self.addon:
            self.console.print("[red]Invalid addon format. Use: category.name[/red]")
            return

        category, name = self.addon.split(".", 1)

        self.show_header(
            title="Attach Addon",
            project=self.project_name,
            subtitle=f"Attaching {self.addon} to {self.app}",
        )

        # Load from database
        from cli.database import get_db_session, Addon as AddonModel, App, Project
        from sqlalchemy import text

        db = get_db_session()
        try:
            # Get project
            project = (
                db.query(Project).filter(Project.name == self.project_name).first()
            )
            if not project:
                self.console.print(
                    f"[red]✗ Project '{self.project_name}' not found in database[/red]"
                )
                return

            # Check if addon exists
            addon = (
                db.query(AddonModel)
                .filter(
                    AddonModel.project_id == project.id,
                    AddonModel.category == category,
                    AddonModel.instance_name == name,
                )
                .first()
            )

            if not addon:
                self.console.print(f"[red]Addon not found: {self.addon}[/red]")
                return

            # Check if app exists
            app = (
                db.query(App)
                .filter(App.project_id == project.id, App.name == self.app)
                .first()
            )

            if not app:
                self.console.print(f"[red]App not found: {self.app}[/red]")
                return

            # Default as_var based on addon type
            if not self.as_var:
                as_var_map = {
                    "postgres": "DATABASE",
                    "redis": "CACHE",
                    "rabbitmq": "QUEUE",
                    "elasticsearch": "SEARCH",
                    "mongodb": "MONGO",
                }
                self.as_var = as_var_map.get(addon.type, addon.type.upper())

            # Check if already attached (via secret_aliases)
            result = db.execute(
                text("""
                    SELECT COUNT(*) FROM secret_aliases
                    WHERE project_name = :project
                    AND app_name = :app
                    AND target_key LIKE :pattern
                """),
                {
                    "project": self.project_name,
                    "app": self.app,
                    "pattern": f"{addon.type}.{name}.%",
                },
            )
            if result.fetchone()[0] > 0:
                self.console.print(
                    f"[yellow]Already attached: {self.addon} to {self.app}[/yellow]"
                )
                return

            # Create secret aliases for addon credentials
            # This creates mappings like DATABASE_HOST -> postgres.primary.HOST
            addon_keys = {
                "postgres": ["HOST", "PORT", "USER", "PASSWORD", "DATABASE"],
                "redis": ["HOST", "PORT", "PASSWORD"],
                "rabbitmq": ["HOST", "PORT", "USER", "PASSWORD", "VHOST"],
                "mongodb": ["HOST", "PORT", "USER", "PASSWORD", "DATABASE"],
                "elasticsearch": ["HOST", "PORT"],
            }

            keys = addon_keys.get(addon.type, ["HOST", "PORT"])
            for key in keys:
                alias_key = f"{self.as_var}_{key}"
                target_key = f"{addon.type}.{name}.{key}"

                db.execute(
                    text("""
                        INSERT INTO secret_aliases (project_name, app_name, alias_key, target_key, target_source)
                        VALUES (:project, :app, :alias, :target, 'addon')
                        ON CONFLICT (project_name, app_name, alias_key) DO UPDATE
                        SET target_key = :target
                    """),
                    {
                        "project": self.project_name,
                        "app": self.app,
                        "alias": alias_key,
                        "target": target_key,
                    },
                )

            db.commit()

            self.console.print(
                f"[green]✓[/green] Attached [cyan]{self.addon}[/cyan] to [cyan]{self.app}[/cyan]"
            )
            self.console.print(f"  As: {self.as_var}")
            self.console.print(f"  Access: {self.access}")

        finally:
            db.close()

        # Automatically regenerate workflows
        self.console.print("\n[bold cyan]→[/bold cyan] Regenerating workflows...")
        try:
            result = subprocess.run(
                ["superdeploy", f"{self.project_name}:generate"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                self.console.print("[green]✓[/green] Workflows regenerated")
            else:
                self.console.print(
                    f"[yellow]⚠[/yellow] Generate failed: {result.stderr}"
                )
        except Exception as e:
            self.console.print(f"[yellow]⚠[/yellow] Generate failed: {e}")

        # Automatically sync secrets
        self.console.print("[bold cyan]→[/bold cyan] Syncing secrets to GitHub...")
        try:
            result = subprocess.run(
                ["superdeploy", f"{self.project_name}:sync"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                self.console.print("[green]✓[/green] Secrets synced")
            else:
                self.console.print(f"[yellow]⚠[/yellow] Sync failed: {result.stderr}")
        except Exception as e:
            self.console.print(f"[yellow]⚠[/yellow] Sync failed: {e}")

        # Deploy app (restart to pick up new env vars)
        self.console.print(
            f"[bold cyan]→[/bold cyan] Deploying [cyan]{self.app}[/cyan] to pick up new addon..."
        )

        logger = DeployLogger(self.project_name, self.console)

        try:
            # Get app config to find which VM it's on
            app_config = config["apps"][self.app]
            vm_role = app_config.get("vm", "app")

            # Use Ansible to restart the app's containers
            ansible_cmd = [
                "ansible-playbook",
                str(self.project_root / "shared/ansible/playbooks/app-restart.yml"),
                "-e",
                f"project_name={self.project_name}",
                "-e",
                f"app_name={self.app}",
                "-e",
                f"vm_role={vm_role}",
                "--limit",
                f"{self.project_name}_{vm_role}",
            ]

            result = subprocess.run(ansible_cmd, capture_output=True, text=True)

            if result.returncode == 0:
                self.console.print(
                    f"[green]✓[/green] App [cyan]{self.app}[/cyan] restarted"
                )
                self.console.print(
                    "\n[bold green]✅ Addon attached and live![/bold green]"
                )
            else:
                self.console.print("[yellow]⚠[/yellow] App restart failed")
                self.console.print(
                    f"\n[dim]Manual restart:[/dim] [cyan]cd ~/code/{self.app} && git push origin production[/cyan]"
                )
        except Exception as e:
            self.console.print(f"[yellow]⚠[/yellow] Auto-deploy failed: {e}")
            self.console.print(
                f"\n[dim]Manual restart:[/dim] [cyan]cd ~/code/{self.app} && git push origin production[/cyan]"
            )


class AddonsDetachCommand(ProjectCommand):
    """Detach addon from app in config.yml."""

    def __init__(
        self,
        project_name: str,
        addon: str,
        app: str,
        verbose: bool = False,
        json_output: bool = False,
    ):
        super().__init__(project_name, verbose=verbose, json_output=json_output)
        self.addon = addon
        self.app = app

    def execute(self) -> None:
        if "." not in self.addon:
            self.console.print("[red]Invalid addon format. Use: category.name[/red]")
            return

        category, name = self.addon.split(".", 1)

        self.show_header(
            title="Detach Addon",
            project=self.project_name,
            subtitle=f"Detaching {self.addon} from {self.app}",
        )

        # Load from database
        from cli.database import get_db_session, Addon as AddonModel, App, Project
        from sqlalchemy import text

        db = get_db_session()
        try:
            # Get project
            project = (
                db.query(Project).filter(Project.name == self.project_name).first()
            )
            if not project:
                self.console.print(
                    f"[red]✗ Project '{self.project_name}' not found in database[/red]"
                )
                return

            # Check if app exists
            app = (
                db.query(App)
                .filter(App.project_id == project.id, App.name == self.app)
                .first()
            )

            if not app:
                self.console.print(f"[red]App not found: {self.app}[/red]")
                return

            # Check if addon exists
            addon = (
                db.query(AddonModel)
                .filter(
                    AddonModel.project_id == project.id,
                    AddonModel.category == category,
                    AddonModel.instance_name == name,
                )
                .first()
            )

            if not addon:
                self.console.print(f"[yellow]Addon not found: {self.addon}[/yellow]")
                return

            # Remove all secret aliases for this addon attachment
            result = db.execute(
                text("""
                    DELETE FROM secret_aliases
                    WHERE project_name = :project
                    AND app_name = :app
                    AND target_key LIKE :pattern
                """),
                {
                    "project": self.project_name,
                    "app": self.app,
                    "pattern": f"{addon.type}.{name}.%",
                },
            )

            if result.rowcount == 0:
                self.console.print(
                    f"[yellow]Addon not attached to {self.app}: {self.addon}[/yellow]"
                )
                return

            db.commit()

            self.console.print(
                f"[green]✓[/green] Detached [cyan]{self.addon}[/cyan] from [cyan]{self.app}[/cyan]"
            )

        finally:
            db.close()

        # Automatically regenerate workflows
        self.console.print("\n[bold cyan]→[/bold cyan] Regenerating workflows...")
        try:
            result = subprocess.run(
                ["superdeploy", f"{self.project_name}:generate"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                self.console.print("[green]✓[/green] Workflows regenerated")
            else:
                self.console.print(
                    f"[yellow]⚠[/yellow] Generate failed: {result.stderr}"
                )
        except Exception as e:
            self.console.print(f"[yellow]⚠[/yellow] Generate failed: {e}")

        # Automatically sync secrets
        self.console.print("[bold cyan]→[/bold cyan] Syncing secrets to GitHub...")
        try:
            result = subprocess.run(
                ["superdeploy", f"{self.project_name}:sync"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                self.console.print("[green]✓[/green] Secrets synced")
            else:
                self.console.print(f"[yellow]⚠[/yellow] Sync failed: {result.stderr}")
        except Exception as e:
            self.console.print(f"[yellow]⚠[/yellow] Sync failed: {e}")

        # Restart app to remove addon env vars
        self.console.print(
            f"[bold cyan]→[/bold cyan] Restarting [cyan]{self.app}[/cyan] to remove addon..."
        )

        logger = DeployLogger(self.project_name, self.console)

        try:
            # Reload config after detach
            config_path = (
                self.project_root / "projects" / self.project_name / "config.yml"
            )
            with open(config_path) as f:
                config = yaml.safe_load(f)

            # Get app config to find which VM it's on
            app_config = config["apps"][self.app]
            vm_role = app_config.get("vm", "app")

            # Use Ansible to restart the app's containers
            ansible_cmd = [
                "ansible-playbook",
                str(self.project_root / "shared/ansible/playbooks/app-restart.yml"),
                "-e",
                f"project_name={self.project_name}",
                "-e",
                f"app_name={self.app}",
                "-e",
                f"vm_role={vm_role}",
                "--limit",
                f"{self.project_name}_{vm_role}",
            ]

            result = subprocess.run(ansible_cmd, capture_output=True, text=True)

            if result.returncode == 0:
                self.console.print(
                    f"[green]✓[/green] App [cyan]{self.app}[/cyan] restarted"
                )
                self.console.print(
                    "\n[bold green]✅ Addon detached and removed![/bold green]"
                )
            else:
                self.console.print("[yellow]⚠[/yellow] App restart failed")
                self.console.print(
                    f"\n[dim]Manual restart:[/dim] [cyan]cd ~/code/{self.app} && git push origin production[/cyan]"
                )
        except Exception as e:
            self.console.print(f"[yellow]⚠[/yellow] Auto-restart failed: {e}")
            self.console.print(
                f"\n[dim]Manual restart:[/dim] [cyan]cd ~/code/{self.app} && git push origin production[/cyan]"
            )


# Click command wrappers
@click.command(name="addons:list")
@click.option("--verbose", "-v", is_flag=True)
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def addons_list(project, verbose, json_output):
    """
    List all addon instances

    Examples:
        superdeploy cheapa:addons:list
        superdeploy cheapa:addons
    """
    cmd = AddonsListCommand(project, verbose=verbose, json_output=json_output)
    cmd.run()


@click.command(name="addons:info")
@click.argument("addon")  # databases.primary
@click.option("--verbose", "-v", is_flag=True)
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def addons_info(project, addon, verbose, json_output):
    """
    Show detailed information about an addon instance

    Examples:
        superdeploy cheapa:addons:info databases.primary
        superdeploy cheapa:addons:info caches.session
    """
    cmd = AddonsInfoCommand(project, addon, verbose=verbose, json_output=json_output)
    cmd.run()


@click.command(name="addons:add")
@click.argument("addon_type")  # postgres, redis, rabbitmq, etc.
@click.option("--name", required=True, help="Instance name (e.g., 'primary', 'cache')")
@click.option("--version", help="Addon version (default: latest stable)")
@click.option("--plan", default="standard", help="Resource plan (default: standard)")
@click.option("--verbose", "-v", is_flag=True)
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def addons_add(project, addon_type, name, version, plan, verbose, json_output):
    """
    Add new addon instance to project

    Examples:
        superdeploy cheapa:addons:add postgres --name primary
        superdeploy cheapa:addons:add redis --name cache --version 7-alpine
        superdeploy cheapa:addons:add rabbitmq --name queue --plan large
    """
    cmd = AddonsAddCommand(
        project,
        addon_type,
        name,
        version,
        plan,
        verbose=verbose,
        json_output=json_output,
    )
    cmd.run()


@click.command(name="addons:remove")
@click.argument("addon")  # databases.primary
@click.option("--verbose", "-v", is_flag=True)
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def addons_remove(project, addon, verbose, json_output):
    """
    Remove addon instance from project

    Examples:
        superdeploy cheapa:addons:remove databases.primary
        superdeploy cheapa:addons:remove caches.session
    """
    cmd = AddonsRemoveCommand(project, addon, verbose=verbose, json_output=json_output)
    cmd.run()


@click.command(name="addons:attach")
@click.argument("addon")  # databases.primary
@click.option("--app", required=True, help="App name to attach to")
@click.option(
    "--as", "as_var", help="Environment variable prefix (auto-detected if not provided)"
)
@click.option(
    "--access", default="readwrite", help="Access level: readwrite or readonly"
)
@click.option("--verbose", "-v", is_flag=True)
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def addons_attach(project, addon, app, as_var, access, verbose, json_output):
    """
    Attach addon to app (adds to app's config.yml)

    Examples:
        superdeploy cheapa:addons:attach databases.primary --app api
        superdeploy cheapa:addons:attach databases.primary --app storefront --as DB --access readonly
    """
    cmd = AddonsAttachCommand(
        project, addon, app, as_var, access, verbose=verbose, json_output=json_output
    )
    cmd.run()


@click.command(name="addons:detach")
@click.argument("addon")  # databases.primary
@click.option("--app", required=True, help="App name to detach from")
@click.option("--verbose", "-v", is_flag=True)
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def addons_detach(project, addon, app, verbose, json_output):
    """
    Detach addon from app (removes from app's config.yml)

    Examples:
        superdeploy cheapa:addons:detach databases.primary --app api
    """
    cmd = AddonsDetachCommand(
        project, addon, app, verbose=verbose, json_output=json_output
    )
    cmd.run()


# Alias: addons without subcommand defaults to list
@click.command(name="addons")
@click.option("--verbose", "-v", is_flag=True)
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def addons(project, verbose, json_output):
    """
    List all addon instances (alias for addons:list)
    """
    cmd = AddonsListCommand(project, verbose=verbose, json_output=json_output)
    cmd.run()
