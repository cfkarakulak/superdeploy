"""Deploy command - Quick local deployment"""

import click
import subprocess
import json
from pathlib import Path
from rich.console import Console
from cli.secret_manager import SecretManager

console = Console()


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
    from cli.utils import get_project_root
    
    try:
        # Get project root
        project_root = get_project_root()
        
        # Load secrets
        secret_mgr = SecretManager(project_root, project)
        secrets = secret_mgr.load_secrets()
        
        if not secrets or "secrets" not in secrets:
            console.print("[red]❌ No secrets found. Run 'superdeploy {project}:init' first[/red]")
            return
        
        shared_secrets = secrets["secrets"].get("shared", {})
        
        # Find app in project config
        config_file = project_root / "projects" / project / "config.yml"
        if not config_file.exists():
            console.print(f"[red]❌ Project config not found: {config_file}[/red]")
            return
        
        import yaml
        with open(config_file) as f:
            config = yaml.safe_load(f)
        
        apps = config.get("apps", {})
        if app not in apps:
            console.print(f"[red]❌ App '{app}' not found in config[/red]")
            console.print(f"Available apps: {', '.join(apps.keys())}")
            return
        
        app_config = apps[app]
        app_path = Path(app_config["path"])
        vm_role = app_config.get("vm", "app")
        
        if not app_path.exists():
            console.print(f"[red]❌ App path not found: {app_path}[/red]")
            return
        
        console.print(f"\n[bold cyan]🚀 Deploying {app}[/bold cyan]")
        console.print(f"Path: {app_path}")
        console.print(f"VM: {vm_role}")
        
        # Read .superdeploy marker
        marker_file = app_path / ".superdeploy"
        if not marker_file.exists():
            console.print(f"[red]❌ No .superdeploy marker found. Run 'superdeploy {project}:generate' first[/red]")
            return
        
        with open(marker_file) as f:
            marker = yaml.safe_load(f)
        
        # Docker config
        docker_org = shared_secrets.get("DOCKER_ORG", config.get("docker", {}).get("organization"))
        docker_registry = shared_secrets.get("DOCKER_REGISTRY", config.get("docker", {}).get("registry", "docker.io"))
        image_name = f"{docker_registry}/{docker_org}/{app}"
        
        # Get Git SHA for tagging
        git_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=app_path,
            text=True
        ).strip()[:7]
        
        image_tag = f"{image_name}:{git_sha}"
        image_latest = f"{image_name}:latest"
        
        console.print(f"Image: {image_tag}")
        
        # Step 1: Build
        if build:
            console.print("\n[bold]📦 Building Docker image...[/bold]")
            build_cmd = [
                "docker", "build",
                "-t", image_tag,
                "-t", image_latest,
                str(app_path)
            ]
            
            if verbose:
                console.print(f"[dim]$ {' '.join(build_cmd)}[/dim]")
            
            result = subprocess.run(build_cmd, cwd=app_path)
            if result.returncode != 0:
                console.print("[red]❌ Build failed[/red]")
                return
            
            console.print("[green]✓ Build successful[/green]")
        
        # Step 2: Push
        if push:
            console.print("\n[bold]📤 Pushing to registry...[/bold]")
            
            # Login first
            docker_username = shared_secrets.get("DOCKER_USERNAME")
            docker_token = shared_secrets.get("DOCKER_TOKEN")
            
            if docker_username and docker_token:
                login_result = subprocess.run(
                    ["docker", "login", docker_registry, "-u", docker_username, "--password-stdin"],
                    input=docker_token,
                    text=True,
                    capture_output=True
                )
                if login_result.returncode != 0:
                    console.print("[yellow]⚠️  Docker login failed, continuing anyway...[/yellow]")
            
            # Push both tags
            for tag in [image_tag, image_latest]:
                if verbose:
                    console.print(f"[dim]Pushing {tag}...[/dim]")
                
                result = subprocess.run(["docker", "push", tag])
                if result.returncode != 0:
                    console.print(f"[red]❌ Push failed for {tag}[/red]")
                    return
            
            console.print("[green]✓ Push successful[/green]")
        
        # Step 3: Deploy to VM
        console.print("\n[bold]🚀 Deploying to VM...[/bold]")
        
        # Find target VM
        from cli.state_manager import StateManager
        state_mgr = StateManager(project_root, project)
        state = state_mgr.load_state()
        
        vms = state.get("vms", {})
        target_vm = None
        
        # Find VM matching the role
        for vm_name, vm_data in vms.items():
            if vm_role in vm_name:
                target_vm = vm_data
                break
        
        if not target_vm:
            console.print(f"[red]❌ No VM found for role '{vm_role}'[/red]")
            return
        
        vm_ip = target_vm.get("external_ip")
        ssh_key = Path(config.get("cloud", {}).get("ssh", {}).get("key_path", "~/.ssh/superdeploy_deploy")).expanduser()
        ssh_user = config.get("cloud", {}).get("ssh", {}).get("user", "superdeploy")
        
        console.print(f"Target: {ssh_user}@{vm_ip}")
        
        # Deploy via SSH
        deploy_script = f"""
cd /opt/superdeploy/projects/{project}/compose
echo "🔄 Pulling latest image..."
docker compose pull {app}
echo "🚀 Deploying {app}..."
docker compose up -d {app}
sleep 3
CONTAINER_NAME="{project}_{app}"
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
            "-i", str(ssh_key),
            "-o", "StrictHostKeyChecking=no",
            f"{ssh_user}@{vm_ip}",
            deploy_script
        ]
        
        if verbose:
            console.print(f"[dim]$ ssh {ssh_user}@{vm_ip} ...[/dim]")
        
        result = subprocess.run(ssh_cmd)
        
        if result.returncode == 0:
            console.print(f"\n[green]✅ {app} deployed successfully![/green]")
            
            # Show URL if domain configured
            domain = app_config.get("domain")
            if domain:
                console.print(f"🌐 https://{domain}")
        else:
            console.print(f"\n[red]❌ Deployment failed[/red]")
            return
            
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        if verbose:
            import traceback
            console.print(traceback.format_exc())

