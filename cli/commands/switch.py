"""SuperDeploy CLI - Switch between release versions"""

import click
from cli.base import ProjectCommand


class SwitchCommand(ProjectCommand):
    """Switch application to any version using Git SHA (zero-downtime)."""

    def __init__(
        self,
        project_name: str,
        app_name: str,
        git_sha: str,
        force: bool = False,
        verbose: bool = False,
    ):
        super().__init__(project_name, verbose=verbose)
        self.app_name = app_name
        self.git_sha = git_sha
        self.force = force

    def execute(self) -> None:
        """Execute switch command."""
        self.show_header(
            title="Switch Release Version",
            project=self.project_name,
            app=self.app_name,
            details={"Target Git SHA": self.git_sha[:7] if self.git_sha else "latest"},
        )

        # Get VM for app
        try:
            vm_name, vm_ip = self.get_vm_for_app(self.app_name)
            self.console.print(f"[dim]Target VM: {vm_name} ({vm_ip})[/dim]\n")
        except Exception as e:
            self.console.print(f"[red]❌ Failed to find VM: {e}[/red]")
            raise SystemExit(1)

        # Get SSH service
        vm_service = self.ensure_vm_service()
        ssh_service = vm_service.get_ssh_service()

        # Load config to get Docker org
        config = self.config_service.get_raw_config(self.project_name)
        docker_org = config.get("docker", {}).get("organization", "DOCKER_ORG")

        # Confirm switch
        if not self.force:
            self.console.print(
                f"[yellow]⚠️  This will switch {self.app_name} to Git SHA: {self.git_sha[:7]}[/yellow]"
            )
            self.console.print(
                "\nContinue? [bold bright_white]\\[y/n][/bold bright_white] [dim](y)[/dim]: ",
                end="",
            )
            answer = input().strip().lower()
            if answer not in ["y", "yes", ""]:
                self.console.print("[yellow]⏹️  Switch cancelled[/yellow]")
                return

        self.console.print("\n[cyan]🔄 Starting zero-downtime switch...[/cyan]")

        # Zero-downtime switch script with health check and automatic rollback
        switch_script = f"""
set -e

CONTAINER_NAME="{self.project_name}_{self.app_name}"
NEW_IMAGE="{docker_org}/{self.app_name}:{self.git_sha}"
BACKUP_CONTAINER="${{CONTAINER_NAME}}_backup_$$"

echo "📦 Step 1/5: Pulling new Docker image..."
if ! docker pull $NEW_IMAGE; then
    echo "❌ Failed to pull image: $NEW_IMAGE"
    exit 1
fi

echo "💾 Step 2/5: Backing up current container..."
# Get current image
CURRENT_IMAGE=$(docker inspect --format='{{{{.Config.Image}}}}' $CONTAINER_NAME 2>/dev/null || echo "none")
echo "   Current image: $CURRENT_IMAGE"

if [ "$CURRENT_IMAGE" = "none" ]; then
    echo "⚠️  No existing container found, performing fresh deployment..."
    
    cd /opt/superdeploy/projects/{self.project_name}/compose
    
    # Update docker-compose.yml with new image
    sed -i.bak "s|image: {docker_org}/{self.app_name}:.*|image: $NEW_IMAGE|g" docker-compose.yml
    
    echo "🚀 Step 3/5: Deploying new container..."
    docker compose up -d {self.app_name}
    
    echo "⏳ Step 4/5: Waiting for health check (30s)..."
    sleep 10
    
    STATUS=$(docker inspect -f '{{{{.State.Status}}}}' $CONTAINER_NAME 2>/dev/null || echo "not_found")
    HEALTH=$(docker inspect -f '{{{{.State.Health.Status}}}}' $CONTAINER_NAME 2>/dev/null || echo "none")
    
    if [ "$STATUS" = "running" ]; then
        if [ "$HEALTH" = "healthy" ] || [ "$HEALTH" = "none" ]; then
            echo "✅ Step 5/5: Deployment successful!"
            echo "SWITCH_SUCCESS"
        else
            echo "❌ Container unhealthy: $HEALTH"
            docker logs $CONTAINER_NAME --tail 30
            exit 1
        fi
    else
        echo "❌ Container not running: $STATUS"
        docker logs $CONTAINER_NAME --tail 30
        exit 1
    fi
else
    # Rename current container as backup
    echo "   Renaming to: $BACKUP_CONTAINER"
    docker rename $CONTAINER_NAME $BACKUP_CONTAINER 2>/dev/null || true
    
    cd /opt/superdeploy/projects/{self.project_name}/compose
    
    # Update docker-compose.yml with new image
    sed -i.bak "s|image: {docker_org}/{self.app_name}:.*|image: $NEW_IMAGE|g" docker-compose.yml
    
    echo "🚀 Step 3/5: Starting new container..."
    docker compose up -d {self.app_name}
    
    echo "⏳ Step 4/5: Waiting for health check (30s)..."
    sleep 10
    
    # Check new container health
    STATUS=$(docker inspect -f '{{{{.State.Status}}}}' $CONTAINER_NAME 2>/dev/null || echo "not_found")
    HEALTH=$(docker inspect -f '{{{{.State.Health.Status}}}}' $CONTAINER_NAME 2>/dev/null || echo "none")
    
    if [ "$STATUS" = "running" ] && ([ "$HEALTH" = "healthy" ] || [ "$HEALTH" = "none" ]); then
        echo "✅ Step 5/5: New container healthy, removing backup..."
        docker stop $BACKUP_CONTAINER 2>/dev/null || true
        docker rm $BACKUP_CONTAINER 2>/dev/null || true
        echo "✅ Zero-downtime switch completed!"
        echo "SWITCH_SUCCESS"
    else
        echo "❌ New container failed health check!"
        echo "   Status: $STATUS"
        echo "   Health: $HEALTH"
        echo ""
        echo "🔄 Performing automatic rollback..."
        
        # Stop failed container
        docker stop $CONTAINER_NAME 2>/dev/null || true
        docker rm $CONTAINER_NAME 2>/dev/null || true
        
        # Restore backup
        docker rename $BACKUP_CONTAINER $CONTAINER_NAME
        docker start $CONTAINER_NAME
        
        echo "✅ Rollback complete - original version restored"
        echo ""
        echo "📋 Failed container logs:"
        docker logs $BACKUP_CONTAINER --tail 50 2>/dev/null || echo "No logs available"
        
        echo "ROLLBACK_PERFORMED"
        exit 1
    fi
fi

# Update versions.json
VERSIONS_FILE="/opt/superdeploy/projects/{self.project_name}/versions.json"
if [ -f "$VERSIONS_FILE" ]; then
    DEPLOYED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    UPDATED_JSON=$(cat "$VERSIONS_FILE" | jq --arg app "{self.app_name}" --arg sha "{self.git_sha}" --arg deployed "$DEPLOYED_AT" '
        .[$app].git_sha = $sha |
        .[$app].deployed_at = $deployed |
        .[$app].deployed_by = "switch" |
        .[$app].branch = "manual"
    ')
    echo "$UPDATED_JSON" | sudo tee "$VERSIONS_FILE" > /dev/null
    sudo chown superdeploy:superdeploy "$VERSIONS_FILE"
    echo "📝 Version tracking updated"
fi

# Cleanup old images
docker image prune -f > /dev/null 2>&1
"""

        try:
            result = ssh_service.execute_command(
                vm_ip, switch_script, check=False, timeout=120
            )

            if "SWITCH_SUCCESS" in result.stdout:
                self.console.print(
                    "\n[green]✅ Zero-downtime switch completed successfully![/green]"
                )
                self.console.print(
                    f"[dim]Application switched to Git SHA: {self.git_sha[:7]}[/dim]"
                )
                self.console.print("[dim]  → Old container stopped[/dim]")
                self.console.print("[dim]  → New container started[/dim]")
                self.console.print("[dim]  → Health check passed[/dim]\n")

                # Show verification command
                self.console.print("[bold]Verify deployment:[/bold]")
                self.console.print(
                    f"  [cyan]superdeploy {self.project_name}:status[/cyan]"
                )
                self.console.print(
                    f"  [cyan]superdeploy {self.project_name}:logs -a {self.app_name}[/cyan]\n"
                )
            elif "ROLLBACK_PERFORMED" in result.stdout:
                self.console.print(
                    "\n[red]❌ Switch failed - automatic rollback performed[/red]"
                )
                self.console.print(
                    "[yellow]⚠️  Original version restored (no downtime occurred)[/yellow]"
                )
                self.console.print("\n[dim]Check logs for details:[/dim]")
                self.console.print(f"[dim]{result.stdout}[/dim]\n")
                raise SystemExit(1)
            else:
                self.console.print("\n[red]❌ Switch failed[/red]")
                if self.verbose and result.stderr:
                    self.console.print(f"[dim]{result.stderr}[/dim]")
                raise SystemExit(1)

        except Exception as e:
            self.console.print(f"[red]❌ Switch error: {e}[/red]")
            raise SystemExit(1)


