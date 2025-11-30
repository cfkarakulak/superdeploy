"""
SuperDeploy GCP Management Commands

Commands for managing GCP authentication and service accounts.
"""

import os
import subprocess
import click
from pathlib import Path
from typing import List, Dict, Optional
from rich.console import Console
from rich.table import Table
from rich.prompt import Confirm

from cli.base import BaseCommand


# ============================================================================
# GCP Utilities (moved from cli/utils/gcp.py)
# ============================================================================


def check_gcp_auth() -> tuple[bool, Optional[str]]:
    """
    Check if GCP authentication is properly configured.

    Returns:
        (is_authenticated, credentials_path)
    """
    # Check GOOGLE_APPLICATION_CREDENTIALS env var
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    if creds_path:
        # Expand ~ to home directory
        creds_path = os.path.expanduser(creds_path)

        if os.path.exists(creds_path):
            return True, creds_path
        else:
            return False, f"File not found: {creds_path}"

    # Check common locations
    common_paths = [
        "~/.superdeploy-sa.json",
        "~/.superdeploy-key.json",
        "~/superdeploy-key.json",
    ]

    for path in common_paths:
        expanded = os.path.expanduser(path)
        if os.path.exists(expanded):
            # Set env var for current session
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = expanded
            return True, expanded

    return False, "No service account credentials found"


def list_gcp_projects() -> Optional[List[Dict[str, str]]]:
    """
    List available GCP projects from authenticated credentials.

    Returns:
        List of project dicts with 'id', 'name', 'number' or None if auth fails
    """
    try:
        from google.cloud import resourcemanager_v3

        client = resourcemanager_v3.ProjectsClient()
        projects = []

        # Search all projects accessible to the authenticated user
        request = resourcemanager_v3.SearchProjectsRequest()

        for project in client.search_projects(request=request):
            # Only include ACTIVE projects
            if project.state == resourcemanager_v3.Project.State.ACTIVE:
                projects.append(
                    {
                        "id": project.project_id,
                        "name": project.display_name,
                        "number": project.name.split("/")[-1],
                    }
                )

        return projects

    except Exception:
        return None


def select_gcp_project(
    console: Console, default_project_id: Optional[str] = None
) -> str:
    """
    Interactive GCP project selection.

    Args:
        console: Rich console for output
        default_project_id: Default project ID if available

    Returns:
        Selected project ID

    Raises:
        RuntimeError: If GCP authentication fails or no projects found
    """
    import inquirer

    projects = list_gcp_projects()

    if projects is None:
        console.print("  [red]✗[/red] Failed to fetch GCP projects")
        console.print("  [yellow]Authentication required[/yellow]")
        console.print("  [dim]Run: superdeploy gcp setup[/dim]\n")
        raise RuntimeError("GCP authentication failed")

    if not projects:
        console.print("  [red]✗[/red] No active GCP projects found")
        console.print(
            "  [dim]Create project at: https://console.cloud.google.com[/dim]\n"
        )
        raise RuntimeError("No GCP projects available")

    # Interactive selection with arrow keys

    # Create choices
    choices = [f"{p['id']} ({p['name']})" for p in projects]

    # Find default
    default = choices[0]
    if default_project_id:
        for choice in choices:
            if choice.startswith(default_project_id):
                default = choice
                break

    questions = [
        inquirer.List(
            "project",
            message="GCP Project",
            choices=choices,
            default=default,
            carousel=True,
        )
    ]

    answers = inquirer.prompt(questions, raise_keyboard_interrupt=True)
    if not answers:
        raise RuntimeError("Project selection cancelled")

    # Extract project ID from selection
    selected = answers["project"]
    selected_project_id = selected.split(" (")[0]
    return selected_project_id


def get_gcp_regions() -> List[str]:
    """Get common GCP regions (predefined list for selection)."""
    return [
        "us-central1",  # Iowa
        "us-east1",  # South Carolina
        "us-east4",  # Virginia
        "us-west1",  # Oregon
        "us-west2",  # Los Angeles
        "us-west3",  # Salt Lake City
        "us-west4",  # Las Vegas
        "europe-west1",  # Belgium
        "europe-west2",  # London
        "europe-west3",  # Frankfurt
        "europe-west4",  # Netherlands
        "europe-north1",  # Finland
        "asia-east1",  # Taiwan
        "asia-east2",  # Hong Kong
        "asia-northeast1",  # Tokyo
        "asia-northeast2",  # Osaka
        "asia-northeast3",  # Seoul
        "asia-southeast1",  # Singapore
        "asia-southeast2",  # Jakarta
        "asia-south1",  # Mumbai
        "australia-southeast1",  # Sydney
        "australia-southeast2",  # Melbourne
        "southamerica-east1",  # São Paulo
    ]


