"""Deploy command - Quick local deployment"""

import click
import subprocess
import yaml
from pathlib import Path
from cli.base import ProjectCommand
from cli.secret_manager import SecretManager


class DeployCommand(ProjectCommand):
    """Quick local deployment - Build, push, and deploy an app."""

    def __init__(
        self,
        project_name: str,
        app_name: str,
        build: bool = True,
        push: bool = True,
        verbose: bool = False,
    ):
        super().__init__(project_name, verbose=verbose)
        self.app_name = app_name
        self.build = build
        self.push = push

    def execute(self) -> None:
        """Execute deploy command."""
        from cli.utils import get_project_root

        try:
            # Get project root
            project_root = get_project_root()

            # Load secrets
            secret_mgr = SecretManager(project_root, self.project_name)
            secrets = secret_mgr.load_secrets()

            if not secrets or "secrets" not in secrets:
                self.console.print(
                    f"[red]❌ No secrets found. Run 'superdeploy {self.project_name}:init' first[/red]"
                )
                return

            shared_secrets = secrets["secrets"].get("shared", {})

            # Find app in project config
            config_file = project_root / "projects" / self.project_name / "config.yml"
            if not config_file.exists():
                self.console.print(
                    f"[red]❌ Project config not found: {config_file}[/red]"
                )
                return

            with open(config_file) as f:
                config = yaml.safe_load(f)

            apps = config.get("apps", {})
            if self.app_name not in apps:
                self.console.print(
                    f"[red]❌ App '{self.app_name}' not found in config[/red]"
                )
                self.console.print(f"Available apps: {', '.join(apps.keys())}")
                return

            app_config = apps[self.app_name]
            app_path = Path(app_config["path"])
            vm_role = app_config.get("vm", "app")

            if not app_path.exists():
                self.console.print(f"[red]❌ App path not found: {app_path}[/red]")
                return

            self.console.print(f"\n[bold cyan]🚀 Deploying {self.app_name}[/bold cyan]")
            self.console.print(f"Path: {app_path}")
            self.console.print(f"VM: {vm_role}")

            # Read .superdeploy marker (verify it exists)
            marker_file = app_path / ".superdeploy"
            if not marker_file.exists():
                self.console.print(
                    f"[red]❌ No .superdeploy marker found. Run 'superdeploy {self.project_name}:generate' first[/red]"
                )
                return

            # Docker config
            docker_org = shared_secrets.get(
                "DOCKER_ORG", config.get("docker", {}).get("organization")
            )
            docker_registry = shared_secrets.get(
                "DOCKER_REGISTRY",
                config.get("docker", {}).get("registry", "docker.io"),
            )
            image_name = f"{docker_registry}/{docker_org}/{self.app_name}"

            # Get Git SHA for tagging
            git_sha = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=app_path, text=True
            ).strip()[:7]

            image_tag = f"{image_name}:{git_sha}"
            image_latest = f"{image_name}:latest"

            self.console.print(f"Image: {image_tag}")

            # Step 1: Build
            if self.build:
                self.console.print("\n[bold]📦 Building Docker image...[/bold]")
                build_cmd = [
                    "docker",
                    "build",
                    "-t",
                    image_tag,
                    "-t",
                    image_latest,
                    str(app_path),
                ]

                if self.verbose:
                    self.console.print(f"[dim]$ {' '.join(build_cmd)}[/dim]")

                result = subprocess.run(build_cmd, cwd=app_path)
                if result.returncode != 0:
                    self.console.print("[red]❌ Build failed[/red]")
                    return

                self.console.print("[green]✓ Build successful[/green]")

            # Step 2: Push
            if self.push:
                self.console.print("\n[bold]📤 Pushing to registry...[/bold]")

                # Login first
                docker_username = shared_secrets.get("DOCKER_USERNAME")
                docker_token = shared_secrets.get("DOCKER_TOKEN")

                if docker_username and docker_token:
                    login_result = subprocess.run(
                        [
                            "docker",
                            "login",
                            docker_registry,
                            "-u",
                            docker_username,
                            "--password-stdin",
                        ],
                        input=docker_token,
                        text=True,
                        capture_output=True,
                    )
                    if login_result.returncode != 0:
                        self.console.print(
                            "[yellow]⚠️  Docker login failed, continuing anyway...[/yellow]"
                        )

                # Push both tags
                for tag in [image_tag, image_latest]:
                    if self.verbose:
                        self.console.print(f"[dim]Pushing {tag}...[/dim]")

                    result = subprocess.run(["docker", "push", tag])
                    if result.returncode != 0:
                        self.console.print(f"[red]❌ Push failed for {tag}[/red]")
                        return

                self.console.print("[green]✓ Push successful[/green]")

            # Step 3: Deploy to VM
            self.console.print("\n[bold]🚀 Deploying to VM...[/bold]")

            # Find target VM
            state = self.state_service.load_state()

            vms = state.get("vms", {})
            target_vm = None

            # Find VM matching the role
            for vm_name, vm_data in vms.items():
                if vm_role in vm_name:
                    target_vm = vm_data
                    break

            if not target_vm:
                self.console.print(f"[red]❌ No VM found for role '{vm_role}'[/red]")
                return

            vm_ip = target_vm.get("external_ip")
            ssh_key = Path(
                config.get("cloud", {})
                .get("ssh", {})
                .get("key_path", "~/.ssh/superdeploy_deploy")
            ).expanduser()
            ssh_user = (
                config.get("cloud", {}).get("ssh", {}).get("user", "superdeploy")
            )

            self.console.print(f"Target: {ssh_user}@{vm_ip}")

            # Deploy via SSH
            deploy_script = f"""
cd /opt/superdeploy/projects/{self.project_name}/compose
echo "🔄 Pulling latest image..."
docker compose pull {self.app_name}
echo "🚀 Deploying {self.app_name}..."
docker compose up -d {self.app_name}
sleep 3
CONTAINER_NAME="{self.project_name}_{self.app_name}"
STATUS=$(docker inspect -f '{{{{.State.Status}}}}' $CONTAINER_NAME 2>/dev/null || echo "not_found")
if [ "$STATUS" = "running" ]; then
    echo "✅ Deployment successful!"
    docker logs $CONTAINER_NAME --tail 20
    docker image prune -f
else
    echo "❌ Container failed to start"
    docker logs $CONTAINER_NAME --tail 50
    exit 1
fi
"""

            ssh_cmd = [
                "ssh",
                "-i",
                str(ssh_key),
                "-o",
                "StrictHostKeyChecking=no",
                f"{ssh_user}@{vm_ip}",
                deploy_script,
            ]

            if self.verbose:
                self.console.print(f"[dim]$ ssh {ssh_user}@{vm_ip} ...[/dim]")

            result = subprocess.run(ssh_cmd)

            if result.returncode == 0:
                self.console.print(
                    f"\n[green]✅ {self.app_name} deployed successfully![/green]"
                )

                # Show URL if domain configured
                domain = app_config.get("domain")
                if domain:
                    self.console.print(f"🌐 https://{domain}")
            else:
                self.console.print("\n[red]❌ Deployment failed[/red]")
                return

        except Exception as e:
            self.console.print(f"[red]❌ Error: {e}[/red]")
            if self.verbose:
                import traceback

                self.console.print(traceback.format_exc())


@click.command(name="deploy")
@click.option("-a", "--app", required=True, help="App name to deploy")
@click.option("--build/--no-build", default=True, help="Build Docker image")
@click.option("--push/--no-push", default=True, help="Push to registry")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def deploy(project, app, build, push, verbose):
    """
    Quick local deployment - Build, push, and deploy an app

    This command will:
    1. Read app configuration from .superdeploy marker
    2. Build Docker image (if --build)
    3. Push to registry (if --push)
    4. Deploy to target VM via SSH

    Examples:
        superdeploy cheapa:deploy -a api
        superdeploy cheapa:deploy -a storefront --no-build
        superdeploy cheapa:deploy -a api -v
    """
    cmd = DeployCommand(project, app, build=build, push=push, verbose=verbose)
    cmd.run()
