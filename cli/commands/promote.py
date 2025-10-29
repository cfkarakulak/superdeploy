"""SuperDeploy CLI - Promote command (staging → production)"""

import click
import requests
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from cli.utils import load_env, validate_env_vars

console = Console()


@click.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option("-a", "--app", required=True, help="App name (api, dashboard, services)")
@click.option("--from-env", default="staging", help="Source environment")
@click.option("--to-env", default="production", help="Target environment")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def promote(project, app, from_env, to_env, yes):
    """
    Promote deployment from one environment to another

    \b
    Examples:
      superdeploy promote -p acme -a api                    # staging → production
      superdeploy promote -p acme -a api --from-env dev     # dev → production
      superdeploy promote -p acme -a all -y                 # Skip confirmation
    
    \b
    This command:
    1. Gets the current image tag from source environment
    2. Deploys the same tag to target environment
    3. Ensures consistency across environments
    """
    env = load_env(project=project)

    # Validate required vars
    required = ["CORE_EXTERNAL_IP", "FORGEJO_PAT", "FORGEJO_ORG", "REPO_SUPERDEPLOY"]
    if not validate_env_vars(env, required):
        raise SystemExit(1)

    console.print(
        Panel.fit(
            f"[bold yellow]🚀 Promote Deployment[/bold yellow]\n\n"
            f"[white]Project: {project}[/white]\n"
            f"[white]App: {app}[/white]\n"
            f"[white]From: {from_env}[/white]\n"
            f"[white]To: {to_env}[/white]",
            border_style="yellow",
        )
    )

    # Get current image tag from source environment
    console.print(f"[cyan]📋 Fetching current {from_env} image...[/cyan]")
    
    try:
        # Get container info from source environment
        import subprocess
        
        container_name = f"{project}-{app}-{from_env}"
        result = subprocess.run(
            [
                "ssh",
                f"{env.get('SSH_USER', 'superdeploy')}@{env['CORE_EXTERNAL_IP']}",
                "-i",
                env["SSH_KEY_PATH"],
                f"docker inspect {container_name} --format '{{{{.Config.Image}}}}'",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        
        source_image = result.stdout.strip()
        
        if not source_image:
            console.print(f"[red]❌ No {from_env} deployment found for {app}[/red]")
            raise SystemExit(1)
        
        # Extract tag from image
        image_tag = source_image.split(":")[-1]
        
        console.print(f"[green]✓[/green] Source image: {source_image}")
        console.print(f"[green]✓[/green] Tag: {image_tag}")
        
    except subprocess.CalledProcessError as e:
        console.print(f"[red]❌ Failed to get source image: {e.stderr}[/red]")
        raise SystemExit(1)

    # Confirmation
    if not yes:
        if not Confirm.ask(
            f"\n[yellow]Promote {app} from {from_env} to {to_env}?[/yellow]"
        ):
            console.print("[dim]Cancelled.[/dim]")
            raise SystemExit(0)

    # Trigger deployment to target environment
    console.print(f"\n[cyan]🚀 Deploying to {to_env}...[/cyan]")
    
    forgejo_url = f"http://{env['CORE_EXTERNAL_IP']}:3001"
    workflow_url = f"{forgejo_url}/api/v1/repos/{env['FORGEJO_ORG']}/{env['REPO_SUPERDEPLOY']}/actions/workflows/project-deploy.yml/dispatches"

    payload = {
        "ref": "master",
        "inputs": {
            "project": project,
            "service": app,
            "environment": to_env,
            "image": source_image,
            "git_sha": image_tag,
            "git_ref": f"promote-{from_env}-to-{to_env}",
        },
    }

    headers = {
        "Authorization": f"token {env['FORGEJO_PAT']}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            workflow_url, json=payload, headers=headers, timeout=10
        )

        if response.status_code == 204:
            console.print("[green]✅ Promotion triggered successfully![/green]")
            console.print(
                f"\n[cyan]Monitor:[/cyan] {forgejo_url}/{env['FORGEJO_ORG']}/{env['REPO_SUPERDEPLOY']}/actions"
            )
        else:
            console.print(f"[red]❌ API call failed: {response.status_code}[/red]")
            console.print(f"[dim]{response.text}[/dim]")
            raise SystemExit(1)

    except requests.exceptions.RequestException as e:
        console.print(f"[red]❌ Request failed: {e}[/red]")
        raise SystemExit(1)
