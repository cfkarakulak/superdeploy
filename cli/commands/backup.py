"""SuperDeploy CLI - Backup command"""

import click
from datetime import datetime
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from cli.ui_components import show_header
from cli.utils import ssh_command

console = Console()


@click.command(name="backups:create")
@click.option("--output", "-o", help="Backup output path (default: ./backups/)")
def backups_create(project, output):
    """
    Backup project database and configurations

    \b
    Examples:
      superdeploy backups:create -p acme                    # Backup to ./backups/
      superdeploy backups:create -p acme -o /tmp/backup     # Custom output path

    \b
    This command backs up:
    - PostgreSQL database dump
    - Project configuration files
    - Environment variables (encrypted)
    - Docker compose files
    """
    # Load state to get VM IPs
    from cli.utils import get_project_root
    from cli.state_manager import StateManager

    project_root = get_project_root()
    state_mgr = StateManager(project_root, project)
    state = state_mgr.load_state()

    if not state or "vms" not in state:
        console.print("[red]✗[/red] No deployment state found")
        console.print(f"Run: [red]superdeploy {project}:up[/red]")
        raise SystemExit(1)

    # Build env dict from state for compatibility
    env = {}
    for vm_name, vm_data in state.get("vms", {}).items():
        if "external_ip" in vm_data:
            env_key = vm_name.upper().replace("-", "_")
            env[f"{env_key}_EXTERNAL_IP"] = vm_data["external_ip"]

    # Default output path
    if not output:
        output = f"./backups/{project}"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{project}_{timestamp}"

    show_header(
        title="Backup Project",
        project=project,
        details={"Output": f"{output}/{backup_name}"},
        console=console,
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Step 1: Create backup directory
        task1 = progress.add_task("[cyan]Creating backup directory...", total=1)

        import os

        os.makedirs(f"{output}/{backup_name}", exist_ok=True)

        progress.advance(task1)
        console.print(f"[green]✓[/green] Directory created: {output}/{backup_name}")

        # Step 2: Backup PostgreSQL database
        task2 = progress.add_task("[cyan]Backing up database...", total=1)

        try:
            # Get database credentials from secrets.yml
            from cli.utils import get_project_path, get_project_root
            from cli.secret_manager import SecretManager

            project_root = get_project_root()
            project_path = get_project_path(project)

            # Load secrets from secrets.yml
            secret_mgr = SecretManager(project_root, project)
            secrets_data = secret_mgr.load_secrets()
            passwords = secrets_data.get("secrets", {}).get("shared", {})

            # Dump database via SSH - dynamically find database addon
            from cli.core.config_loader import ConfigLoader
            from cli.core.addon_loader import AddonLoader
            from cli.utils import get_project_root

            project_root = get_project_root()
            projects_dir = project_root / "projects"
            config_loader = ConfigLoader(projects_dir)
            project_config = config_loader.load_project(project)

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
                        db_user = addon_config.get("user", f"{project}_user")
                        db_name = addon_config.get("database", f"{project}_db")
                        db_cmd = f"docker exec {project}-{addon_name} pg_dump -U {db_user} {db_name}"
                    elif addon_name == "mongodb":
                        db_name = addon_config.get("database", f"{project}_db")
                        db_cmd = f"docker exec {project}-{addon_name} mongodump --db {db_name} --archive"
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
            with open(f"{output}/{backup_name}/database.sql", "w") as f:
                f.write(db_dump)

            progress.advance(task2)
            console.print("[green]✓[/green] Database backed up")

        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Database backup failed: {e}")

        # Step 3: Backup configuration files
        task3 = progress.add_task("[cyan]Backing up configs...", total=1)

        try:
            import shutil

            project_path = get_project_path(project)

            # Copy config files
            shutil.copy(project_path / "project.yml", f"{output}/{backup_name}/")

            if (project_path / "secrets.yml").exists():
                shutil.copy(project_path / "secrets.yml", f"{output}/{backup_name}/")

            # Copy compose files
            compose_dir = project_path / "compose"
            if compose_dir.exists():
                shutil.copytree(compose_dir, f"{output}/{backup_name}/compose")

            progress.advance(task3)
            console.print("[green]✓[/green] Configs backed up")

        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Config backup failed: {e}")

        # Step 4: Create backup manifest
        task4 = progress.add_task("[cyan]Creating manifest...", total=1)

        manifest = {
            "project": project,
            "timestamp": timestamp,
            "backup_date": datetime.now().isoformat(),
            "files": [
                "database.sql",
                "project.yml",
                "secrets.yml",
                "compose/",
            ],
        }

        import json

        with open(f"{output}/{backup_name}/manifest.json", "w") as f:
            json.dump(manifest, f, indent=2)

        progress.advance(task4)
        console.print("[green]✓[/green] Manifest created")

    console.print("\n[color(248)]Backup complete.[/color(248)]")
    console.print(f"\n[white]Backup location:[/white] {output}/{backup_name}")
    console.print(
        f"[white]Restore with:[/white] superdeploy restore -p {project} --from {backup_name}"
    )
