"""
Generate deployment files - GitHub Actions workflows with self-hosted runners
"""

import click
from pathlib import Path
from rich.console import Console
from cli.ui_components import show_header
from jinja2 import Template

console = Console()


@click.command(name="generate")
@click.option("--app", help="Generate for specific app only")
def generate(project, app):
    """
    Generate deployment files with GitHub Actions workflows

    Features:
    - Secret hierarchy (shared + app-specific)
    - GitHub self-hosted runners
    - .superdeploy marker files
    - Smart VM selection based on labels

    Example:
        superdeploy cheapa:generate
        superdeploy cheapa:generate --app api
    """
    show_header(
        title="Generate Deployment Files",
        project=project,
        subtitle="GitHub Actions workflows + Self-hosted runners",
        console=console,
    )

    from cli.utils import get_project_root
    from cli.core.config_loader import ConfigLoader
    from cli.secret_manager import SecretManager
    from cli.marker_manager import MarkerManager

    project_root = get_project_root()
    projects_dir = project_root / "projects"
    project_dir = projects_dir / project

    # Load config
    config_loader = ConfigLoader(projects_dir)

    try:
        project_config = config_loader.load_project(project)
        console.print(f"[dim]✓ Loaded config: {project_dir}/config.yml[/dim]")
    except FileNotFoundError as e:
        console.print(f"[red]❌ {e}[/red]")
        return
    except ValueError as e:
        console.print(f"[red]❌ Invalid configuration: {e}[/red]")
        return

    config = project_config.raw_config

    # Validate apps
    if not config.get("apps"):
        console.print("[red]❌ No apps defined in config![/red]")
        return

    # Initialize secret manager
    secret_mgr = SecretManager(project_root, project)

    # Check if secrets.yml exists
    if not secret_mgr.secrets_file.exists():
        console.print("\n[red]❌ No secrets.yml found![/red]")
        console.print("[yellow]Run first:[/yellow] superdeploy :init" + project)
        console.print("[dim]Or create manually with structure:[/dim]")
        console.print("[dim]secrets:[/dim]")
        console.print("[dim]  shared: {}[/dim]")
        console.print("[dim]  api: {}[/dim]")
        return

    # Load secrets
    all_secrets = secret_mgr.load_secrets()
    console.print("\n[dim]✓ Loaded secrets from secrets.yml[/dim]")

    # Filter apps
    apps_to_generate = config["apps"]
    if app:
        if app not in apps_to_generate:
            console.print(f"[red]❌ App not found: {app}[/red]")
            return
        apps_to_generate = {app: apps_to_generate[app]}

    console.print(
        f"\n[bold cyan]📝 Generating for {len(apps_to_generate)} app(s)...[/bold cyan]\n"
    )

    # Get GitHub org
    github_org = config.get("github", {}).get("organization", f"{project}io")

    # Generate for each app
    for app_name, app_config in apps_to_generate.items():
        app_path = Path(app_config["path"]).expanduser().resolve()

        if not app_path.exists():
            console.print(
                f"  [yellow]⚠[/yellow] {app_name}: Path not found: {app_path}"
            )
            continue

        console.print(f"[cyan]{app_name}:[/cyan]")

        # 1. Detect app type
        app_type = _detect_app_type(app_path)
        console.print(f"  Type: {app_type}")

        # 2. Create .superdeploy marker (with vm_role for GitHub runner routing)
        vm_role = app_config.get("vm", "app")  # Default to 'app' if not specified
        marker = MarkerManager.create_marker(app_path, project, app_name, vm_role)
        console.print(f"  [green]✓[/green] {marker.name}")

        # 3. Get app secrets (merged)
        app_secrets = secret_mgr.get_app_secrets(app_name)
        secret_count = len(app_secrets)
        console.print(f"  Secrets: {secret_count}")

        # 4. Generate GitHub workflow
        # Build the secret variable line dynamically (can't use Jinja2 inside raw block)
        secret_var_line = f"              SECRET_VALUE='${{{{ secrets.{app_name.upper()}_ENV_JSON }}}}'"

        github_workflow_template = _get_github_workflow_template(app_type)
        github_workflow = Template(github_workflow_template).render(
            project=project,
            app=app_name,
            vm_role=vm_role,
            secret_var_line=secret_var_line,
        )
        github_dir = app_path / ".github" / "workflows"
        github_dir.mkdir(parents=True, exist_ok=True)
        (github_dir / "deploy.yml").write_text(github_workflow)
        console.print("  [green]✓[/green] .github/workflows/deploy.yml")

        console.print()

    # Summary
    console.print("\n[green]✅ Generation complete![/green]")
    console.print("\n[bold]📝 Next steps:[/bold]")
    console.print("\n1. Setup GitHub runners on VMs:")
    console.print(f"   [red]superdeploy {project}:up[/red]")
    console.print("\n2. Commit to app repos:")
    console.print("   [dim]cd <app-repo>[/dim]")
    console.print("   [dim]git add .superdeploy .github/[/dim]")
    console.print('   [dim]git commit -m "Add SuperDeploy config"[/dim]')
    console.print("   [dim]git push origin production[/dim]")
    console.print("\n3. GitHub Actions will automatically deploy!")


