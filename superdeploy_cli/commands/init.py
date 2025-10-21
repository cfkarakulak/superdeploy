"""SuperDeploy CLI - Init command (Interactive setup wizard)"""

import click
import inquirer
import secrets
from rich.console import Console
from rich.panel import Panel
from pathlib import Path
import subprocess

console = Console()


@click.command()
@click.option(
    "--non-interactive", is_flag=True, help="Non-interactive mode (use defaults)"
)
def init(non_interactive):
    """
    Interactive setup wizard - Creates .env with smart defaults

    This command will:
    - Detect GCP project
    - Generate secure passwords
    - Create SSH keys (if needed)
    - Set up .env file
    """
    console.print(
        Panel.fit(
            "[bold cyan]SuperDeploy Setup Wizard[/bold cyan]\n\n"
            "[white]Let's configure your deployment environment![/white]",
            border_style="cyan",
        )
    )

    env_data = {}

    # Detect GCP project
    console.print("\n[cyan]━━━ Step 1/6: GCP Configuration ━━━[/cyan]")
    try:
        result = subprocess.run(
            ["gcloud", "config", "get-value", "project"], capture_output=True, text=True
        )
        detected_project = result.stdout.strip()
        console.print(f"[dim]Detected project: {detected_project}[/dim]")
    except:
        detected_project = ""

    if non_interactive:
        env_data["GCP_PROJECT_ID"] = detected_project or "your-project-id"
    else:
        questions = [
            inquirer.Text(
                "gcp_project", message="GCP Project ID", default=detected_project or ""
            ),
            inquirer.List(
                "gcp_region",
                message="GCP Region",
                choices=["us-central1", "us-east1", "europe-west1", "asia-southeast1"],
                default="us-central1",
            ),
        ]
        answers = inquirer.prompt(questions)
        env_data["GCP_PROJECT_ID"] = answers["gcp_project"]
        env_data["GCP_REGION"] = answers["gcp_region"]

    # SSH Key
    console.print("\n[cyan]━━━ Step 2/6: SSH Configuration ━━━[/cyan]")
    ssh_key_path = Path.home() / ".ssh" / "superdeploy_gcp"

    if not ssh_key_path.exists():
        if non_interactive or inquirer.confirm(
            "SSH key not found. Create one?", default=True
        ):
            console.print("[yellow]Creating SSH key...[/yellow]")
            subprocess.run(
                ["ssh-keygen", "-t", "ed25519", "-f", str(ssh_key_path), "-N", ""],
                check=True,
            )
            console.print("[green]✅ SSH key created![/green]")

            # Add to GCP
            if inquirer.confirm("Add SSH key to GCP?", default=True):
                subprocess.run(
                    [
                        "gcloud",
                        "compute",
                        "os-login",
                        "ssh-keys",
                        "add",
                        "--key-file",
                        f"{ssh_key_path}.pub",
                    ],
                    check=False,
                )

    env_data["SSH_KEY_PATH"] = "~/.ssh/superdeploy_gcp"
    env_data["SSH_USER"] = "superdeploy"

    # Docker Hub
    console.print("\n[cyan]━━━ Step 3/6: Docker Hub ━━━[/cyan]")
    docker_questions = [
        inquirer.Text("docker_user", message="Docker Hub username"),
        inquirer.Password("docker_token", message="Docker Hub token"),
    ]

    if not non_interactive:
        docker_answers = inquirer.prompt(docker_questions)
        env_data["DOCKER_USERNAME"] = docker_answers["docker_user"]
        env_data["DOCKER_TOKEN"] = docker_answers["docker_token"]
        env_data["DOCKER_ORG"] = docker_answers["docker_user"]
    else:
        env_data["DOCKER_USERNAME"] = "your-dockerhub-username"
        env_data["DOCKER_TOKEN"] = "your-dockerhub-token"
        env_data["DOCKER_ORG"] = "your-dockerhub-username"

    env_data["DOCKER_REGISTRY"] = "docker.io"

    # GitHub
    console.print("\n[cyan]━━━ Step 4/6: GitHub Integration ━━━[/cyan]")
    if not non_interactive:
        github_token = inquirer.text("GitHub Personal Access Token")
        env_data["GITHUB_TOKEN"] = github_token
    else:
        env_data["GITHUB_TOKEN"] = "ghp_your_github_token"

    # Forgejo
    console.print("\n[cyan]━━━ Step 5/6: Forgejo Configuration ━━━[/cyan]")
    console.print("[dim]Generating secure passwords...[/dim]")

    env_data["FORGEJO_ORG"] = "cradexco"
    env_data["FORGEJO_ADMIN_USER"] = "admin"
    env_data["FORGEJO_ADMIN_PASSWORD"] = secrets.token_urlsafe(16)
    env_data["FORGEJO_ADMIN_EMAIL"] = "admin@example.com"
    env_data["REPO_SUPERDEPLOY"] = "superdeploy-app"
    env_data["FORGEJO_DB_USER"] = "superdeploy"
    env_data["FORGEJO_DB_PASSWORD"] = secrets.token_urlsafe(16)
    env_data["FORGEJO_DB_NAME"] = "forgejo"

    # App Secrets
    console.print("\n[cyan]━━━ Step 6/6: Application Secrets ━━━[/cyan]")
    console.print("[dim]Generating strong passwords...[/dim]")

    env_data["POSTGRES_USER"] = "superdeploy"
    env_data["POSTGRES_PASSWORD"] = secrets.token_urlsafe(24)
    env_data["POSTGRES_DB"] = "superdeploy_db"
    env_data["RABBITMQ_USER"] = "superdeploy"
    env_data["RABBITMQ_PASSWORD"] = secrets.token_urlsafe(24)
    env_data["REDIS_PASSWORD"] = secrets.token_urlsafe(24)
    env_data["API_SECRET_KEY"] = secrets.token_hex(32)

    # Feature Toggles
    env_data["USE_REMOTE_STATE"] = "false"
    env_data["ENABLE_MONITORING"] = "false"
    env_data["ENABLE_HARDENING"] = "false"
    env_data["EXPOSE_RABBITMQ_MGMT"] = "true"

    # Monitoring
    if not non_interactive:
        alert_email = inquirer.text("Alert email", default="your-email@example.com")
        env_data["ALERT_EMAIL"] = alert_email
    else:
        env_data["ALERT_EMAIL"] = "your-email@example.com"

    env_data["GRAFANA_ADMIN_USER"] = "admin"
    env_data["GRAFANA_ADMIN_PASSWORD"] = secrets.token_urlsafe(16)

    # IP placeholders
    env_data["CORE_EXTERNAL_IP"] = ""
    env_data["CORE_INTERNAL_IP"] = ""
    env_data["SCRAPE_EXTERNAL_IP"] = ""
    env_data["SCRAPE_INTERNAL_IP"] = ""
    env_data["PROXY_EXTERNAL_IP"] = ""
    env_data["PROXY_INTERNAL_IP"] = ""

    # VM Config
    env_data["VM_MACHINE_TYPE"] = "e2-medium"
    env_data["VM_DISK_SIZE"] = "20"
    env_data["VM_IMAGE"] = "debian-cloud/debian-11"

    # Write .env file
    console.print("\n[cyan]━━━ Writing .env file... ━━━[/cyan]")
    env_file = Path.cwd() / ".env"

    with open(env_file, "w") as f:
        f.write("# SuperDeploy Configuration\n")
        f.write("# Generated by: superdeploy init\n\n")

        for key, value in env_data.items():
            f.write(f"{key}={value}\n")

    console.print(f"\n[green]✅ Configuration saved to:[/green] {env_file}")

    # Summary
    console.print("\n[bold cyan]━━━ Setup Complete! ━━━[/bold cyan]")
    console.print("\n[white]Next steps:[/white]")
    console.print("  1. [cyan]superdeploy up[/cyan]        # Deploy infrastructure")
    console.print("  2. [cyan]superdeploy sync[/cyan]      # Sync secrets to GitHub")
    console.print("  3. [cyan]superdeploy deploy[/cyan]    # Deploy applications")

    console.print("\n[dim]Estimated time: ~10 minutes[/dim]")
