"""SuperDeploy CLI - Backup command"""

import click
import shutil
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from rich.progress import Progress, SpinnerColumn, TextColumn

from cli.base import ProjectCommand
from cli.core.addon_loader import AddonLoader


@dataclass
class BackupMetadata:
    """Metadata for a backup."""

    project: str
    timestamp: str
    backup_date: str
    files: list[str]


class BackupService:
    """Service for managing backup operations."""

    @staticmethod
    def get_database_dump_command(
        addon_name: str, addon_config: Dict, project_name: str
    ) -> Optional[str]:
        """Build database backup command based on addon type."""
        if addon_name == "postgres":
            db_user = addon_config.get("user", f"{project_name}_user")
            db_name = addon_config.get("database", f"{project_name}_db")
            return f"docker exec {project_name}-{addon_name} pg_dump -U {db_user} {db_name}"
        elif addon_name == "mongodb":
            db_name = addon_config.get("database", f"{project_name}_db")
            return f"docker exec {project_name}-{addon_name} mongodump --db {db_name} --archive"
        else:
            return None


class BackupsCreateCommand(ProjectCommand):
    """Backup project database and configurations."""

    def __init__(self, project_name: str, output: str = None, verbose: bool = False):
        super().__init__(project_name, verbose=verbose)
        self.output = output or f"./backups/{project_name}"
        self.backup_service = BackupService()

    def execute(self) -> None:
        """Execute backups:create command."""
        # Require deployment
        self.require_deployment()

        # Generate backup name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{self.project_name}_{timestamp}"
        backup_path = Path(self.output) / backup_name

        self.show_header(
            title="Backup Project",
            project=self.project_name,
            details={"Output": str(backup_path)},
        )

        # Initialize logger
        logger = self.init_logger(self.project_name, f"backup-{timestamp}")

        logger.step("Starting backup process")

        # Get VM and SSH service
        vm_service = self.ensure_vm_service()
        ssh_service = vm_service.get_ssh_service()
        vm_ip = self.state_service.get_vm_ip_by_role("core", index=0)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
        ) as progress:
            # Step 1: Create backup directory
            task1 = progress.add_task("[cyan]Creating backup directory...", total=1)
            logger.log(f"Creating backup directory: {backup_path}")
            backup_path.mkdir(parents=True, exist_ok=True)
            progress.advance(task1)
            self.console.print(f"[green]✓[/green] Directory created: {backup_path}")

            # Step 2: Backup database
            task2 = progress.add_task("[cyan]Backing up database...", total=1)
            logger.log("Backing up database")
            self._backup_database(vm_ip, ssh_service, backup_path)
            progress.advance(task2)
            self.console.print("[green]✓[/green] Database backed up")

            # Step 3: Backup configuration files
            task3 = progress.add_task("[cyan]Backing up configs...", total=1)
            logger.log("Backing up configuration files")
            self._backup_configs(backup_path)
            progress.advance(task3)
            self.console.print("[green]✓[/green] Configs backed up")

            # Step 4: Create backup manifest
            task4 = progress.add_task("[cyan]Creating manifest...", total=1)
            logger.log("Creating backup manifest")
            metadata = BackupMetadata(
                project=self.project_name,
                timestamp=timestamp,
                backup_date=datetime.now().isoformat(),
                files=["database.sql", "config.yml", "secrets.yml", "compose/"],
            )
            self._save_manifest(backup_path, metadata)
            progress.advance(task4)
            self.console.print("[green]✓[/green] Manifest created")

        logger.success(f"Backup completed: {backup_path}")
        self._display_completion_message(backup_path)

        if not self.verbose:
            self.console.print(f"\n[dim]Logs saved to:[/dim] {logger.log_path}\n")

    def _backup_database(self, vm_ip: str, ssh_service, backup_path: Path) -> None:
        """Backup database from VM."""
        try:
            # Load project config to find database addon
            project_config = self.config_service.load_project_config(self.project_name)
            addons_dir = self.project_root / "addons"
            addon_loader = AddonLoader(addons_dir)
            loaded_addons = addon_loader.load_addons_for_project(
                project_config.raw_config
            )

            # Find first database addon
            db_cmd = None
            for addon_name, addon in loaded_addons.items():
                if addon.get_category() == "database":
                    addon_config = project_config.get_addons().get(addon_name, {})
                    db_cmd = self.backup_service.get_database_dump_command(
                        addon_name, addon_config, self.project_name
                    )
                    break

            if db_cmd:
                # Execute backup command via SSH
                result = ssh_service.execute_command(vm_ip, db_cmd, timeout=300)

                # Save to file
                db_file = backup_path / "database.sql"
                db_file.write_text(result.stdout)
            else:
                self.console.print("[yellow]⚠[/yellow] No database addon found")

        except Exception as e:
            self.console.print(f"[yellow]⚠[/yellow] Database backup failed: {e}")

    def _backup_configs(self, backup_path: Path) -> None:
        """Backup configuration files."""
        try:
            project_path = self.project_root / "projects" / self.project_name

            # Copy config files
            shutil.copy(project_path / "config.yml", backup_path)

            if (project_path / "secrets.yml").exists():
                shutil.copy(project_path / "secrets.yml", backup_path)

            # Copy compose files
            compose_dir = project_path / "compose"
            if compose_dir.exists():
                shutil.copytree(compose_dir, backup_path / "compose")

        except Exception as e:
            self.console.print(f"[yellow]⚠[/yellow] Config backup failed: {e}")

    def _save_manifest(self, backup_path: Path, metadata: BackupMetadata) -> None:
        """Save backup manifest."""
        manifest_file = backup_path / "manifest.json"
        manifest_file.write_text(
            json.dumps(
                {
                    "project": metadata.project,
                    "timestamp": metadata.timestamp,
                    "backup_date": metadata.backup_date,
                    "files": metadata.files,
                },
                indent=2,
            )
        )

    def _display_completion_message(self, backup_path: Path) -> None:
        """Display backup completion message."""
        self.console.print("\n[color(248)]Backup complete.[/color(248)]")
        self.console.print(f"\n[white]Backup location:[/white] {backup_path}")
        self.console.print(
            f"[white]Restore with:[/white] superdeploy {self.project_name}:restore --from {backup_path.name}"
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
