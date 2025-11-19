"""Deploy command - Quick local deployment"""

import click
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from cli.base import ProjectCommand
from cli.secret_manager import SecretManager
from cli.exceptions import DeploymentError


@dataclass
class DeploymentConfig:
    """Configuration for deployment."""

    app_name: str
    app_path: Path
    vm_role: str
    image_name: str
    image_tag: str
    image_latest: str
    git_sha: str
    docker_registry: str
    docker_username: Optional[str]
    docker_token: Optional[str]


@dataclass
class VMTarget:
    """Target VM for deployment."""

    ip: str
    ssh_user: str
    ssh_key: Path
    vm_name: str


class DockerImageBuilder:
    """Handles Docker image building operations."""

    def __init__(self, console, verbose: bool = False, json_output: bool = False):
        self.console = console
        self.verbose = verbose

    def build(self, app_path: Path, image_tag: str, image_latest: str) -> bool:
        """Build Docker image with given tags."""
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
            return False

        self.console.print("[green]✓ Build successful[/green]")
        return True

    def push(
        self,
        image_tag: str,
        image_latest: str,
        docker_registry: str,
        docker_username: Optional[str],
        docker_token: Optional[str],
    ) -> bool:
        """Push Docker image to registry."""
        self.console.print("\n[bold]📤 Pushing to registry...[/bold]")

        # Login if credentials provided
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
                return False

        self.console.print("[green]✓ Push successful[/green]")
        return True


class ApplicationDeployer:
    """Handles application deployment to VM."""

    def __init__(self, console, verbose: bool = False, json_output: bool = False):
        self.console = console
        self.verbose = verbose

    def deploy(
        self, target: VMTarget, project_name: str, app_name: str, domain: Optional[str]
    ) -> bool:
        """Deploy application to target VM."""
        self.console.print("\n[bold]🚀 Deploying to VM...[/bold]")
        self.console.print(f"Target: {target.ssh_user}@{target.ip}")

        # Build deployment script
        deploy_script = self._build_deploy_script(project_name, app_name)

        # Execute via SSH
        ssh_cmd = [
            "ssh",
            "-i",
            str(target.ssh_key),
            "-o",
            "StrictHostKeyChecking=no",
            f"{target.ssh_user}@{target.ip}",
            deploy_script,
        ]

        if self.verbose:
            self.console.print(f"[dim]$ ssh {target.ssh_user}@{target.ip} ...[/dim]")

        result = subprocess.run(ssh_cmd)

        if result.returncode == 0:
            self.console.print(f"\n[green]✅ {app_name} deployed successfully![/green]")
            if domain:
                self.console.print(f"🌐 https://{domain}")
            return True
        else:
            self.console.print("\n[red]❌ Deployment failed[/red]")
            return False

    def _build_deploy_script(self, project_name: str, app_name: str) -> str:
        """Build shell script for deployment with replica support."""
        return f"""
cd /opt/superdeploy/projects/{project_name}/compose
echo "🔄 Pulling latest image..."
docker compose pull {app_name}

echo "🚀 Deploying {app_name}..."
docker compose up -d {app_name}

echo "⏳ Waiting for containers to stabilize..."
sleep 5

# Check replica status (no container_name in replicated mode)
RUNNING_REPLICAS=$(docker compose ps {app_name} --status running --format '{{{{.Name}}}}' 2>/dev/null | wc -l)
TOTAL_CONTAINERS=$(docker compose ps {app_name} --format '{{{{.Name}}}}' 2>/dev/null | wc -l)

if [ "$RUNNING_REPLICAS" -ge "1" ]; then
    echo "✅ Deployment successful! ($RUNNING_REPLICAS/$TOTAL_CONTAINERS replicas running)"
    
    # Show logs from first replica
    FIRST_CONTAINER=$(docker compose ps {app_name} --format '{{{{.Name}}}}' 2>/dev/null | head -1)
    if [ -n "$FIRST_CONTAINER" ]; then
        echo ""
        echo "📋 Recent logs from $FIRST_CONTAINER:"
        docker logs $FIRST_CONTAINER --tail 20
    fi
    
    # Cleanup old images
    docker image prune -f >/dev/null 2>&1
else
    echo "❌ Deployment failed - no replicas running"
    echo ""
    echo "📋 Service logs:"
    docker compose logs {app_name} --tail 50
    exit 1
fi
"""


