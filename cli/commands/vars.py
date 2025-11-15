"""SuperDeploy CLI - Vars command (GitHub secrets & variables management)"""

import click
import subprocess
import json
from pathlib import Path
from cli.base import ProjectCommand


def read_env_file(env_path):
    """Read .env file and return as dictionary"""
    env_dict = {}

    if not env_path.exists():
        return env_dict

    try:
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue

                # Parse KEY=VALUE
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()

                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]

                    env_dict[key] = value
    except Exception:
        # Silently skip on error
        pass

    return env_dict


def set_github_repo_secrets(repo, secrets_dict, console):
    """Set GitHub repository secrets using gh CLI"""
    success_count = 0
    fail_count = 0

    for key, value in secrets_dict.items():
        try:
            subprocess.run(
                ["gh", "secret", "set", key, "-b", str(value), "-R", repo],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            console.print(f"  [green]✓[/green] {key}")
            success_count += 1
        except subprocess.TimeoutExpired:
            console.print(f"  [red]✗[/red] {key}: timeout (30s)")
            fail_count += 1
        except subprocess.CalledProcessError as e:
            error_msg = (
                e.stderr if e.stderr else e.stdout if e.stdout else "unknown error"
            )
            error_msg = error_msg.strip().replace("\n", " ")[:60]
            console.print(f"  [red]✗[/red] {key}: {error_msg}")
            fail_count += 1
        except Exception as e:
            error_msg = str(e).strip().replace("\n", " ")[:60]
            console.print(f"  [red]✗[/red] {key}: {error_msg}")
            fail_count += 1

    return success_count, fail_count


def set_github_environment_secrets(repo, environment, secrets_dict, console):
    """Set GitHub environment secrets using gh CLI"""
    success_count = 0
    fail_count = 0

    for key, value in secrets_dict.items():
        try:
            subprocess.run(
                [
                    "gh",
                    "secret",
                    "set",
                    key,
                    "-b",
                    str(value),
                    "-R",
                    repo,
                    "--env",
                    environment,
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            console.print(f"  [green]✓[/green] {key}")
            success_count += 1
        except subprocess.TimeoutExpired:
            console.print(f"  [red]✗[/red] {key}: timeout (30s)")
            fail_count += 1
        except subprocess.CalledProcessError as e:
            error_msg = (
                e.stderr if e.stderr else e.stdout if e.stdout else "unknown error"
            )
            error_msg = error_msg.strip().replace("\n", " ")[:60]
            console.print(f"  [red]✗[/red] {key}: {error_msg}")
            fail_count += 1
        except Exception as e:
            error_msg = str(e).strip().replace("\n", " ")[:60]
            console.print(f"  [red]✗[/red] {key}: {error_msg}")
            fail_count += 1

    return success_count, fail_count


def list_github_repo_secrets(repo, console):
    """List all GitHub repository secrets using gh CLI"""
    try:
        result = subprocess.run(
            ["gh", "secret", "list", "-R", repo, "--json", "name"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        secrets = json.loads(result.stdout)
        return [secret["name"] for secret in secrets]
    except Exception as e:
        console.print(f"[yellow]⚠️  Could not list secrets: {e}[/yellow]")
        return []


def list_github_env_secrets(repo, environment, console):
    """List all GitHub environment secrets using gh CLI"""
    try:
        result = subprocess.run(
            [
                "gh",
                "secret",
                "list",
                "-R",
                repo,
                "--env",
                environment,
                "--json",
                "name",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        secrets = json.loads(result.stdout)
        return [secret["name"] for secret in secrets]
    except Exception as e:
        console.print(f"[yellow]⚠️  Could not list environment secrets: {e}[/yellow]")
        return []


def set_github_env_secrets(repo, environment, secrets_dict, console):
    """Set GitHub environment secrets using gh CLI"""
    return set_github_environment_secrets(repo, environment, secrets_dict, console)


def remove_github_repo_secrets(repo, secret_names, console):
    """Remove GitHub repository secrets using gh CLI"""
    success_count = 0
    fail_count = 0

    for secret_name in secret_names:
        try:
            subprocess.run(
                ["gh", "secret", "remove", secret_name, "-R", repo],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            console.print(f"  [red]✗[/red] {secret_name} [dim](removed)[/dim]")
            success_count += 1
        except subprocess.CalledProcessError as e:
            error_msg = (
                e.stderr if e.stderr else e.stdout if e.stdout else "unknown error"
            )
            error_msg = error_msg.strip().replace("\n", " ")[:60]
            console.print(f"  [yellow]⚠️[/yellow] {secret_name}: {error_msg}")
            fail_count += 1
        except Exception as e:
            error_msg = str(e).strip().replace("\n", " ")[:60]
            console.print(f"  [yellow]⚠️[/yellow] {secret_name}: {error_msg}")
            fail_count += 1

    return success_count, fail_count


def remove_github_env_secrets(repo, environment, secret_names, console):
    """Remove GitHub environment secrets using gh CLI"""
    success_count = 0
    fail_count = 0

    for secret_name in secret_names:
        try:
            subprocess.run(
                [
                    "gh",
                    "secret",
                    "remove",
                    secret_name,
                    "-R",
                    repo,
                    "--env",
                    environment,
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            console.print(f"  [red]✗[/red] {secret_name} [dim](removed)[/dim]")
            success_count += 1
        except subprocess.CalledProcessError as e:
            error_msg = (
                e.stderr if e.stderr else e.stdout if e.stdout else "unknown error"
            )
            error_msg = error_msg.strip().replace("\n", " ")[:60]
            console.print(f"  [yellow]⚠️[/yellow] {secret_name}: {error_msg}")
            fail_count += 1
        except Exception as e:
            error_msg = str(e).strip().replace("\n", " ")[:60]
            console.print(f"  [yellow]⚠️[/yellow] {secret_name}: {error_msg}")
            fail_count += 1

    return success_count, fail_count


class VarsClearCommand(ProjectCommand):
    """Clear ALL GitHub secrets and variables."""

    def __init__(
        self,
        project_name: str,
        environment: str = "production",
        verbose: bool = False,
    ):
        super().__init__(project_name, verbose=verbose, json_output=json_output)
        self.environment = environment

    def execute(self) -> None:
        """Execute vars:clear command."""
        self.show_header(
            title=f"Clear GitHub Secrets ({self.environment})",
            project=self.project_name,
            subtitle="Remove all secrets and variables",
        )

        # Load config
        try:
            project_config = self.config_service.load_project_config(self.project_name)
        except (FileNotFoundError, ValueError) as e:
            self.console.print(f"[red]❌ {e}[/red]")
            return

        config = project_config.raw_config

        # Get GitHub organization from config
        github_org = config.get("github", {}).get("organization")
        if not github_org:
            self.console.print("[red]❌ GitHub organization not configured![/red]")
            return

        # Check gh CLI
        try:
            subprocess.run(["gh", "--version"], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.console.print("[red]❌ gh CLI not found![/red]")
            self.console.print("Install: https://cli.github.com/")
            return

        self.console.print(
            "\n[bold cyan]🧹 Clearing GitHub Secrets & Variables[/bold cyan]\n"
        )

        # Process each app
        for app_name, app_config in config.get("apps", {}).items():
            repo = f"{github_org}/{app_name}"
            self.console.print(f"[yellow]📦 {repo}[/yellow]")

            # Clear repository secrets
            repo_secrets = list_github_repo_secrets(repo, self.console)
            if repo_secrets:
                self.console.print(f"  Found {len(repo_secrets)} repository secrets")
                success, fail = remove_github_repo_secrets(
                    repo, repo_secrets, self.console
                )
                self.console.print(
                    f"  [dim]→ {success} repo secrets removed, {fail} failed[/dim]"
                )

            # Clear environment secrets
            env_secrets = list_github_env_secrets(repo, self.environment, self.console)
            if env_secrets:
                self.console.print(
                    f"  Found {len(env_secrets)} {self.environment} environment secrets"
                )
                success, fail = remove_github_env_secrets(
                    repo, self.environment, env_secrets, self.console
                )
                self.console.print(
                    f"  [dim]→ {success} {self.environment} secrets removed, {fail} failed[/dim]"
                )

            self.console.print()

        self.console.print("\n[green]✅ Clear complete![/green]")


class VarsSyncCommand(ProjectCommand):
    """Sync ALL secrets to GitHub."""

    def __init__(
        self,
        project_name: str,
        environment: str = "production",
        verbose: bool = False,
    ):
        super().__init__(project_name, verbose=verbose, json_output=json_output)
        self.environment = environment

    def execute(self) -> None:
        """Execute vars:sync command."""
        self.show_header(
            title=f"Sync Secrets to GitHub ({self.environment})",
            project=self.project_name,
            subtitle="Automated secret management",
        )

        # Initialize logger
        logger = self.init_logger(self.project_name, f"sync-{self.environment}")

        from cli.secret_manager import SecretManager

        if logger:

            logger.step("Loading project configuration")

        # Load config
        try:
            project_config = self.config_service.load_project_config(self.project_name)
            if logger:
                logger.success("Configuration loaded")
        except FileNotFoundError as e:
            if logger:
                logger.log_error(f"Configuration not found: {e}")
            self.console.print(f"[red]❌ {e}[/red]")
            if not self.verbose:
                self.console.print(f"\n[dim]Logs saved to:[/dim] {logger.log_path}\n")
            return
        except ValueError as e:
            if logger:
                logger.log_error(f"Invalid configuration: {e}")
            self.console.print(f"[red]❌ Invalid configuration: {e}[/red]")
            if not self.verbose:
                self.console.print(f"\n[dim]Logs saved to:[/dim] {logger.log_path}\n")
            return

        config = project_config.raw_config

        # Load secrets
        secret_mgr = SecretManager(self.project_root, self.project_name)
        if not secret_mgr.secrets_file.exists():
            self.console.print("[red]❌ No secrets.yml found![/red]")
            return

        all_secrets = secret_mgr.load_secrets()

        # Get GitHub organization from config
        github_org = config.get("github", {}).get("organization")
        if not github_org:
            self.console.print("[red]❌ GitHub organization not configured![/red]")
            self.console.print("")
            self.console.print("Add to config.yml:")
            self.console.print("[dim]github:")
            self.console.print("  organization: your-github-org[/dim]")
            self.console.print("")
            return

        # Check gh CLI
        try:
            subprocess.run(["gh", "--version"], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.console.print("[red]❌ gh CLI not found![/red]")
            self.console.print("Install: https://cli.github.com/")
            return

        self.console.print("\n[bold cyan]📦 Repository Secrets[/bold cyan]")
        self.console.print(
            "[dim]These secrets are shared across all apps in the repo[/dim]\n"
        )

        # Process each app
        for app_name, app_config in config.get("apps", {}).items():
            repo = f"{github_org}/{app_name}"
            self.console.print(f"[cyan]{repo}:[/cyan]")

            # Note: Use vars:clear to remove all secrets before syncing
            if False:  # Clearing is now a separate command
                self.console.print(
                    "  [yellow]🧹 Clearing ALL existing secrets...[/yellow]"
                )

                # Clear repository secrets
                repo_secrets = list_github_repo_secrets(repo, self.console)
                if repo_secrets:
                    self.console.print(
                        f"  [dim]Found {len(repo_secrets)} repository secrets[/dim]"
                    )
                    success, fail = remove_github_repo_secrets(
                        repo, repo_secrets, self.console
                    )
                    self.console.print(
                        f"  [dim]→ {success} repo secrets removed, {fail} failed[/dim]"
                    )

                # Clear environment secrets for both production and staging
                for env in ["production", "staging"]:
                    env_secrets = list_github_env_secrets(repo, env, self.console)
                    if env_secrets:
                        self.console.print(
                            f"  [dim]Found {len(env_secrets)} {env} environment secrets[/dim]"
                        )
                        success, fail = remove_github_env_secrets(
                            repo, env, env_secrets, self.console
                        )
                        self.console.print(
                            f"  [dim]→ {success} {env} secrets removed, {fail} failed[/dim]"
                        )

                self.console.print()

            # Repository-level secrets (Docker + GitHub access)
            # Note: DOCKER_REGISTRY, DOCKER_ORG, and DOCKER_USERNAME are moved to workflow vars to avoid GitHub secret masking
            # Note: REPOSITORY_TOKEN must have repo, workflow, packages, and read:org scopes for private repos
            repo_secrets = {
                "DOCKER_TOKEN": all_secrets.shared.get("DOCKER_TOKEN"),
                "REPOSITORY_TOKEN": all_secrets.shared.get("REPOSITORY_TOKEN"),
            }

            # Remove None values
            repo_secrets = {k: v for k, v in repo_secrets.items() if v is not None}

            if repo_secrets:
                success, fail = set_github_repo_secrets(
                    repo, repo_secrets, self.console
                )
                self.console.print(f"  [dim]→ {success} success, {fail} failed[/dim]\n")
            else:
                self.console.print(
                    "  [dim]⚠️  No Docker secrets found in shared config[/dim]\n"
                )

            # App environment variables (merged .env + secrets.yml)
            self.console.print(
                f"[cyan]App Environment: {app_name} ({self.environment})[/cyan]"
            )

            # Note: Use vars:clear to remove all secrets before syncing
            if False:  # Clearing is now a separate command
                self.console.print(
                    f"  [yellow]🧹 Clearing environment secrets ({self.environment})...[/yellow]"
                )
                existing_env_secrets = list_github_env_secrets(
                    repo, self.environment, self.console
                )
                if existing_env_secrets:
                    self.console.print(
                        f"  [dim]Found {len(existing_env_secrets)} environment secrets to remove[/dim]"
                    )
                    success, fail = remove_github_env_secrets(
                        repo, self.environment, existing_env_secrets, self.console
                    )
                    self.console.print(
                        f"  [dim]→ {success} removed, {fail} failed[/dim]\n"
                    )
                else:
                    self.console.print(
                        "  [dim]No existing environment secrets found[/dim]\n"
                    )

            # Read app's local .env file
            app_path = Path(app_config["path"]).expanduser().resolve()
            env_file_path = app_path / ".env"

            local_env = {}
            if env_file_path.exists():
                local_env = read_env_file(env_file_path)
                self.console.print(
                    f"  [dim]📄 Read {len(local_env)} variables from .env[/dim]"
                )
            else:
                self.console.print(
                    f"  [dim]⚠️  No .env file found at {env_file_path}[/dim]"
                )

            # Get app secrets from secrets.yml (includes shared + app-specific + env_aliases)
            # Note: get_app_secrets() internally calls get_merged_secrets() which resolves aliases
            app_secrets_dict = secret_mgr.get_app_secrets(app_name)
            self.console.print(
                f"  [dim]🔐 Read {len(app_secrets_dict)} secrets from secrets.yml (with aliases)[/dim]"
            )

            # MERGE: secrets.yml as base, local .env overrides
            merged_env = {**app_secrets_dict, **local_env}
            self.console.print(
                f"  [dim]🔀 Merged total: {len(merged_env)} variables[/dim]"
            )

            # Remove Docker secrets from environment secrets
            docker_keys = [
                "DOCKER_ORG",
                "DOCKER_USERNAME",
                "DOCKER_TOKEN",
                "DOCKER_REGISTRY",
            ]
            env_secret_dict = {
                k: v for k, v in merged_env.items() if k not in docker_keys
            }

            # Set each secret individually (for easy management in GitHub UI)
            self.console.print(
                f"  [dim]Setting {len(env_secret_dict)} individual secrets...[/dim]"
            )
            success, fail = set_github_env_secrets(
                repo, self.environment, env_secret_dict, self.console
            )
            self.console.print(f"  [dim]→ {success} success, {fail} failed[/dim]\n")

            self.console.print()

        self.console.print("\n[green]✅ Sync complete![/green]")
        self.console.print("\n[bold]📝 Next steps:[/bold]")
        self.console.print("\n1. Get GitHub runner token:")
        self.console.print(
            f"   https://github.com/{github_org}/settings/actions/runners/new"
        )
        self.console.print("\n2. Deploy with token:")
        self.console.print(
            f"   [red]GITHUB_RUNNER_TOKEN=<token> superdeploy {self.project_name}:up[/red]"
        )


# ============================================================================
# Click Command Wrappers
# ============================================================================


@click.command(name="vars:clear")
@click.option(
    "-e",
    "--env",
    "environment",
    default="production",
    help="Target environment (production/staging)",
)
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def vars_clear(project, environment, verbose, json_output):
    """
    Clear ALL GitHub secrets and variables

    This will remove:
    - All repository secrets
    - All environment secrets (for specified environment)

    Requirements:
    - gh CLI installed and authenticated

    Examples:
        superdeploy cheapa:vars:clear                # Clear production
        superdeploy cheapa:vars:clear -e staging     # Clear staging
    """
    cmd = VarsClearCommand(project, environment=environment, verbose=verbose, json_output=json_output)
    cmd.run()


@click.command(name="vars:sync")
@click.option(
    "-e",
    "--env",
    "environment",
    default="production",
    help="Target environment (production/staging)",
)
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def vars_sync(project, environment, verbose, json_output):
    """
    Sync ALL secrets to GitHub

    - Repository secrets (Docker credentials, shared build secrets)
    - Environment secrets (per-app secrets for production/staging)

    Requirements:
    - gh CLI installed and authenticated
    - secrets.yml file in project directory
    - GitHub Environments created (production/staging)

    Note: Use vars:clear first if you want to remove old secrets

    Examples:
        superdeploy cheapa:vars:sync                    # Sync to production
        superdeploy cheapa:vars:sync -e staging         # Sync to staging
    """
    cmd = VarsSyncCommand(project, environment=environment, verbose=verbose, json_output=json_output)
    cmd.run()
