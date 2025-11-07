"""
Generate deployment files V2 - with secret hierarchy and minimal workflows
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
        superdeploy generate -p cheapa
        superdeploy generate -p cheapa --app api
    """
    show_header(
        title="Generate Deployment Files V2",
        project=project,
        subtitle="Minimal workflows + Secret hierarchy",
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

        # 2. Create .superdeploy marker
        marker = MarkerManager.create_marker(app_path, project, app_name)
        console.print(f"  [green]✓[/green] {marker.name}")

        # 3. Get app secrets (merged)
        app_secrets = secret_mgr.get_app_secrets(app_name)
        secret_count = len(app_secrets)
        console.print(f"  Secrets: {secret_count}")

        # 4. Generate GitHub workflow (minimal)
        github_template = _load_template(template_dir, app_type, "github")
        github_workflow = github_template.render(
            project=project, app=app_name, github_org=github_org
        )
        github_dir = app_path / ".github" / "workflows"
        github_dir.mkdir(parents=True, exist_ok=True)
        (github_dir / "deploy.yml").write_text(github_workflow)
        console.print("  [green]✓[/green] .github/workflows/deploy.yml")

        # 5. Generate Forgejo workflow (minimal)
        forgejo_template = _load_template(template_dir, app_type, "forgejo")
        forgejo_workflow = forgejo_template.render(
            project=project, app=app_name, github_org=github_org
        )
        forgejo_dir = app_path / ".forgejo" / "workflows"
        forgejo_dir.mkdir(parents=True, exist_ok=True)
        (forgejo_dir / "deploy.yml").write_text(forgejo_workflow)
        console.print("  [green]✓[/green] .forgejo/workflows/deploy.yml")

        console.print()

    # Summary
    console.print("[green]✅ Generation complete![/green]")
    console.print("\n[bold]📝 Next steps:[/bold]")
    console.print("\n1. Review generated files (especially secrets.yml)")
    console.print("\n2. Commit to app repos:")
    console.print("   [dim]cd <app-repo>[/dim]")
    console.print("   [dim]git add .superdeploy .github/ .forgejo/[/dim]")
    console.print('   [dim]git commit -m "Add SuperDeploy config"[/dim]')
    console.print("\n3. Deploy infrastructure:")
    console.print(f"   [red]superdeploy up -p {project}[/red]")


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
    """Load Jinja2 template"""

    template_file = template_dir / f"{app_type}-{platform}.yml.j2"

    if not template_file.exists():
        # Fallback to python template
        template_file = template_dir / f"python-{platform}.yml.j2"

    with open(template_file, "r") as f:
        return Template(f.read())
