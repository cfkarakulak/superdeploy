"""SuperDeploy CLI - Releases and Rollback commands"""

import click
import json
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm
from superdeploy_cli.utils import load_env, validate_env_vars, ssh_command

console = Console()


@click.command()
@click.option("-a", "--app", required=True, help="App name (api, dashboard, services)")
@click.option("-n", "--limit", default=10, help="Number of releases to show")
def releases(app, limit):
    """
    Show release history for an app

    \b
    Examples:
      superdeploy releases -a api          # Last 10 releases
      superdeploy releases -a api -n 20    # Last 20 releases

    \b
    Release info includes:
    - Version number
    - Git SHA
    - Deployed timestamp
    - Image tag
    - Status
    """
    env_vars = load_env()

    # Validate required vars
    required = ["CORE_EXTERNAL_IP", "SSH_KEY_PATH", "SSH_USER"]
    if not validate_env_vars(env_vars, required):
        raise SystemExit(1)

    console.print(f"[cyan]📋 Fetching release history for [bold]{app}[/bold]...[/cyan]")

    # SSH command to get container labels and history
    ssh_host = env_vars["CORE_EXTERNAL_IP"]
    ssh_user = env_vars.get("SSH_USER", "superdeploy")
    ssh_key = env_vars["SSH_KEY_PATH"]

    # Get current running container info (use docker inspect --format instead of jq)
    inspect_cmd = f"docker inspect superdeploy-{app} 2>/dev/null || echo 'NOT_FOUND'"

    try:
        current_info = ssh_command(
            host=ssh_host, user=ssh_user, key_path=ssh_key, cmd=inspect_cmd
        )

        # Parse JSON (docker inspect returns array)
        if current_info.strip() == "NOT_FOUND":
            current_data = None
        else:
            try:
                inspect_result = json.loads(current_info)
                current_data = inspect_result[0] if inspect_result else None
            except (json.JSONDecodeError, IndexError):
                current_data = None

        # Get release history from Forgejo (via labels or API)
        # For now, show current running version
        table = Table(title=f"Release History - {app.upper()}", show_header=True)
        table.add_column("Version", style="cyan", no_wrap=True)
        table.add_column("Git SHA", style="green")
        table.add_column("Deployed At", style="dim")
        table.add_column("Image", style="yellow")
        table.add_column("Status", style="bold")

        if current_data:
            config = current_data.get("Config", {})
            labels = config.get("Labels", {})
            image = config.get("Image", "unknown")
            created = current_data.get("Created", "unknown")[:19].replace("T", " ")

            # Extract release info from labels
            version = labels.get("com.superdeploy.release", "current")
            git_sha = labels.get("com.superdeploy.git.sha", "unknown")
            if git_sha and git_sha != "unknown" and len(git_sha) > 7:
                git_sha = git_sha[:7]
            deployed_at = labels.get("com.superdeploy.deployed.at", created)

            # Extract image tag
            image_tag = image.split(":")[-1] if ":" in image else "latest"

            table.add_row(version, git_sha, deployed_at, image_tag, "✅ RUNNING")
        else:
            table.add_row("N/A", "N/A", "N/A", "N/A", "❌ NOT DEPLOYED")

        console.print("\n")
        console.print(table)

        # Show rollback hint
        if current_data:
            console.print(
                f"\n[dim]💡 To rollback: [bold]superdeploy rollback -a {app} <sha>[/bold][/dim]"
            )

    except Exception as e:
        console.print(f"[red]❌ Failed to fetch releases: {e}[/red]")
        raise SystemExit(1)


@click.command()
@click.option("-a", "--app", required=True, help="App name")
@click.argument("target")
@click.option("--force", is_flag=True, help="Skip confirmation")
def rollback(app, target, force):
    """
    Rollback to a previous release

    \b
    Examples:
      superdeploy rollback -a api abc1234      # Rollback to SHA
      superdeploy rollback -a api v41          # Rollback to version
      superdeploy rollback -a api latest       # Rollback to latest

    \b
    Note: This triggers a redeployment with the specified image tag
    """
    env_vars = load_env()

    # Validate required vars
    required = ["CORE_EXTERNAL_IP", "FORGEJO_PAT", "FORGEJO_ORG", "REPO_SUPERDEPLOY"]
    if not validate_env_vars(env_vars, required):
        raise SystemExit(1)

    console.print(
        Panel(
            f"[yellow]⚠️  Rollback Warning[/yellow]\n\n"
            f"[white]App:[/white] {app}\n"
            f"[white]Target:[/white] {target}\n\n"
            f"[dim]This will redeploy the app with the specified version.[/dim]",
            border_style="yellow",
        )
    )

    # Confirm
    if not force:
        if not Confirm.ask("Continue with rollback?"):
            console.print("[yellow]⏹️  Rollback cancelled[/yellow]")
            raise SystemExit(0)

    # Trigger deployment via Forgejo API
    console.print("[cyan]🔄 Triggering rollback deployment...[/cyan]")

    import requests

    forgejo_url = f"http://{env_vars['CORE_EXTERNAL_IP']}:3001"
    workflow_url = f"{forgejo_url}/api/v1/repos/{env_vars['FORGEJO_ORG']}/{env_vars['REPO_SUPERDEPLOY']}/actions/workflows/deploy.yml/dispatches"

    # Build image tags JSON
    image_tags = {app: target}

    payload = {
        "ref": "master",
        "inputs": {
            "environment": "production",
            "services": app,
            "image_tags": json.dumps(image_tags),
            "migrate": "false",
        },
    }

    headers = {
        "Authorization": f"token {env_vars['FORGEJO_PAT']}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            workflow_url, json=payload, headers=headers, timeout=10
        )

        if response.status_code == 204:
            console.print("[green]✅ Rollback triggered successfully![/green]")
            console.print(
                f"\n[cyan]Monitor:[/cyan] {forgejo_url}/{env_vars['FORGEJO_ORG']}/{env_vars['REPO_SUPERDEPLOY']}/actions"
            )
        else:
            console.print(f"[red]❌ API call failed: {response.status_code}[/red]")
            console.print(f"[dim]{response.text}[/dim]")
            raise SystemExit(1)

    except requests.exceptions.RequestException as e:
        console.print(f"[red]❌ Request failed: {e}[/red]")
        raise SystemExit(1)