def _detect_app_type(app_path: Path) -> str:
    """Detect app type from files"""

    # Next.js
    if (app_path / "next.config.js").exists() or (app_path / "next.config.ts").exists():
        return "nextjs"

    # Python/Cara
    if (app_path / "requirements.txt").exists():
        requirements = (app_path / "requirements.txt").read_text()
        if "cara" in requirements.lower():
            return "python"  # Cara framework
        return "python"

    # Default
    return "python"


def _get_github_workflow_template(app_type: str) -> str:
    """Generate GitHub workflow template for direct deployment with self-hosted runners"""

    if app_type == "nextjs":
        return """name: Deploy to {{ project }}

on:
  push:
    branches: [production]
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    outputs:
{% raw %}      project: ${{ steps.config.outputs.project }}
      app: ${{ steps.config.outputs.app }}
      vm_role: ${{ steps.config.outputs.vm_role }}
{% endraw %}    
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
      
      - name: Read app configuration
        id: config
        run: |
          PROJECT=$(grep "^project:" .superdeploy | cut -d: -f2 | xargs)
          APP=$(grep "^app:" .superdeploy | cut -d: -f2 | xargs)
          VM_ROLE=$(grep "^vm:" .superdeploy | cut -d: -f2 | xargs)
{% raw %}          echo "project=$PROJECT" >> $GITHUB_OUTPUT
          echo "app=$APP" >> $GITHUB_OUTPUT
          echo "vm_role=$VM_ROLE" >> $GITHUB_OUTPUT
      
      - name: Build Docker image
        run: |
          docker build -t ${{ secrets.DOCKER_ORG }}/${{ steps.config.outputs.app }}:latest .
          docker tag ${{ secrets.DOCKER_ORG }}/${{ steps.config.outputs.app }}:latest ${{ secrets.DOCKER_ORG }}/${{ steps.config.outputs.app }}:${{ github.sha }}
      
      - name: Push to Docker Hub
        run: |
          echo "${{ secrets.DOCKER_TOKEN }}" | docker login -u "${{ secrets.DOCKER_USERNAME }}" --password-stdin
          docker push ${{ secrets.DOCKER_ORG }}/${{ steps.config.outputs.app }}:latest
          docker push ${{ secrets.DOCKER_ORG }}/${{ steps.config.outputs.app }}:${{ github.sha }}

  deploy:
    needs: build
    runs-on: 
      - self-hosted
      - superdeploy
      - ${{ needs.build.outputs.project }}
      - ${{ needs.build.outputs.vm_role }}
    
    steps:
      - name: Validate runner
        run: |
          echo "🔍 Validating deployment environment..."
          
          if [ ! -f /opt/superdeploy/.project ]; then
            echo "❌ ERROR: /opt/superdeploy/.project not found!"
            exit 1
          fi
          
          RUNNER_PROJECT=$(cat /opt/superdeploy/.project)
          if [ "$RUNNER_PROJECT" != "${{ needs.build.outputs.project }}" ]; then
            echo "❌ ERROR: Wrong project! Expected ${{ needs.build.outputs.project }}, got $RUNNER_PROJECT"
            exit 1
          fi
          
          echo "✅ Correct VM for project: $RUNNER_PROJECT"
      
      - name: Create .env from merged secrets
        run: |
          APP_NAME="${{ needs.build.outputs.app }}"
          ENV_DIR="/opt/superdeploy/projects/${{ needs.build.outputs.project }}/data/$APP_NAME"
          
          echo "📝 Creating .env from ${APP_NAME^^}_ENV_JSON..."
{% endraw %}          
          # GitHub Actions cannot dynamically access secrets
          # The secret is created by: superdeploy sync (merges app .env + secrets.yml)
          case "$APP_NAME" in
            {{ app }})
{{ secret_var_line }}
              ;;
            *)
              echo "❌ App '$APP_NAME' not configured in workflow"
              exit 1
              ;;
          esac
{% raw %}          
          # Convert JSON to .env format
          echo "$SECRET_VALUE" | jq -r 'to_entries[] | "\(.key)=\(.value)"' > /tmp/final.env
          
          # Write to VM directory
          sudo mkdir -p "$ENV_DIR"
          sudo cp /tmp/final.env "$ENV_DIR/.env"
          sudo chown superdeploy:superdeploy "$ENV_DIR/.env"
          sudo chmod 600 "$ENV_DIR/.env"
          
          echo "✅ Environment file created at $ENV_DIR/.env"
          echo "📊 Total variables: $(wc -l < "$ENV_DIR/.env")"
      
      - name: Deploy application
        run: |
          cd /opt/superdeploy/projects/${{ needs.build.outputs.project }}/compose
          
          # Check if this specific service exists in docker-compose.yml (without running full config validation)
          if ! grep -q "^  ${{ needs.build.outputs.app }}:" docker-compose.yml; then
            echo "⏭️  Skipping: App not configured on this VM"
            exit 0
          fi
          
          echo "🚀 Deploying ${{ needs.build.outputs.app }}..."
          
          docker compose pull ${{ needs.build.outputs.app }}
          docker compose up -d ${{ needs.build.outputs.app }}
          
          sleep 5
          
          CONTAINER_NAME="${{ needs.build.outputs.project }}_${{ needs.build.outputs.app }}"
          STATUS=$(docker inspect -f '{{.State.Status}}' $CONTAINER_NAME 2>/dev/null || echo "not_found")
          
          if [ "$STATUS" = "running" ]; then
            echo "✅ Deployment successful!"
            docker image prune -f
          else
            echo "❌ Container failed to start"
            docker logs $CONTAINER_NAME --tail 50
            exit 1
          fi
{% endraw %}"""

    # Default: Python/Cara
    return """name: Deploy to {{ project }}

on:
  push:
    branches: [production]
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    outputs:
{% raw %}      project: ${{ steps.config.outputs.project }}
      app: ${{ steps.config.outputs.app }}
      vm_role: ${{ steps.config.outputs.vm_role }}
{% endraw %}    
    steps:
      - uses: actions/checkout@v4
      
      - name: Read app configuration
        id: config
        run: |
          PROJECT=$(grep "^project:" .superdeploy | cut -d: -f2 | xargs)
          APP=$(grep "^app:" .superdeploy | cut -d: -f2 | xargs)
          VM_ROLE=$(grep "^vm:" .superdeploy | cut -d: -f2 | xargs)
{% raw %}          echo "project=$PROJECT" >> $GITHUB_OUTPUT
          echo "app=$APP" >> $GITHUB_OUTPUT
          echo "vm_role=$VM_ROLE" >> $GITHUB_OUTPUT
      
      - name: Build Docker image
        run: |
          docker build -t ${{ secrets.DOCKER_ORG }}/${{ steps.config.outputs.app }}:latest .
          docker tag ${{ secrets.DOCKER_ORG }}/${{ steps.config.outputs.app }}:latest ${{ secrets.DOCKER_ORG }}/${{ steps.config.outputs.app }}:${{ github.sha }}
      
      - name: Push to Docker Hub
        run: |
          echo "${{ secrets.DOCKER_TOKEN }}" | docker login -u "${{ secrets.DOCKER_USERNAME }}" --password-stdin
          docker push ${{ secrets.DOCKER_ORG }}/${{ steps.config.outputs.app }}:latest
          docker push ${{ secrets.DOCKER_ORG }}/${{ steps.config.outputs.app }}:${{ github.sha }}

  deploy:
    needs: build
    runs-on: 
      - self-hosted
      - superdeploy
      - ${{ needs.build.outputs.project }}
      - ${{ needs.build.outputs.vm_role }}
    
    steps:
      - name: Validate runner
        run: |
          echo "🔍 Validating deployment environment..."
          
          if [ ! -f /opt/superdeploy/.project ]; then
            echo "❌ ERROR: /opt/superdeploy/.project not found!"
            exit 1
          fi
          
          RUNNER_PROJECT=$(cat /opt/superdeploy/.project)
          if [ "$RUNNER_PROJECT" != "${{ needs.build.outputs.project }}" ]; then
            echo "❌ ERROR: Wrong project! Expected ${{ needs.build.outputs.project }}, got $RUNNER_PROJECT"
            exit 1
          fi
          
          echo "✅ Correct VM for project: $RUNNER_PROJECT"
      
      - name: Create .env from merged secrets
        run: |
          APP_NAME="${{ needs.build.outputs.app }}"
          ENV_DIR="/opt/superdeploy/projects/${{ needs.build.outputs.project }}/data/$APP_NAME"
          
          echo "📝 Creating .env from ${APP_NAME^^}_ENV_JSON..."
{% endraw %}          
          # GitHub Actions cannot dynamically access secrets
          # The secret is created by: superdeploy sync (merges app .env + secrets.yml)
          case "$APP_NAME" in
            {{ app }})
{{ secret_var_line }}
              ;;
            *)
              echo "❌ App '$APP_NAME' not configured in workflow"
              exit 1
              ;;
          esac
{% raw %}          
          # Convert JSON to .env format
          echo "$SECRET_VALUE" | jq -r 'to_entries[] | "\(.key)=\(.value)"' > /tmp/final.env
          
          # Write to VM directory
          sudo mkdir -p "$ENV_DIR"
          sudo cp /tmp/final.env "$ENV_DIR/.env"
          sudo chown superdeploy:superdeploy "$ENV_DIR/.env"
          sudo chmod 600 "$ENV_DIR/.env"
          
          echo "✅ Environment file created at $ENV_DIR/.env"
          echo "📊 Total variables: $(wc -l < "$ENV_DIR/.env")"
      
      - name: Deploy application
        run: |
          cd /opt/superdeploy/projects/${{ needs.build.outputs.project }}/compose
          
          # Check if this specific service exists in docker-compose.yml (without running full config validation)
          if ! grep -q "^  ${{ needs.build.outputs.app }}:" docker-compose.yml; then
            echo "⏭️  Skipping: App not configured on this VM"
            exit 0
          fi
          
          echo "🚀 Deploying ${{ needs.build.outputs.app }}..."
          
          docker compose pull ${{ needs.build.outputs.app }}
          docker compose up -d ${{ needs.build.outputs.app }}
          
          sleep 5
          
          CONTAINER_NAME="${{ needs.build.outputs.project }}_${{ needs.build.outputs.app }}"
          STATUS=$(docker inspect -f '{{.State.Status}}' $CONTAINER_NAME 2>/dev/null || echo "not_found")
          
          if [ "$STATUS" = "running" ]; then
            echo "✅ Deployment successful!"
            docker image prune -f
          else
            echo "❌ Container failed to start"
            docker logs $CONTAINER_NAME --tail 50
            exit 1
          fi
{% endraw %}"""
