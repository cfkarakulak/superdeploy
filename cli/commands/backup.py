"""SuperDeploy CLI - Backup command"""

import click
import os
import shutil
import json
from datetime import datetime
from rich.progress import Progress, SpinnerColumn, TextColumn
from cli.base import ProjectCommand
from cli.utils import ssh_command, get_project_path


class BackupsCreateCommand(ProjectCommand):
    """Backup project database and configurations."""

    def __init__(self, project_name: str, output: str = None, verbose: bool = False):
        super().__init__(project_name, verbose=verbose)
        self.output = output

    def execute(self) -> None:
        """Execute backups:create command."""
        # Load state to get VM IPs
        state = self.state_service.load_state()

        if not state or "vms" not in state:
            self.console.print("[red]✗[/red] No deployment state found")
            self.console.print(f"Run: [red]superdeploy {self.project_name}:up[/red]")
            raise SystemExit(1)

        # Build env dict from state for compatibility
        env = {}
        for vm_name, vm_data in state.get("vms", {}).items():
            if "external_ip" in vm_data:
                env_key = vm_name.upper().replace("-", "_")
                env[f"{env_key}_EXTERNAL_IP"] = vm_data["external_ip"]

        # Default output path
        if not self.output:
            self.output = f"./backups/{self.project_name}"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{self.project_name}_{timestamp}"

        self.show_header(
            title="Backup Project",
            project=self.project_name,
            details={"Output": f"{self.output}/{backup_name}"},
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
        ) as progress:
            # Step 1: Create backup directory
            task1 = progress.add_task("[cyan]Creating backup directory...", total=1)

            os.makedirs(f"{self.output}/{backup_name}", exist_ok=True)

            progress.advance(task1)
            self.console.print(
                f"[green]✓[/green] Directory created: {self.output}/{backup_name}"
            )

            # Step 2: Backup PostgreSQL database
            task2 = progress.add_task("[cyan]Backing up database...", total=1)

            try:
                # Get database credentials from secrets.yml
                from cli.secret_manager import SecretManager
                from cli.utils import get_project_root

                project_root = get_project_root()
                project_path = get_project_path(self.project_name)

                # Load secrets from secrets.yml
                secret_mgr = SecretManager(project_root, self.project_name)
                secrets_data = secret_mgr.load_secrets()
                passwords = secrets_data.get("secrets", {}).get("shared", {})

                # Dump database via SSH - dynamically find database addon
                from cli.core.addon_loader import AddonLoader

                project_config = self.config_service.load_project(self.project_name)

                # Load addons to find database addon by category
                addons_dir = project_root / "addons"
                addon_loader = AddonLoader(addons_dir)
                loaded_addons = addon_loader.load_addons_for_project(
                    project_config.raw_config
                )

                # Find first database addon
                db_addon = None
                db_cmd = None

                for addon_name, addon in loaded_addons.items():
                    if addon.get_category() == "database":
                        db_addon = addon_name
                        addon_config = project_config.get_addons().get(addon_name, {})

                        # Build backup command based on addon name
                        if addon_name == "postgres":
                            db_user = addon_config.get(
                                "user", f"{self.project_name}_user"
                            )
                            db_name = addon_config.get(
                                "database", f"{self.project_name}_db"
                            )
                            db_cmd = f"docker exec {self.project_name}-{addon_name} pg_dump -U {db_user} {db_name}"
                        elif addon_name == "mongodb":
                            db_name = addon_config.get(
                                "database", f"{self.project_name}_db"
                            )
                            db_cmd = f"docker exec {self.project_name}-{addon_name} mongodump --db {db_name} --archive"
                        # Add more database types as needed

                        break  # Use first database addon found

                if db_cmd:
                    db_dump = ssh_command(
                        host=env["CORE_EXTERNAL_IP"],
                        user=env.get("SSH_USER", "superdeploy"),
                        key_path=env["SSH_KEY_PATH"],
                        cmd=db_cmd,
                    )

                    # Save to file
                    with open(f"{self.output}/{backup_name}/database.sql", "w") as f:
                        f.write(db_dump)

                progress.advance(task2)
                self.console.print("[green]✓[/green] Database backed up")

            except Exception as e:
                self.console.print(f"[yellow]⚠[/yellow] Database backup failed: {e}")

            # Step 3: Backup configuration files
            task3 = progress.add_task("[cyan]Backing up configs...", total=1)

            try:
                project_path = get_project_path(self.project_name)

                # Copy config files
                shutil.copy(
                    project_path / "config.yml", f"{self.output}/{backup_name}/"
                )

                if (project_path / "secrets.yml").exists():
                    shutil.copy(
                        project_path / "secrets.yml", f"{self.output}/{backup_name}/"
                    )

                # Copy compose files
                compose_dir = project_path / "compose"
                if compose_dir.exists():
                    shutil.copytree(compose_dir, f"{self.output}/{backup_name}/compose")

                progress.advance(task3)
                self.console.print("[green]✓[/green] Configs backed up")

            except Exception as e:
                self.console.print(f"[yellow]⚠[/yellow] Config backup failed: {e}")

            # Step 4: Create backup manifest
            task4 = progress.add_task("[cyan]Creating manifest...", total=1)

            manifest = {
                "project": self.project_name,
                "timestamp": timestamp,
                "backup_date": datetime.now().isoformat(),
                "files": [
                    "database.sql",
                    "config.yml",
                    "secrets.yml",
                    "compose/",
                ],
            }

            with open(f"{self.output}/{backup_name}/manifest.json", "w") as f:
                json.dump(manifest, f, indent=2)

            progress.advance(task4)
            self.console.print("[green]✓[/green] Manifest created")

        self.console.print("\n[color(248)]Backup complete.[/color(248)]")
        self.console.print(
            f"\n[white]Backup location:[/white] {self.output}/{backup_name}"
        )
        self.console.print(
            f"[white]Restore with:[/white] superdeploy {self.project_name}:restore --from {backup_name}"
        )


@click.command(name="backups:create")
@click.option("--output", "-o", help="Backup output path (default: ./backups/)")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
def backups_create(project, output, verbose):
    """
    Backup project database and configurations

    \b
    Examples:
      superdeploy cheapa:backups:create                    # Backup to ./backups/
      superdeploy cheapa:backups:create -o /tmp/backup     # Custom output path

    \b
    This command backs up:
    - PostgreSQL database dump
    - Project configuration files
    - Environment variables (encrypted)
    - Docker compose files
    """
    cmd = BackupsCreateCommand(project, output=output, verbose=verbose)
    cmd.run()