class DeployCommand(ProjectCommand):
    """Quick local deployment - Build, push, and deploy an app."""

    def __init__(
        self,
        project_name: str,
        app_name: str,
        build: bool = True,
        push: bool = True,
        verbose: bool = False,
        json_output: bool = False,
    ):
        super().__init__(project_name, verbose=verbose, json_output=json_output)
        self.app_name = app_name
        self.build_image = build
        self.push_image = push

        # Initialize service classes
        self.image_builder = DockerImageBuilder(self.console, verbose)
        self.app_deployer = ApplicationDeployer(self.console, verbose)

    def execute(self) -> None:
        """Execute deploy command."""
        self.show_header(
            title="Quick Deploy",
            project=self.project_name,
            app=self.app_name,
        )

        # Initialize logger
        logger = self.init_logger(self.project_name, f"deploy-{self.app_name}")

        try:
            if logger:
                logger.step("Loading deployment configuration")
            # Load and validate configuration
            deploy_config = self._load_deployment_config()
            target_vm = self._find_target_vm(deploy_config.vm_role)
            if logger:
                logger.success("Configuration loaded")

            # Display deployment info
            self._display_deployment_info(deploy_config)

            # Step 1: Build Docker image
            if self.build_image:
                if logger:
                    logger.step("Building Docker image")
                if not self.image_builder.build(
                    deploy_config.app_path,
                    deploy_config.image_tag,
                    deploy_config.image_latest,
                ):
                    if logger:
                        logger.log_error("Image build failed")
                    return
                if logger:
                    logger.success("Image built successfully")

            # Step 2: Push to registry
            if self.push_image:
                if logger:
                    logger.step("Pushing image to registry")
                if not self.image_builder.push(
                    deploy_config.image_tag,
                    deploy_config.image_latest,
                    deploy_config.docker_registry,
                    deploy_config.docker_username,
                    deploy_config.docker_token,
                ):
                    if logger:
                        logger.log_error("Image push failed")
                    return
                if logger:
                    logger.success("Image pushed successfully")

            # Step 3: Deploy to VM
            if logger:
                logger.step(f"Deploying to VM ({target_vm.vm_name})")
            domain = self._get_app_domain()
            if not self.app_deployer.deploy(
                target_vm, self.project_name, self.app_name, domain
            ):
                if logger:
                    logger.log_error("Deployment failed")
                return

            if logger:

                logger.success("Deployment completed successfully")

            if not self.verbose:
                self.console.print(f"\n[dim]Logs saved to:[/dim] {logger.log_path}\n")

        except DeploymentError as e:
            if logger:
                logger.log_error(f"Deployment error: {e}")
            self.console.print(f"[red]❌ {e}[/red]")
            if not self.verbose:
                self.console.print(f"[dim]Logs saved to:[/dim] {logger.log_path}\n")
            raise SystemExit(1)
        except Exception as e:
            if logger:
                logger.log_error(f"Unexpected error: {e}")
            self.console.print(f"[red]❌ Error: {e}[/red]")
            if self.verbose:
                import traceback

                self.console.print(traceback.format_exc())
            if not self.verbose:
                self.console.print(f"[dim]Logs saved to:[/dim] {logger.log_path}\n")
            raise SystemExit(1)

    def _load_deployment_config(self) -> DeploymentConfig:
        """Load and validate deployment configuration."""
        # Load secrets
        secret_mgr = SecretManager(self.project_root, self.project_name)
        secrets = secret_mgr.load_secrets()

        if not secrets:
            raise DeploymentError(
                f"No secrets found. Run 'superdeploy {self.project_name}:init' first"
            )

        shared_secrets = secrets.get('shared', {})

        # Load project config
        project_config = self.config_service.load_project_config(self.project_name)
        config = project_config.raw_config

        # Get app configuration
        apps = config.get("apps", {})
        if self.app_name not in apps:
            available = ", ".join(apps.keys())
            raise DeploymentError(
                f"App '{self.app_name}' not found. Available: {available}"
            )

        app_config = apps[self.app_name]
        app_path = Path(app_config["path"])
        vm_role = app_config.get("vm", "app")

        if not app_path.exists():
            raise DeploymentError(f"App path not found: {app_path}")

        # Verify marker file
        marker_file = app_path / "superdeploy"
        if not marker_file.exists():
            raise DeploymentError(
                f"No superdeploy marker found. Run 'superdeploy {self.project_name}:generate' first"
            )

        # Build Docker image configuration
        docker_org = shared_secrets.get(
            "DOCKER_ORG", config.get("docker", {}).get("organization")
        )
        docker_registry = shared_secrets.get(
            "DOCKER_REGISTRY", config.get("docker", {}).get("registry", "docker.io")
        )
        image_name = f"{docker_registry}/{docker_org}/{self.app_name}"

        # Get Git SHA
        git_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=app_path, text=True
        ).strip()[:7]

        return DeploymentConfig(
            app_name=self.app_name,
            app_path=app_path,
            vm_role=vm_role,
            image_name=image_name,
            image_tag=f"{image_name}:{git_sha}",
            image_latest=f"{image_name}:latest",
            git_sha=git_sha,
            docker_registry=docker_registry,
            docker_username=shared_secrets.get("DOCKER_USERNAME"),
            docker_token=shared_secrets.get("DOCKER_TOKEN"),
        )

    def _find_target_vm(self, vm_role: str) -> VMTarget:
        """Find target VM for deployment."""
        state_service = self.ensure_state_service()
        state = state_service.load_state()
        vms = state.get("vms", {})

        # Find VM matching the role
        target_vm = None
        for vm_name, vm_data in vms.items():
            if vm_role in vm_name:
                target_vm = vm_data
                break

        if not target_vm:
            raise DeploymentError(f"No VM found for role '{vm_role}'")

        # Get SSH configuration
        project_config = self.config_service.load_project_config(self.project_name)
        config = project_config.raw_config

        vm_ip = target_vm.get("external_ip")
        ssh_key = Path(
            config.get("cloud", {})
            .get("ssh", {})
            .get("key_path", "~/.ssh/superdeploy_deploy")
        ).expanduser()
        ssh_user = config.get("cloud", {}).get("ssh", {}).get("user", "superdeploy")

        return VMTarget(ip=vm_ip, ssh_user=ssh_user, ssh_key=ssh_key, vm_name=vm_name)

    def _display_deployment_info(self, config: DeploymentConfig) -> None:
        """Display deployment information."""
        self.console.print(f"\n[bold cyan]🚀 Deploying {self.app_name}[/bold cyan]")
        self.console.print(f"Path: {config.app_path}")
        self.console.print(f"VM: {config.vm_role}")
        self.console.print(f"Image: {config.image_tag}")

    def _get_app_domain(self) -> Optional[str]:
        """Get app domain if configured."""
        project_config = self.config_service.load_project_config(self.project_name)
        apps = project_config.raw_config.get("apps", {})
        app_config = apps.get(self.app_name, {})
        return app_config.get("domain")


@click.command(name="deploy")
@click.option("-a", "--app", required=True, help="App name to deploy")
@click.option("--build/--no-build", default=True, help="Build Docker image")
@click.option("--push/--no-push", default=True, help="Push to registry")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def deploy(project, app, build, push, verbose, json_output):
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
    cmd = DeployCommand(project, app, build=build, push=push, verbose=verbose, json_output=json_output)
    cmd.run()
