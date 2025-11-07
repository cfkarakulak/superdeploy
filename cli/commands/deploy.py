"""SuperDeploy CLI - Deploy command (Refactored)"""

import click
import subprocess
from pathlib import Path
from cli.base import ProjectCommand


class DeployCommand(ProjectCommand):
    """Deploy application via git push to Forgejo."""

    def __init__(
        self,
        project_name: str,
        app_name: str,
        message: str = None,
        verbose: bool = False,
    ):
        super().__init__(project_name, verbose=verbose)
        self.app_name = app_name
        self.message = message

    def execute(self) -> None:
        """Execute deploy command."""
        self.show_header(
            title="Deploy Application",
            project=self.project_name,
            app=self.app_name,
            details={"Message": self.message} if self.message else None,
        )

        # Initialize logger
        logger = self.init_logger(self.project_name, f"deploy-{self.app_name}")

        logger.step("[1/2] Preparing Deployment")

        # Get app config
        try:
            app_config = self.get_app_config(self.app_name)
            app_path = Path(app_config["path"]).expanduser()

            if not app_path.exists():
                self.exit_with_error(f"App directory not found: {app_path}")

            self.console.print(f"  ✓ Located {self.app_name} at {app_path}")

        except KeyError:
            self.exit_with_error(f"App '{self.app_name}' not found in project config")

        # Check for changes and commit
        try:
            self._commit_changes(app_path, logger)
        except subprocess.CalledProcessError as e:
            self.handle_error(e, "Git operations failed")
            raise SystemExit(1)

        logger.step("[2/2] Deploying to Production")

        # Push to production
        try:
            result = subprocess.run(
                ["git", "push", "origin", "production"],
                cwd=app_path,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                self.console.print("  ✓ Pushed to production")

                if not self.verbose:
                    self.console.print(
                        "\n[color(248)]Deployment triggered.[/color(248)]"
                    )
                    self.console.print("\n[dim]Monitor logs:[/dim]")
                    self.console.print(
                        f"  [cyan]superdeploy logs -p {self.project_name} -a {self.app_name} -f[/cyan]"
                    )
                    self.console.print(
                        f"\n[dim]Logs saved to:[/dim] {logger.log_path}\n"
                    )
            else:
                logger.log_error("Push failed", context=result.stderr)
                raise SystemExit(1)

        except subprocess.CalledProcessError as e:
            self.handle_error(e, "Git push failed")
            raise SystemExit(1)

    def _commit_changes(self, app_path: Path, logger) -> None:
        """Commit changes if any exist."""
        # Check if there are changes
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=app_path,
            capture_output=True,
            text=True,
        )

        has_changes = bool(result.stdout.strip())

        if has_changes:
            # Add all changes
            subprocess.run(["git", "add", "-A"], cwd=app_path, check=True)

            # Commit
            commit_msg = self.message or f"Deploy {self.app_name}"
            subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=app_path,
                check=True,
                capture_output=True,
            )
            self.console.print("  ✓ Changes committed")
        else:
            self.console.print("  ✓ No changes to commit")


@click.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option("-a", "--app", required=True, help="App name (api, dashboard, services)")
@click.option("--message", "-m", help="Commit message (optional)")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
def deploy(project, app, message, verbose):
    """
    Deploy an application (direct push to Forgejo)

    This command will:
    1. Commit any changes in app-repos/<app>
    2. Push to Forgejo (triggers deployment)
    3. Show deployment logs

    \b
    Quick Deploy:
      superdeploy deploy -p <project> -a <app>

    \b
    With custom message:
      superdeploy deploy -p <project> -a <app> -m "Fix bug"
    """
    cmd = DeployCommand(project, app, message=message, verbose=verbose)
    cmd.run()