# ============================================================================
# GCP Commands
# ============================================================================


class GcpSetupCommand(BaseCommand):
    """Setup GCP service account for SuperDeploy."""

    def __init__(
        self, project_id: str = None, force: bool = False, verbose: bool = False
    ):
        super().__init__(verbose=verbose)
        self.project_id = project_id
        self.force = force
        self.sa_key_path = Path.home() / ".superdeploy-sa.json"
        self.zshrc_path = Path.home() / ".zshrc"

    def execute(self):
        """Execute GCP setup."""
        self.show_header(
            title="GCP Setup",
            subtitle="Service account configuration",
            border_color="cyan",
        )

        # Step 1: Check if already setup
        if not self.force and self._is_already_setup():
            if not Confirm.ask("Service account already exists. Continue anyway?"):
                self.console.print("[yellow]Setup cancelled.[/yellow]")
                return

        # Step 2: Select or validate project
        if self.project_id:
            selected_project = self.project_id
            self.console.print(f"[dim]Using project: {selected_project}[/dim]")
        else:
            selected_project = select_gcp_project(self.console)
            if not selected_project:
                self.console.print("[red]✗[/red] No project selected")
                raise SystemExit(1)

        # Step 3: Enable required APIs
        self.console.print("\n[cyan]▶[/cyan] Enabling required GCP APIs...")

        apis = [
            "compute.googleapis.com",
            "cloudresourcemanager.googleapis.com",
        ]

        for api in apis:
            result = self._run_command(
                ["gcloud", "services", "enable", api, "--project", selected_project]
            )

            if result.returncode == 0:
                self.console.print(f"[green]✓[/green] {api}")
            else:
                self.console.print(f"[yellow]⚠[/yellow] {api} (may already be enabled)")

        # Step 4: Create service account
        self.console.print("\n[cyan]▶[/cyan] Creating service account...")
        sa_email = f"superdeploy@{selected_project}.iam.gserviceaccount.com"

        result = self._run_command(
            [
                "gcloud",
                "iam",
                "service-accounts",
                "create",
                "superdeploy",
                "--display-name=SuperDeploy Global",
                "--project",
                selected_project,
            ]
        )

        if result.returncode == 0:
            self.console.print("[green]✓[/green] Service account created")
        else:
            if "already exists" in result.stderr.lower():
                self.console.print("[yellow]⚠[/yellow] Service account already exists")
            else:
                self.console.print("[red]✗[/red] Failed to create service account")
                if self.verbose:
                    self.console.print(f"[dim]{result.stderr}[/dim]")
                raise SystemExit(1)

        # Step 5: Grant roles
        self.console.print("\n[cyan]▶[/cyan] Granting permissions...")

        roles = [
            ("roles/compute.admin", "Compute Admin"),
            ("roles/storage.admin", "Storage Admin"),
            ("roles/iam.serviceAccountUser", "Service Account User"),
        ]

        for role, description in roles:
            result = self._run_command(
                [
                    "gcloud",
                    "projects",
                    "add-iam-policy-binding",
                    selected_project,
                    "--member",
                    f"serviceAccount:{sa_email}",
                    "--role",
                    role,
                    "--quiet",
                ]
            )

            if result.returncode == 0:
                self.console.print(f"[green]✓[/green] {description}")
            else:
                self.console.print(
                    f"[yellow]⚠[/yellow] {description} (may already exist)"
                )

        # Step 6: Create and download key
        self.console.print("\n[cyan]▶[/cyan] Creating service account key...")

        # Remove old key if exists
        if self.sa_key_path.exists():
            self.sa_key_path.unlink()

        result = self._run_command(
            [
                "gcloud",
                "iam",
                "service-accounts",
                "keys",
                "create",
                str(self.sa_key_path),
                "--iam-account",
                sa_email,
                "--project",
                selected_project,
            ]
        )

        if result.returncode == 0:
            self.console.print(f"[green]✓[/green] Key saved to {self.sa_key_path}")
        else:
            self.console.print("[red]✗[/red] Failed to create key")
            if self.verbose:
                self.console.print(f"[dim]{result.stderr}[/dim]")
            raise SystemExit(1)

        # Step 7: Add to shell config
        self.console.print("\n[cyan]▶[/cyan] Configuring environment...")

        env_line = f"export GOOGLE_APPLICATION_CREDENTIALS={self.sa_key_path}"

        if self._add_to_shell_config(env_line):
            self.console.print("[green]✓[/green] Added to ~/.zshrc")
        else:
            self.console.print("[yellow]⚠[/yellow] Already in ~/.zshrc")

        # Step 8: Success message
        self.console.print("\n[bold green]✅ Setup Complete![/bold green]\n")
        self.console.print("[dim]To activate in current shell:[/dim]")
        self.console.print("[cyan]  source ~/.zshrc[/cyan]")
        self.console.print("[cyan]  # OR[/cyan]")
        self.console.print(
            f"[cyan]  export GOOGLE_APPLICATION_CREDENTIALS={self.sa_key_path}[/cyan]\n"
        )

    def _is_already_setup(self) -> bool:
        """Check if service account is already configured."""
        return self.sa_key_path.exists()

    def _add_to_shell_config(self, line: str) -> bool:
        """Add environment variable to shell config. Returns True if added."""
        if not self.zshrc_path.exists():
            self.zshrc_path.touch()

        content = self.zshrc_path.read_text()

        if "GOOGLE_APPLICATION_CREDENTIALS" in content:
            return False

        with open(self.zshrc_path, "a") as f:
            f.write("\n# SuperDeploy GCP Service Account\n")
            f.write(f"{line}\n")

        return True

    def _run_command(self, cmd: list) -> subprocess.CompletedProcess:
        """Run shell command and return result."""
        return subprocess.run(cmd, capture_output=True, text=True)


