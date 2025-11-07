"""
Generate deployment files - Forgejo workflows with secret hierarchy
"""

import click
from pathlib import Path
from rich.console import Console
from cli.ui_components import show_header
from jinja2 import Template

console = Console()


@click.command(name="generate")
@click.option("--project", "-p", required=True, help="Project name")
@click.option("--app", help="Generate for specific app only")
def generate(project, app):
    """
    Generate deployment files with minimal workflows

    Features:
    - Secret hierarchy (shared + app-specific)
    - Minimal workflow templates
    - .superdeploy marker files

    Example:
        superdeploy cheapa:generate
        superdeploy cheapa:generate --app api
    """
    show_header(
        title="Generate Deployment Files",
        project=project,
        subtitle="Forgejo workflows + Secret hierarchy",
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
        console.print(f"[dim]✓ Loaded config: {project_dir}/project.yml[/dim]")
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
        console.print("[yellow]Run first:[/yellow] superdeploy init -p " + project)
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

    # Template directory
    template_dir = project_root / "cli" / "templates" / "workflows"

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

        # 2. Create .superdeploy marker (with vm_role for Forgejo runner routing)
        vm_role = app_config.get("vm", "app")  # Default to 'app' if not specified
        marker = MarkerManager.create_marker(app_path, project, app_name, vm_role)
        console.print(f"  [green]✓[/green] {marker.name}")

        # 3. Get app secrets (merged)
        app_secrets = secret_mgr.get_app_secrets(app_name)
        secret_count = len(app_secrets)
        console.print(f"  Secrets: {secret_count}")

        # 4. Generate GitHub workflow
        github_workflow_template = _get_github_workflow_template(app_type)
        github_workflow = Template(github_workflow_template).render(
            project=project, app=app_name
        )
        github_dir = app_path / ".github" / "workflows"
        github_dir.mkdir(parents=True, exist_ok=True)
        (github_dir / "deploy.yml").write_text(github_workflow)
        console.print("  [green]✓[/green] .github/workflows/deploy.yml")

        console.print()

    # 5. Generate Forgejo project-specific workflow (in superdeploy repo)
    console.print(
        f"\n[bold cyan]📝 Generating Forgejo workflow for {project}...[/bold cyan]\n"
    )
    forgejo_workflow = _get_forgejo_project_workflow_template(project)
    forgejo_dir = project_root / ".forgejo" / "workflows"
    forgejo_dir.mkdir(parents=True, exist_ok=True)
    forgejo_file = forgejo_dir / f"deploy-{project}.yml"
    forgejo_file.write_text(forgejo_workflow)
    console.print(f"  [green]✓[/green] .forgejo/workflows/deploy-{project}.yml")
    console.print("  [dim]Commit this to superdeploy repo![/dim]")

    # Summary
    console.print("\n[green]✅ Generation complete![/green]")
    console.print("\n[bold]📝 Next steps:[/bold]")
    console.print("\n1. Review generated files (especially secrets.yml)")
    console.print("\n2. Commit to app repos:")
    console.print("   [dim]cd <app-repo>[/dim]")
    console.print("   [dim]git add .superdeploy .github/[/dim]")
    console.print('   [dim]git commit -m "Add SuperDeploy config"[/dim]')
    console.print("\n3. Deploy infrastructure:")
    console.print(f"   [red]superdeploy {project}:up[/red]")


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


def _load_template(template_dir: Path, app_type: str, platform: str) -> Template:
    """Generate workflow template dynamically (no external template files needed)"""

    if platform == "github":
        template_content = _get_github_workflow_template(app_type)
    elif platform == "forgejo":
        template_content = _get_forgejo_workflow_template(app_type)
    else:
        raise ValueError(f"Unknown platform: {platform}")

    return Template(template_content)


def _get_github_workflow_template(app_type: str) -> str:
    """Generate GitHub workflow template"""

    if app_type == "nextjs":
        return """name: Deploy to {{ project }}

on:
  push:
    branches: [production]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
      
      - name: Install dependencies
        run: npm ci
      
      - name: Build application
        run: npm run build
        env:
          NODE_ENV: production
      
      - name: Deploy to VM
        run: |
          echo "Deploy {{ app }} to {{ project }}"
          # Deployment logic handled by Forgejo
"""

    # Default: Python/Cara
    return """name: Deploy to {{ project }}

on:
  push:
    branches: [production]
  workflow_dispatch:

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Read app configuration
        id: config
        run: |
          PROJECT=$(grep "^project:" .superdeploy | cut -d: -f2 | xargs)
          APP=$(grep "^app:" .superdeploy | cut -d: -f2 | xargs)
          VM_ROLE=$(grep "^vm:" .superdeploy | cut -d: -f2 | xargs)
          echo "project=$PROJECT" >> $GITHUB_OUTPUT
          echo "app=$APP" >> $GITHUB_OUTPUT
          echo "vm_role=$VM_ROLE" >> $GITHUB_OUTPUT
      
      - name: Build Docker image
        run: |
          docker build -t ${{ '{{' }} secrets.DOCKER_ORG {{ '}}' }}/${{ '{{' }} steps.config.outputs.app {{ '}}' }}:latest .
          docker tag ${{ '{{' }} secrets.DOCKER_ORG {{ '}}' }}/${{ '{{' }} steps.config.outputs.app {{ '}}' }}:latest \
                     ${{ '{{' }} secrets.DOCKER_ORG {{ '}}' }}/${{ '{{' }} steps.config.outputs.app {{ '}}' }}:${{ '{{' }} github.sha {{ '}}' }}
      
      - name: Push to Docker Hub
        run: |
          echo "${{ '{{' }} secrets.DOCKER_TOKEN {{ '}}' }}" | docker login -u "${{ '{{' }} secrets.DOCKER_USERNAME {{ '}}' }}" --password-stdin
          docker push ${{ '{{' }} secrets.DOCKER_ORG {{ '}}' }}/${{ '{{' }} steps.config.outputs.app {{ '}}' }}:latest
          docker push ${{ '{{' }} secrets.DOCKER_ORG {{ '}}' }}/${{ '{{' }} steps.config.outputs.app {{ '}}' }}:${{ '{{' }} github.sha {{ '}}' }}
      
      - name: Trigger Forgejo deployment
        run: |
          # Validate required secrets
          if [ -z "${{ '{{' }} secrets.ORCHESTRATOR_IP {{ '}}' }}" ]; then
            echo "❌ ERROR: ORCHESTRATOR_IP secret not set!"
            exit 1
          fi
          
          # Build JSON payload properly
          PROJECT=${{ '{{' }} steps.config.outputs.project {{ '}}' }}
          PAYLOAD=$(cat <<EOF
          {
            "ref": "master",
            "inputs": {
              "app": "${{ '{{' }} steps.config.outputs.app {{ '}}' }}",
              "vm_role": "${{ '{{' }} steps.config.outputs.vm_role {{ '}}' }}",
              "image": "${{ '{{' }} secrets.DOCKER_ORG {{ '}}' }}/${{ '{{' }} steps.config.outputs.app {{ '}}' }}:latest",
              "git_sha": "${{ '{{' }} github.sha {{ '}}' }}"
            }
          }
          EOF
          )
          
          # Trigger project-specific Forgejo workflow
          curl -X POST \
            "http://${{ '{{' }} secrets.ORCHESTRATOR_IP {{ '}}' }}:3001/api/v1/repos/cradexco/superdeploy/actions/workflows/deploy-${PROJECT}.yml/dispatches" \
            -H "Authorization: token ${{ '{{' }} secrets.FORGEJO_PAT {{ '}}' }}" \
            -H "Content-Type: application/json" \
            -d "$PAYLOAD"
          
          echo "✅ Deployment triggered on Forgejo"
"""


def _get_forgejo_project_workflow_template(project: str) -> str:
    """Generate project-specific Forgejo workflow template"""
    return f"""# =============================================================================
# SuperDeploy - Deployment Workflow for Project: {project}
# =============================================================================
# Triggered by GitHub Actions via workflow_dispatch API
# Runs ONLY on {project} project VMs
# =============================================================================

name: Deploy Application ({project})

on:
  workflow_dispatch:
    inputs:
      app:
        description: 'App name (e.g., api, storefront)'
        required: true
        type: string
      vm_role:
        description: 'VM role (e.g., app, core)'
        required: true
        type: string
      image:
        description: 'Docker image (e.g., c100394/api:latest)'
        required: true
        type: string
      git_sha:
        description: 'Git commit SHA'
        required: true
        type: string

jobs:
  deploy:
    # Project-specific runner labels - only {project} VMs will pick this up
    runs-on: 
      - self-hosted
      - {project}
      - app
    
    env:
      PROJECT: {project}
      APP: ${{{{ inputs.app }}}}
      VM_ROLE: ${{{{ inputs.vm_role }}}}
      IMAGE: ${{{{ inputs.image }}}}
      GIT_SHA: ${{{{ inputs.git_sha }}}}
    
    steps:
      - name: Validate runner project
        run: |
          echo "🔍 Validating runner project..."
          
          # Each VM has a .project file identifying which project it runs
          if [ ! -f /opt/superdeploy/.project ]; then
            echo "❌ ERROR: /opt/superdeploy/.project not found!"
            echo "   This VM is not properly configured."
            exit 1
          fi
          
          RUNNER_PROJECT=$(cat /opt/superdeploy/.project)
          
          if [ "$RUNNER_PROJECT" != "$PROJECT" ]; then
            echo "❌ ERROR: Wrong VM!"
            echo "   This runner is for project: $RUNNER_PROJECT"
            echo "   But job is for project: $PROJECT"
            exit 1
          fi
          
          echo "✅ Correct VM for project: $RUNNER_PROJECT"
          echo ""
      
      - name: Check if app exists on this VM
        id: check_app
        run: |
          echo "🔍 Checking if $APP is configured on this VM..."
          
          cd /opt/superdeploy/projects/$PROJECT/compose
          
          # Check if app is defined in docker-compose.yml
          if docker compose config 2>/dev/null | grep -q "^  $APP:"; then
            echo "✅ App '$APP' is configured on this VM"
            echo "app_exists=true" >> $GITHUB_OUTPUT
          else
            echo "⏭️  Skipping: App '$APP' not configured on this VM"
            echo "app_exists=false" >> $GITHUB_OUTPUT
          fi
      
      - name: Display deployment info
        if: steps.check_app.outputs.app_exists == 'true'
        run: |
          echo "🚀 Deploying application..."
          echo "  Project: $PROJECT"
          echo "  App: $APP"
          echo "  VM Role: $VM_ROLE"
          echo "  Image: $IMAGE"
          echo "  Git SHA: $GIT_SHA"
          echo ""
      
      - name: Pull latest image
        if: steps.check_app.outputs.app_exists == 'true'
        run: |
          cd /opt/superdeploy/projects/$PROJECT/compose
          docker compose pull $APP
      
      - name: Restart container
        if: steps.check_app.outputs.app_exists == 'true'
        run: |
          cd /opt/superdeploy/projects/$PROJECT/compose
          docker compose up -d $APP
      
      - name: Wait for health check
        if: steps.check_app.outputs.app_exists == 'true'
        run: |
          echo "⏳ Waiting for container to be healthy..."
          sleep 5
          
          # Check container status (docker-compose uses underscore in names)
          CONTAINER_NAME="${{PROJECT}}_${{APP}}"
          STATUS=$(docker inspect -f '{{{{.State.Status}}}}' $CONTAINER_NAME 2>/dev/null || echo "not_found")
          
          if [ "$STATUS" = "running" ]; then
            echo "✅ Container is running!"
          else
            echo "❌ Container failed to start (status: $STATUS)"
            docker logs $CONTAINER_NAME --tail 50
            exit 1
          fi
      
      - name: Cleanup old images
        if: steps.check_app.outputs.app_exists == 'true'
        run: |
          docker image prune -f
          echo "🧹 Cleanup complete"
      
      - name: Deployment summary
        if: steps.check_app.outputs.app_exists == 'true'
        run: |
          echo ""
          echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
          echo "✅ Deployment successful!"
          echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
          echo "  Project: $PROJECT"
          echo "  App: $APP"
          echo "  Image: $IMAGE"
          echo "  SHA: $GIT_SHA"
          echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
          echo ""
"""


def _get_forgejo_workflow_template(app_type: str) -> str:
    """Generate Forgejo workflow template (deprecated - use project-specific workflows)"""

    if app_type == "nextjs":
        return """name: Deploy {{ app }}

on:
  push:
    branches: [production]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    container:
      image: node:20-alpine
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Install dependencies
        run: npm ci
      
      - name: Build
        run: npm run build
        env:
          NODE_ENV: production
      
      - name: Build Docker image
        run: |
          docker build -t {{ github_org }}/{{ app }}:${{ '{{' }} github.sha {{ '}}' }} .
          docker tag {{ github_org }}/{{ app }}:${{ '{{' }} github.sha {{ '}}' }} {{ github_org }}/{{ app }}:latest
      
      - name: Push to registry
        run: |
          echo "${{ '{{' }} secrets.DOCKER_TOKEN {{ '}}' }}" | docker login -u "${{ '{{' }} secrets.DOCKER_USERNAME {{ '}}' }}" --password-stdin
          docker push {{ github_org }}/{{ app }}:${{ '{{' }} github.sha {{ '}}' }}
          docker push {{ github_org }}/{{ app }}:latest
      
      - name: Deploy to VM
        run: |
          # SSH to VM and update container
          echo "Deploying {{ app }} to {{ project }}..."
"""

    # Default: Python/Cara
    return """name: Deploy {{ app }}

on:
  push:
    branches: [production]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    container:
      image: python:3.11-slim
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Install dependencies
        run: |
          pip install --upgrade pip
          pip install -r requirements.txt
      
      - name: Run tests
        run: |
          # Add your test command here
          echo "Tests passed"
      
      - name: Build Docker image
        run: |
          docker build -t {{ github_org }}/{{ app }}:${{ '{{' }} github.sha {{ '}}' }} .
          docker tag {{ github_org }}/{{ app }}:${{ '{{' }} github.sha {{ '}}' }} {{ github_org }}/{{ app }}:latest
      
      - name: Push to registry
        run: |
          echo "${{ '{{' }} secrets.DOCKER_TOKEN {{ '}}' }}" | docker login -u "${{ '{{' }} secrets.DOCKER_USERNAME {{ '}}' }}" --password-stdin
          docker push {{ github_org }}/{{ app }}:${{ '{{' }} github.sha {{ '}}' }}
          docker push {{ github_org }}/{{ app }}:latest
      
      - name: Deploy to VM
        run: |
          # SSH to VM and update container
          echo "Deploying {{ app }} to {{ project }}..."
"""
