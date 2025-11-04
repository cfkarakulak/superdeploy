"""SuperDeploy CLI - Monitoring command"""

import click
from rich.console import Console
from rich.panel import Panel
from cli.utils import get_project_root

console = Console()


@click.command(name="monitoring:sync")
def monitoring_sync():
    """Sync all projects to Prometheus monitoring"""
    console.print(
        Panel.fit(
            "[bold cyan]📊 Syncing Projects to Monitoring[/bold cyan]\n\n"
            "[white]This will update Prometheus with all project targets[/white]",
            border_style="cyan",
        )
    )

    project_root = get_project_root()
    
    # Load orchestrator config
    from cli.core.orchestrator_loader import OrchestratorLoader

    orchestrator_loader = OrchestratorLoader(project_root / "shared")

    try:
        orch_config = orchestrator_loader.load()
    except FileNotFoundError as e:
        console.print(f"[red]❌ {e}[/red]")
        raise SystemExit(1)

    # Get orchestrator IP
    orchestrator_ip = orch_config.get_ip()
    if not orchestrator_ip:
        console.print("[red]❌ Orchestrator not deployed yet![/red]")
        console.print("[yellow]Run: superdeploy orchestrator up[/yellow]")
        raise SystemExit(1)

    console.print(f"[dim]Orchestrator IP: {orchestrator_ip}[/dim]")

    # Get SSH config
    ssh_config = orch_config.config.get('ssh', {})
    
    # Sync all projects
    console.print("\n[cyan]🔍 Discovering projects...[/cyan]")
    
    from cli.monitoring_utils import sync_all_projects_to_monitoring
    
    projects_dir = project_root / "projects"
    
    success = sync_all_projects_to_monitoring(
        orchestrator_ip=orchestrator_ip,
        projects_dir=projects_dir,
        ssh_key_path=ssh_config.get('key_path', '~/.ssh/superdeploy_deploy'),
        ssh_user=ssh_config.get('user', 'superdeploy')
    )
    
    if success:
        console.print("\n[green]✅ All projects synced to monitoring![/green]")
        console.print(f"\n[cyan]📊 Grafana:[/cyan] http://{orchestrator_ip}:3000")
        console.print(f"[cyan]📈 Prometheus:[/cyan] http://{orchestrator_ip}:9090")
    else:
        console.print("\n[yellow]⚠️  Some projects failed to sync[/yellow]")
        raise SystemExit(1)


@click.command(name="monitoring:status")
@click.option('--project', '-p', required=True, help='Project name')
def monitoring_status(project):
    """Check monitoring status for a project"""
    console.print(
        Panel.fit(
            f"[bold cyan]📊 Monitoring Status: {project}[/bold cyan]",
            border_style="cyan",
        )
    )
    
    project_root = get_project_root()
    
    # Load orchestrator config
    from cli.core.orchestrator_loader import OrchestratorLoader

    orchestrator_loader = OrchestratorLoader(project_root / "shared")

    try:
        orch_config = orchestrator_loader.load()
    except FileNotFoundError as e:
        console.print(f"[red]❌ {e}[/red]")
        raise SystemExit(1)

    # Get orchestrator IP
    orchestrator_ip = orch_config.get_ip()
    if not orchestrator_ip:
        console.print("[red]❌ Orchestrator not deployed yet![/red]")
        raise SystemExit(1)

    # Check if project exists in Prometheus
    import subprocess
    from pathlib import Path
    
    ssh_config = orch_config.config.get('ssh', {})
    ssh_key = Path(ssh_config.get('key_path', '~/.ssh/superdeploy_deploy')).expanduser()
    ssh_user = ssh_config.get('user', 'superdeploy')
    
    # Download Prometheus config
    import tempfile
    import yaml
    
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.yml', delete=False) as tmp_file:
        tmp_path = tmp_file.name
    
    download_cmd = [
        "scp",
        "-i", str(ssh_key),
        "-o", "StrictHostKeyChecking=no",
        f"{ssh_user}@{orchestrator_ip}:/opt/superdeploy/projects/orchestrator/addons/monitoring/prometheus/prometheus.yml",
        tmp_path
    ]
    
    result = subprocess.run(download_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        console.print(f"[red]❌ Failed to check monitoring status[/red]")
        raise SystemExit(1)
    
    # Parse config
    with open(tmp_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Find project
    scrape_configs = config.get('scrape_configs', [])
    project_job_name = f'{project}-services'
    
    found = False
    for job in scrape_configs:
        if job.get('job_name') == project_job_name:
            found = True
            targets = job.get('static_configs', [{}])[0].get('targets', [])
            
            console.print(f"\n[green]✅ {project} is configured in Prometheus[/green]")
            console.print(f"\n[cyan]Targets:[/cyan]")
            for target in targets:
                console.print(f"  • {target}")
            break
    
    if not found:
        console.print(f"\n[yellow]⚠️  {project} is NOT configured in Prometheus[/yellow]")
        console.print(f"\n[cyan]Run:[/cyan] superdeploy monitoring:sync")
    
    # Cleanup
    Path(tmp_path).unlink(missing_ok=True)
    
    console.print(f"\n[cyan]📊 Grafana:[/cyan] http://{orchestrator_ip}:3000")
    console.print(f"[cyan]📈 Prometheus:[/cyan] http://{orchestrator_ip}:9090")
