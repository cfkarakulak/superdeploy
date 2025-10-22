"""SuperDeploy CLI - Sync Repository Secrets (Project-Agnostic)"""

import click
import subprocess
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from dotenv import dotenv_values
import yaml

console = Console()


@click.command()
@click.option(
    "--env",
    "-e",
    "env_mappings",
    multiple=True,
    required=True,
    help="Env file to repo mapping: path/to/.env:owner/repo OR just path/to/.env",
)
@click.option(
    "--core-secrets",
    "-c",
    help="YAML file with core secrets (e.g., DB passwords) - these take precedence",
)
@click.option(
    "--output-dir",
    "-o",
    help="Directory to write merged secrets files (for debugging)",
)
def sync_repos(env_mappings, core_secrets, output_dir):
    """
    Sync secrets to GitHub repositories (100% project-agnostic)
    
    This command is COMPLETELY generic - no hardcoded projects, services, or secrets!
    
    \b
    Usage Examples:
      # Single repo
      superdeploy sync:repos -e ~/api/.env:myorg/api
      
      # Multiple repos
      superdeploy sync:repos \\
        -e ~/api/.env:myorg/api \\
        -e ~/dashboard/.env:myorg/dashboard
      
      # With core secrets (DB/Queue/Cache passwords)
      superdeploy sync:repos \\
        -e ~/api/.env:myorg/api \\
        -c ~/superdeploy/projects/myproject/.passwords.yml
      
      # Auto-detect repo from directory name
      superdeploy sync:repos -e ~/app-repos/api/.env
      # → Syncs to: {GITHUB_ORG}/api
    
    \b
    Core Secrets File Format (.passwords.yml):
      passwords:
        POSTGRES_PASSWORD: xxx
        RABBITMQ_PASSWORD: yyy
        REDIS_PASSWORD: zzz
        # Any other secrets...
    
    \b
    How It Works:
      1. Load app .env file
      2. Load core secrets (if provided)
      3. Merge: core secrets OVERRIDE app secrets
      4. Sync to GitHub
    
    \b
    NO HARDCODED:
      ✗ No hardcoded project names
      ✗ No hardcoded service names
      ✗ No hardcoded secret keys
      ✗ No hardcoded paths
      ✗ No assumptions about your stack!
    """
    from cli.utils import load_env

    console.print(
        Panel.fit(
            "[bold cyan]🔄 Repository Secrets Sync[/bold cyan]\n\n"
            "[white]Syncing secrets to GitHub repositories...[/white]",
            border_style="cyan",
        )
    )

    # Load infrastructure env for GitHub org (optional)
    try:
        infra_env = load_env()
        default_github_org = infra_env.get("GITHUB_ORG")
    except:
        default_github_org = None

    # Parse env mappings
    env_to_repo = {}
    for mapping in env_mappings:
        if ":" in mapping:
            # Explicit mapping: path:owner/repo
            env_path, repo = mapping.split(":", 1)
            env_path = Path(env_path).expanduser().resolve()
            env_to_repo[env_path] = repo
        else:
            # Auto-detect repo from directory name
            env_path = Path(mapping).expanduser().resolve()
            repo_name = env_path.parent.name
            
            if default_github_org:
                repo = f"{default_github_org}/{repo_name}"
            else:
                console.print(
                    f"[red]❌ Cannot auto-detect repo for {env_path}[/red]"
                )
                console.print(
                    "[yellow]Hint: Either set GITHUB_ORG in .env or use explicit mapping: path:owner/repo[/yellow]"
                )
                raise SystemExit(1)
            
            env_to_repo[env_path] = repo

    # Validate all env files exist
    for env_path in env_to_repo.keys():
        if not env_path.exists():
            console.print(f"[red]❌ Env file not found: {env_path}[/red]")
            raise SystemExit(1)

    # Load core secrets if provided
    core_secrets_dict = {}
    if core_secrets:
        core_secrets_path = Path(core_secrets).expanduser().resolve()
        if not core_secrets_path.exists():
            console.print(f"[red]❌ Core secrets file not found: {core_secrets_path}[/red]")
            raise SystemExit(1)
        
        try:
            with open(core_secrets_path) as f:
                core_data = yaml.safe_load(f)
                # Support both flat and nested format
                if "passwords" in core_data:
                    core_secrets_dict = core_data["passwords"]
                else:
                    core_secrets_dict = core_data
            
            console.print(f"\n[cyan]📦 Core secrets loaded from:[/cyan]")
            console.print(f"  {core_secrets_path}")
            console.print(f"  [dim]Found {len(core_secrets_dict)} core secrets[/dim]")
        except Exception as e:
            console.print(f"[red]❌ Error loading core secrets: {e}[/red]")
            raise SystemExit(1)

    # Setup output directory for merged files
    if output_dir:
        output_path = Path(output_dir).expanduser().resolve()
        output_path.mkdir(parents=True, exist_ok=True)
    else:
        output_path = None

    # Sync each env file to its repo
    console.print(f"\n[cyan]📦 Target repositories:[/cyan]")
    for env_path, repo in env_to_repo.items():
        console.print(f"  • {env_path.name} → {repo}")

    console.print("\n[cyan]🔄 Syncing secrets...[/cyan]")

    for env_path, repo in env_to_repo.items():
        console.print(f"\n  [bold]{repo}[/bold]")

        # Load app env
        try:
            app_env = dotenv_values(env_path)
            console.print(f"    [dim]📄 Loaded {len(app_env)} vars from {env_path.name}[/dim]")
        except Exception as e:
            console.print(f"    [red]✗[/red] Failed to load env: {e}")
            continue

        # Merge: app env first, then core secrets override
        final_secrets = {}
        
        # Add app env vars
        for key, value in app_env.items():
            if value and not value.startswith("#"):
                final_secrets[key] = value
        
        # Override with core secrets (they take precedence)
        if core_secrets_dict:
            overridden = []
            for key, value in core_secrets_dict.items():
                if key in final_secrets:
                    overridden.append(key)
                final_secrets[key] = value
            
            if overridden:
                console.print(f"    [dim]🔄 Overridden {len(overridden)} keys with core secrets[/dim]")

        # Write merged secrets to file (for debugging)
        if output_path:
            merged_file = output_path / f".merged-{env_path.stem}.yml"
            try:
                with open(merged_file, "w") as f:
                    yaml.dump(
                        {
                            "repo": repo,
                            "merged_at": datetime.now().isoformat(),
                            "source_env": str(env_path),
                            "core_secrets_used": bool(core_secrets_dict),
                            "secrets": {k: v for k, v in final_secrets.items() if v},
                        },
                        f,
                        default_flow_style=False,
                    )
                console.print(f"    [dim]📝 Merged secrets: {merged_file}[/dim]")
            except Exception as e:
                console.print(f"    [yellow]⚠[/yellow] Could not write merged file: {e}")

        # Sync all secrets
        console.print(f"    [cyan]Syncing {len(final_secrets)} secrets...[/cyan]")
        synced_count = 0
        
        for key, value in final_secrets.items():
            if value is None or value == "":
                console.print(f"      [yellow]⚠[/yellow] {key}: empty value")
                continue

            try:
                subprocess.run(
                    ["gh", "secret", "set", key, "-b", str(value), "-R", repo],
                    check=True,
                    capture_output=True,
                )
                console.print(f"      [green]✓[/green] {key}")
                synced_count += 1
            except subprocess.CalledProcessError as e:
                error_msg = e.stderr.decode() if e.stderr else str(e)
                console.print(f"      [red]✗[/red] {key}: {error_msg}")
            except Exception as e:
                console.print(f"      [red]✗[/red] {key}: {e}")

        console.print(
            f"    [green]✓[/green] Synced {synced_count}/{len(final_secrets)} secrets"
        )

    console.print("\n[green]✅ All secrets synced![/green]")