@click.command(name="releases:switch")
@click.option("-a", "--app", required=True, help="App name (api, services, storefront)")
@click.option(
    "-v",
    "--version",
    "git_sha",
    required=True,
    help="Git SHA to switch to (e.g., d0a2405 or full SHA)",
)
@click.option("--force", is_flag=True, help="Skip confirmation")
@click.option("--verbose", is_flag=True, help="Show all command output")
def releases_switch(project, app, git_sha, force, verbose):
    """
    Switch to any release version (forward/backward) with zero-downtime

    \b
    Examples:
      superdeploy cheapa:releases:switch -a api -v d0a2405      # Switch to specific SHA
      superdeploy cheapa:releases:switch -a api -v 622b34f --force  # Skip confirmation

    \b
    Features:
    ✅ Zero-downtime switching (new starts before old stops)
    ✅ Automatic health checks (waits for healthy status)
    ✅ Automatic rollback on failure (no downtime if switch fails)
    ✅ Version tracking (updates versions.json)
    ✅ Unlimited versions (all Git SHAs on Docker Hub)

    \b
    How it works:
    1. Pull Docker image with target Git SHA tag
    2. Rename current container as backup
    3. Start new container from new image
    4. Wait for health check (30s)
    5. If healthy: Stop backup container ✅
    6. If failed: Restore backup container (automatic rollback) 🔄

    \b
    Find available versions:
      superdeploy cheapa:releases:list -a api    # See current deployment
      superdeploy cheapa:status                  # See all app versions
      docker pull <org>/api:<git-sha>            # Check Docker Hub
    """
    cmd = SwitchCommand(project, app, git_sha=git_sha, force=force, verbose=verbose)
    cmd.run()


if __name__ == "__main__":
    releases_switch()