class GcpAuthStatusCommand(BaseCommand):
    """Show GCP authentication status."""

    def execute(self):
        """Execute status check."""
        self.show_header(
            title="GCP Authentication Status",
            subtitle="Check current authentication",
            border_color="cyan",
        )

        table = Table(show_header=False, padding=(0, 2))
        table.add_column("Check", style="white")
        table.add_column("Status")

        # Check gcloud auth
        result = subprocess.run(
            ["gcloud", "config", "get-value", "account"], capture_output=True, text=True
        )
        gcloud_account = result.stdout.strip() if result.returncode == 0 else None

        if gcloud_account:
            table.add_row("gcloud account", f"[green]✓[/green] {gcloud_account}")
        else:
            table.add_row("gcloud account", "[red]✗[/red] Not authenticated")

        # Check gcloud project
        result = subprocess.run(
            ["gcloud", "config", "get-value", "project"], capture_output=True, text=True
        )
        gcloud_project = result.stdout.strip() if result.returncode == 0 else None

        if gcloud_project:
            table.add_row("gcloud project", f"[green]✓[/green] {gcloud_project}")
        else:
            table.add_row("gcloud project", "[yellow]⚠[/yellow] Not set")

        # Check GOOGLE_APPLICATION_CREDENTIALS
        cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

        if cred_path:
            if Path(cred_path).exists():
                table.add_row("Service Account", f"[green]✓[/green] {cred_path}")
            else:
                table.add_row(
                    "Service Account",
                    f"[yellow]⚠[/yellow] {cred_path} (file not found)",
                )
        else:
            table.add_row("Service Account", "[yellow]⚠[/yellow] Not set")

        # Check if ready
        ready = bool(cred_path and Path(cred_path).exists())

        self.console.print(table)
        self.console.print()

        if ready:
            self.console.print("[bold green]✅ Ready to deploy![/bold green]\n")
        else:
            self.console.print("[bold yellow]⚠️  Setup required[/bold yellow]")
            self.console.print("[dim]Run: superdeploy gcp setup[/dim]\n")


