"""SuperDeploy CLI - Promote command"""

import click
from cli.base import ProjectCommand


class PromoteCommand(ProjectCommand):
    """Promote code between environments using Git branches."""

    def __init__(
        self,
        project_name: str,
        app_name: str,
        from_branch: str = "staging",
        to_branch: str = "production",
        verbose: bool = False,
    ):
        super().__init__(project_name, verbose=verbose)
        self.app_name = app_name
        self.from_branch = from_branch
        self.to_branch = to_branch

    def execute(self) -> None:
        """Execute promote command."""
        self.show_header(
            title="Promote Between Environments",
            project=self.project_name,
            app=self.app_name,
            details={"From": self.from_branch, "To": self.to_branch},
        )

        self.console.print("[bold]Run these commands:[/bold]")
        self.console.print(f"  [green]cd app-repos/{self.app_name}[/green]")
        self.console.print(
            f"  [green]git checkout {self.from_branch} && git pull[/green]"
        )
        self.console.print(f"  [green]git checkout {self.to_branch}[/green]")
        self.console.print(f"  [green]git merge {self.from_branch}[/green]")
        self.console.print(
            f"  [green]git push origin {self.to_branch}[/green]  # Auto-deploys!\n"
        )

        self.console.print(
            "[dim]GitHub Actions will automatically deploy to production[/dim]\n"
        )


@click.command()
@click.option("-a", "--app", required=True, help="App name")
@click.option("--from-branch", default="staging", help="Source branch")
@click.option("--to-branch", default="production", help="Target branch")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
def promote(project, app, from_branch, to_branch, verbose):
    """
    Promote code between environments using Git branches

    \b
    Example:
      superdeploy cheapa:promote -a api
      # Merges staging → production and auto-deploys
    """
    cmd = PromoteCommand(
        project, app, from_branch=from_branch, to_branch=to_branch, verbose=verbose
    )
    cmd.run()
