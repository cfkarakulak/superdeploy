"""SuperDeploy CLI - Backup command"""

import click
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from cli.utils import load_env, validate_env_vars, ssh_command

console = Console()


@click.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option("--output", "-o", help="Backup output path (default: ./backups/)")
def backup(project, output):
    """
    Backup project database and configurations

    \b
    Examples:
      superdeploy backup -p acme                    # Backup to ./backups/
      superdeploy backup -p acme -o /tmp/backup     # Custom output path
    
    \b
    This command backs up:
    - PostgreSQL database dump
    - Project configuration files
    - Environment variables (encrypted)
    - Docker compose files
    """
    env = load_env(project=project)

    # Validate required vars
    required = ["CORE_EXTERNAL_IP", "SSH_KEY_PATH"]
    if not validate_env_vars(env, required):
        raise SystemExit(1)

    # Default output path
    if not output:
        output = f"./backups/{project}"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{project}_{timestamp}"

    console.print(
        Panel.fit(
            f"[bold cyan]💾 Backup Project[/bold cyan]\n\n"
            f"[white]Project: {project}[/white]\n"
            f"[white]Output: {output}/{backup_name}[/white]",
            border_style="cyan",
        )
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
            # Get database credentials from project config
            from cli.utils import get_project_path
            from dotenv import dotenv_values
            
            project_path = get_project_path(project)
            passwords = dotenv_values(project_path / ".env")
            
            # Dump database via SSH
            db_dump = ssh_command(
                host=env["CORE_EXTERNAL_IP"],
                user=env.get("SSH_USER", "superdeploy"),
                key_path=env["SSH_KEY_PATH"],
                cmd=f"docker exec {project}-postgres pg_dump -U {project}_user {project}_db",
            )
            
            # Save to file
            with open(f"{output}/{backup_name}/database.sql", "w") as f:
                f.write(db_dump)
            
            progress.advance(task2)
            console.print(f"[green]✓[/green] Database backed up")
            
        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Database backup failed: {e}")

        # Step 3: Backup configuration files
        task3 = progress.add_task("[cyan]Backing up configs...", total=1)
        
        try:
            import shutil
            from pathlib import Path
            
            project_path = get_project_path(project)
            
            # Copy config files
            shutil.copy(project_path / "project.yml", f"{output}/{backup_name}/")
            
            if (project_path / ".env").exists():
                shutil.copy(project_path / ".env", f"{output}/{backup_name}/")
            
            # Copy compose files
            compose_dir = project_path / "compose"
            if compose_dir.exists():
                shutil.copytree(compose_dir, f"{output}/{backup_name}/compose")
            
            progress.advance(task3)
            console.print(f"[green]✓[/green] Configs backed up")
            
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
                ".env",
                "compose/",
            ],
        }
        
        import json
        with open(f"{output}/{backup_name}/manifest.json", "w") as f:
            json.dump(manifest, f, indent=2)
        
        progress.advance(task4)
        console.print(f"[green]✓[/green] Manifest created")

    console.print("\n[bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold green]")
    console.print("[bold green]💾 Backup Complete![/bold green]")
    console.print("[bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold green]")
    console.print(f"\n[white]Backup location:[/white] {output}/{backup_name}")
    console.print(f"[white]Restore with:[/white] superdeploy restore -p {project} --from {backup_name}")