class GcpAuthRotateCommand(BaseCommand):
    """Rotate GCP service account key."""

    def __init__(self, project_id: str = None, verbose: bool = False):
        super().__init__(verbose=verbose)
        self.project_id = project_id
        self.sa_key_path = Path.home() / ".superdeploy-sa.json"

    def execute(self):
        """Execute key rotation."""
        self.show_header(
            title="Rotate Service Account Key",
            subtitle="Generate new credentials",
            border_color="yellow",
        )

        # Check if key exists
        if not self.sa_key_path.exists():
            self.console.print("[red]✗[/red] No service account key found")
            self.console.print("[dim]Run: superdeploy gcp:setup[/dim]")
            raise SystemExit(1)

        # Read current key to get project and email
        import json

        try:
            with open(self.sa_key_path) as f:
                key_data = json.load(f)
                project_id = key_data.get("project_id")
                sa_email = key_data.get("client_email")
        except Exception as e:
            self.console.print(f"[red]✗[/red] Failed to read key file: {e}")
            raise SystemExit(1)

        if not project_id or not sa_email:
            self.console.print("[red]✗[/red] Invalid key file")
            raise SystemExit(1)

        self.console.print(f"[dim]Project: {project_id}[/dim]")
        self.console.print(f"[dim]Service Account: {sa_email}[/dim]\n")

        if not Confirm.ask("Continue with key rotation?"):
            self.console.print("[yellow]Rotation cancelled.[/yellow]")
            return

        # Delete old key
        self.console.print("[cyan]▶[/cyan] Deleting old key...")
        self.sa_key_path.unlink()
        self.console.print("[green]✓[/green] Old key deleted")

        # Create new key
        self.console.print("[cyan]▶[/cyan] Creating new key...")
        result = subprocess.run(
            [
                "gcloud",
                "iam",
                "service-accounts",
                "keys",
                "create",
                str(self.sa_key_path),
                "--iam-account",
                sa_email,
                "--project",
                project_id,
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            self.console.print("[green]✓[/green] New key created")
            self.console.print(
                "\n[bold green]✅ Key rotated successfully![/bold green]\n"
            )
        else:
            self.console.print("[red]✗[/red] Failed to create new key")
            if self.verbose:
                self.console.print(f"[dim]{result.stderr}[/dim]")
            raise SystemExit(1)


class GcpProjectsCommand(BaseCommand):
    """List available GCP projects."""

    def execute(self):
        """Execute projects listing."""
        self.show_header(
            title="GCP Projects", subtitle="Available projects", border_color="cyan"
        )

        self.console.print("[cyan]▶[/cyan] Fetching GCP projects...\n")

        projects = list_gcp_projects()

        if projects is None:
            self.console.print("[yellow]⚠[/yellow] Could not fetch GCP projects")
            self.console.print("[dim]Make sure you're authenticated:[/dim]")
            self.console.print("[dim]  gcloud auth application-default login[/dim]")
            self.console.print("[dim]  OR set GOOGLE_APPLICATION_CREDENTIALS[/dim]\n")
            raise SystemExit(1)

        if not projects:
            self.console.print("[yellow]⚠[/yellow] No active GCP projects found\n")
            return

        for idx, project in enumerate(projects, 1):
            self.console.print(
                f"  [dim]{idx}.[/dim] [cyan]{project['id']}[/cyan] [dim]({project['name']})[/dim]"
            )

        self.console.print(f"\n[dim]Total: {len(projects)} project(s)[/dim]\n")


@click.group(name="gcp")
def gcp_group():
    """GCP authentication and project management."""
    pass


@gcp_group.command(name="setup")
@click.option("--project", "-p", help="GCP Project ID")
@click.option(
    "--force", "-f", is_flag=True, help="Force setup even if already configured"
)
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def gcp_setup_command(project, force, verbose):
    """Setup GCP service account for SuperDeploy."""
    cmd = GcpSetupCommand(project_id=project, force=force, verbose=verbose)
    cmd.execute()


@gcp_group.group(name="auth")
def auth_group():
    """GCP authentication commands."""
    pass


@auth_group.command(name="status")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def gcp_auth_status_command(verbose):
    """Show GCP authentication status."""
    cmd = GcpAuthStatusCommand(verbose=verbose)
    cmd.execute()


@auth_group.command(name="rotate")
@click.option("--project", "-p", help="GCP Project ID")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def gcp_auth_rotate_command(project, verbose):
    """Rotate GCP service account key."""
    cmd = GcpAuthRotateCommand(project_id=project, verbose=verbose)
    cmd.execute()


@gcp_group.command(name="projects")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def gcp_projects_command(verbose):
    """List available GCP projects."""
    cmd = GcpProjectsCommand(verbose=verbose)
    cmd.execute()
