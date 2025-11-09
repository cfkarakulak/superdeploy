"""
Generate deployment files - GitHub Actions workflows with self-hosted runners
"""

import click
from pathlib import Path
from jinja2 import Template
from cli.base import ProjectCommand


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
    branches: [production, staging]
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
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Login to Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_TOKEN }}
      
      - name: Build and push Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: |
            ${{ secrets.DOCKER_ORG }}/${{ steps.config.outputs.app }}:latest
            ${{ secrets.DOCKER_ORG }}/${{ steps.config.outputs.app }}:${{ github.sha }}
          cache-from: type=registry,ref=${{ secrets.DOCKER_ORG }}/${{ steps.config.outputs.app }}:buildcache
          cache-to: type=registry,ref=${{ secrets.DOCKER_ORG }}/${{ steps.config.outputs.app }}:buildcache,mode=max

  deploy:
    needs: build
    environment: ${{ github.ref_name }}
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
          
          # Create empty .env files for other apps to prevent docker-compose errors
          for app_dir in ../data/*/; do
            if [ -d "$app_dir" ]; then
              app_name=$(basename "$app_dir")
              env_file="../data/$app_name/.env"
              if [ ! -f "$env_file" ]; then
                echo "# Placeholder .env for $app_name" > "$env_file"
                echo "📝 Created placeholder .env for $app_name"
              fi
            fi
          done
          
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
      
      - name: Run deployment hooks
        run: |
          cd /opt/superdeploy/projects/${{ needs.build.outputs.project }}
          
          if [ ! -f config.yml ]; then
            echo "⏭️  No config.yml found, skipping hooks"
            exit 0
          fi
          
          APP_NAME="${{ needs.build.outputs.app }}"
          
          cat > /tmp/read_hooks.py <<'PYEOF'
          import yaml
          import sys
          import os
          
          try:
              with open('config.yml') as f:
                  config = yaml.safe_load(f)
              app_name = os.environ.get('APP_NAME', '')
              hooks = config.get('apps', {}).get(app_name, {}).get('hooks', {})
              after_deploy = hooks.get('after_deploy', [])
              if after_deploy:
                  for cmd in after_deploy:
                      print(cmd)
          except Exception:
              sys.exit(0)
          PYEOF
          
          HOOKS=$(APP_NAME="$APP_NAME" python3 /tmp/read_hooks.py)
          
          if [ -z "$HOOKS" ]; then
            echo "⏭️  No post-deployment hooks configured for ${{ needs.build.outputs.app }}"
            exit 0
          fi
          
          echo "🔧 Running post-deployment hooks for ${{ needs.build.outputs.app }}..."
          cd compose
          
          echo "$HOOKS" | while IFS= read -r cmd; do
            if [ -n "$cmd" ]; then
              echo "▶ Running: $cmd"
              docker compose exec -T ${{ needs.build.outputs.app }} $cmd || echo "⚠️  Hook failed: $cmd"
            fi
          done
          
          echo "✅ Post-deployment hooks completed"
{% endraw %}"""

    # Default: Python/Cara
    return """name: Deploy to {{ project }}

on:
  push:
    branches: [production, staging]
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
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Login to Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_TOKEN }}
      
      - name: Build and push Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: |
            ${{ secrets.DOCKER_ORG }}/${{ steps.config.outputs.app }}:latest
            ${{ secrets.DOCKER_ORG }}/${{ steps.config.outputs.app }}:${{ github.sha }}
          cache-from: type=registry,ref=${{ secrets.DOCKER_ORG }}/${{ steps.config.outputs.app }}:buildcache
          cache-to: type=registry,ref=${{ secrets.DOCKER_ORG }}/${{ steps.config.outputs.app }}:buildcache,mode=max

  deploy:
    needs: build
    environment: ${{ github.ref_name }}
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
          
          # Create empty .env files for other apps to prevent docker-compose errors
          for app_dir in ../data/*/; do
            if [ -d "$app_dir" ]; then
              app_name=$(basename "$app_dir")
              env_file="../data/$app_name/.env"
              if [ ! -f "$env_file" ]; then
                echo "# Placeholder .env for $app_name" > "$env_file"
                echo "📝 Created placeholder .env for $app_name"
              fi
            fi
          done
          
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
      
      - name: Run deployment hooks
        run: |
          cd /opt/superdeploy/projects/${{ needs.build.outputs.project }}
          
          if [ ! -f config.yml ]; then
            echo "⏭️  No config.yml found, skipping hooks"
            exit 0
          fi
          
          APP_NAME="${{ needs.build.outputs.app }}"
          
          cat > /tmp/read_hooks.py <<'PYEOF'
          import yaml
          import sys
          import os
          
          try:
              with open('config.yml') as f:
                  config = yaml.safe_load(f)
              app_name = os.environ.get('APP_NAME', '')
              hooks = config.get('apps', {}).get(app_name, {}).get('hooks', {})
              after_deploy = hooks.get('after_deploy', [])
              if after_deploy:
                  for cmd in after_deploy:
                      print(cmd)
          except Exception:
              sys.exit(0)
          PYEOF
          
          HOOKS=$(APP_NAME="$APP_NAME" python3 /tmp/read_hooks.py)
          
          if [ -z "$HOOKS" ]; then
            echo "⏭️  No post-deployment hooks configured for ${{ needs.build.outputs.app }}"
            exit 0
          fi
          
          echo "🔧 Running post-deployment hooks for ${{ needs.build.outputs.app }}..."
          cd compose
          
          echo "$HOOKS" | while IFS= read -r cmd; do
            if [ -n "$cmd" ]; then
              echo "▶ Running: $cmd"
              docker compose exec -T ${{ needs.build.outputs.app }} $cmd || echo "⚠️  Hook failed: $cmd"
            fi
          done
          
          echo "✅ Post-deployment hooks completed"
{% endraw %}"""


class GenerateCommand(ProjectCommand):
    """Generate deployment files with GitHub Actions workflows."""

    def __init__(self, project_name: str, app: str = None, verbose: bool = False):
        super().__init__(project_name, verbose=verbose)
        self.app = app

    def execute(self) -> None:
        """Execute generate command."""
        self.show_header(
            title="Generate Deployment Files",
            project=self.project_name,
            subtitle="GitHub Actions workflows + Self-hosted runners",
        )

        from cli.secret_manager import SecretManager
        from cli.marker_manager import MarkerManager
        from cli.utils import get_project_root

        project_root = get_project_root()
        projects_dir = project_root / "projects"
        project_dir = projects_dir / self.project_name

        # Load config
        try:
            project_config = self.config_service.load_project(self.project_name)
            self.console.print(f"[dim]✓ Loaded config: {project_dir}/config.yml[/dim]")
        except FileNotFoundError as e:
            self.console.print(f"[red]❌ {e}[/red]")
            return
        except ValueError as e:
            self.console.print(f"[red]❌ Invalid configuration: {e}[/red]")
            return

        config = project_config.raw_config

        # Validate apps
        if not config.get("apps"):
            self.console.print("[red]❌ No apps defined in config![/red]")
            return

        # Initialize secret manager
        secret_mgr = SecretManager(project_root, self.project_name)

        # Check if secrets.yml exists
        if not secret_mgr.secrets_file.exists():
            self.console.print("\n[red]❌ No secrets.yml found![/red]")
            self.console.print(
                f"[yellow]Run first:[/yellow] superdeploy {self.project_name}:init"
            )
            self.console.print("[dim]Or create manually with structure:[/dim]")
            self.console.print("[dim]secrets:[/dim]")
            self.console.print("[dim]  shared: {}[/dim]")
            self.console.print("[dim]  api: {}[/dim]")
            return

        # Load secrets
        all_secrets = secret_mgr.load_secrets()
        self.console.print("\n[dim]✓ Loaded secrets from secrets.yml[/dim]")

        # Filter apps
        apps_to_generate = config["apps"]
        if self.app:
            if self.app not in apps_to_generate:
                self.console.print(f"[red]❌ App not found: {self.app}[/red]")
                return
            apps_to_generate = {self.app: apps_to_generate[self.app]}

        self.console.print(
            f"\n[bold cyan]📝 Generating for {len(apps_to_generate)} app(s)...[/bold cyan]\n"
        )

        # Get GitHub org
        github_org = config.get("github", {}).get(
            "organization", f"{self.project_name}io"
        )

        # Generate for each app
        for app_name, app_config in apps_to_generate.items():
            app_path = Path(app_config["path"]).expanduser().resolve()

            if not app_path.exists():
                self.console.print(
                    f"  [yellow]⚠[/yellow] {app_name}: Path not found: {app_path}"
                )
                continue

            self.console.print(f"[cyan]{app_name}:[/cyan]")

            # 1. Detect app type
            app_type = _detect_app_type(app_path)
            self.console.print(f"  Type: {app_type}")

            # 2. Create .superdeploy marker
            vm_role = app_config.get("vm", "app")
            marker = MarkerManager.create_marker(
                app_path, self.project_name, app_name, vm_role
            )
            self.console.print(f"  [green]✓[/green] {marker.name}")

            # 3. Get app secrets (merged)
            app_secrets = secret_mgr.get_app_secrets(app_name)
            secret_count = len(app_secrets)
            self.console.print(f"  Secrets: {secret_count}")

            # 4. Generate GitHub workflow
            secret_var_line = f"              SECRET_VALUE='${{{{ secrets.{app_name.upper()}_ENV_JSON }}}}'"

            github_workflow_template = _get_github_workflow_template(app_type)
            github_workflow = Template(github_workflow_template).render(
                project=self.project_name,
                app=app_name,
                vm_role=vm_role,
                secret_var_line=secret_var_line,
            )
            github_dir = app_path / ".github" / "workflows"
            github_dir.mkdir(parents=True, exist_ok=True)
            (github_dir / "deploy.yml").write_text(github_workflow)
            self.console.print("  [green]✓[/green] .github/workflows/deploy.yml")

            self.console.print()

        # Summary
        self.console.print("\n[green]✅ Generation complete![/green]")
        self.console.print("\n[bold]📝 Next steps:[/bold]")
        self.console.print("\n1. Setup GitHub runners on VMs:")
        self.console.print(f"   [red]superdeploy {self.project_name}:up[/red]")
        self.console.print("\n2. Commit to app repos:")
        self.console.print("   [dim]cd <app-repo>[/dim]")
        self.console.print("   [dim]git add .superdeploy .github/[/dim]")
        self.console.print('   [dim]git commit -m "Add SuperDeploy config"[/dim]')
        self.console.print("   [dim]git push origin production[/dim]")
        self.console.print("\n3. GitHub Actions will automatically deploy!")


@click.command(name="generate")
@click.option("--app", help="Generate for specific app only")
@click.option("--verbose", "-v", is_flag=True, help="Show all command output")
def generate(project, app, verbose):
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
    cmd = GenerateCommand(project, app=app, verbose=verbose)
    cmd.run()
