"""SuperDeploy CLI - Deploy command"""

import click
import json
import requests
from rich.console import Console
from rich.panel import Panel
from cli.utils import load_env, validate_env_vars, get_project_root
from cli.ansible_utils import parse_project_config, generate_ansible_extra_vars

console = Console()


@click.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option("-a", "--app", help="App name (api, dashboard, services, or 'all')")
@click.option(
    "-e",
    "--env",
    "environment",
    default="production",
    type=click.Choice(["production", "staging", "development"]),
    help="Environment (production, staging, development)",
)
@click.option("-t", "--tag", help="Image tag (default: latest)")
@click.option("--migrate", is_flag=True, help="Run DB migrations")
def deploy(project, app, environment, tag, migrate):
    """
    Trigger deployment via Forgejo workflow

    \b
    Examples:
      superdeploy deploy -p cheapa -a api                    # Deploy API (production)
      superdeploy deploy -p cheapa -a api -e staging         # Deploy to staging
      superdeploy deploy -p cheapa -a api -t abc123          # Deploy specific tag
      superdeploy deploy -p cheapa -a all                    # Deploy all services
      superdeploy deploy -p cheapa -a api --migrate          # Deploy + migrate
    """
    env = load_env()

    # Validate required vars
    required = ["CORE_EXTERNAL_IP", "FORGEJO_PAT", "FORGEJO_ORG", "REPO_SUPERDEPLOY"]
    if not validate_env_vars(env, required):
        raise SystemExit(1)

    console.print(
        Panel.fit(
            f"[bold cyan]🚀 Triggering Deployment[/bold cyan]\n\n"
            f"[white]Project: {project}[/white]\n"
            f"[white]App: {app or 'all'}[/white]\n"
            f"[white]Environment: {environment}[/white]\n"
            f"[white]Tag: {tag or 'latest'}[/white]",
            border_style="cyan",
        )
    )

    # Determine services
    if app == "all" or not app:
        services = "api,dashboard,services"
    else:
        services = app

    # Build image tags JSON
    if tag:
        # Specific tag
        if "," in services:
            # All services, same tag
            image_tags = {svc: tag for svc in services.split(",")}
        else:
            # Single service
            image_tags = {services: tag}
    else:
        # Latest
        image_tags = {svc: "latest" for svc in services.split(",")}

    # Forgejo API call
    forgejo_url = f"http://{env['CORE_EXTERNAL_IP']}:3001"
    workflow_url = f"{forgejo_url}/api/v1/repos/{env['FORGEJO_ORG']}/{env['REPO_SUPERDEPLOY']}/actions/workflows/deploy.yml/dispatches"

    payload = {
        "ref": "master",
        "inputs": {
            "project": project,  # Project is mandatory now
            "environment": environment,
            "services": services,
            "image_tags": json.dumps(image_tags),
            "migrate": "true" if migrate else "false",
        },
    }

    headers = {
        "Authorization": f"token {env['FORGEJO_PAT']}",
        "Content-Type": "application/json",
    }

    # Retry logic for API calls
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(1, max_retries + 1):
        try:
            console.print(f"[cyan]📡 Calling Forgejo API... (attempt {attempt}/{max_retries})[/cyan]")

            response = requests.post(
                workflow_url, json=payload, headers=headers, timeout=10
            )

            if response.status_code == 204:
                console.print("[green]✅ Deployment triggered successfully![/green]")
                console.print(
                    f"\n[cyan]Monitor:[/cyan] {forgejo_url}/{env['FORGEJO_ORG']}/{env['REPO_SUPERDEPLOY']}/actions"
                )
                break
            else:
                console.print(f"[red]❌ API call failed: {response.status_code}[/red]")
                console.print(f"[dim]{response.text}[/dim]")
                
                if attempt < max_retries:
                    console.print(f"[yellow]⏳ Retrying in {retry_delay}s...[/yellow]")
                    import time
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    raise SystemExit(1)

        except requests.exceptions.Timeout:
            console.print(f"[yellow]⚠️  Request timeout[/yellow]")
            if attempt < max_retries:
                console.print(f"[yellow]⏳ Retrying in {retry_delay}s...[/yellow]")
                import time
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                console.print("[red]❌ Max retries exceeded[/red]")
                raise SystemExit(1)
                
        except requests.exceptions.RequestException as e:
            console.print(f"[red]❌ Request failed: {e}[/red]")
            if attempt < max_retries:
                console.print(f"[yellow]⏳ Retrying in {retry_delay}s...[/yellow]")
                import time
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                raise SystemExit(1)
