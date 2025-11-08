#!/usr/bin/env python3
"""
Domain management commands for SuperDeploy.
Heroku-style domain registration and management.
"""

import click
import yaml
import json
import subprocess
from pathlib import Path
from rich.console import Console
from rich.table import Table
from cli.ui_components import show_header

console = Console()


@click.command(name="domain:add")
@click.option("-p", "--project", help="Project name (required for app domains)")
@click.argument("app_name")
@click.argument("domain")
def domain_add(project: str, app_name: str, domain: str):
    """
    Add a domain to an application or orchestrator service.

    Orchestrator services (grafana, prometheus) are auto-detected.
    Project apps require -p flag.

    Examples:
        # Orchestrator services (keyword-based, no -p needed)
        superdeploy domain:add grafana grafana.cheapa.io
        superdeploy domain:add prometheus prometheus.cheapa.io

        # Project apps (explicit -p required)
        superdeploy domain:add -p cheapa api api.cheapa.io
        superdeploy domain:add -p cheapa dashboard dashboard.cheapa.io
    """
    try:
        # Auto-detect orchestrator services by keyword
        ORCHESTRATOR_SERVICES = ["grafana", "prometheus"]
        is_orchestrator = app_name in ORCHESTRATOR_SERVICES

        # Validate inputs
        if is_orchestrator and project:
            console.print(f"[red]✗ '{app_name}' is an orchestrator service[/red]")
            console.print(
                "[yellow]Tip: Don't use -p flag for orchestrator services[/yellow]"
            )
            console.print(f"Usage: superdeploy domain:add {app_name} {domain}")
            raise click.Abort()

        if not is_orchestrator and not project:
            console.print(f"[red]✗ '{app_name}' requires -p <project> flag[/red]")
            console.print(
                f"Usage: superdeploy domain:add -p <project> {app_name} {domain}"
            )
            raise click.Abort()

        # Show header
        if is_orchestrator:
            show_header(
                title="Add Domain",
                details={"Service": app_name, "Domain": domain, "Type": "Orchestrator"},
                console=console,
            )
        else:
            show_header(
                title="Add Domain",
                project=project,
                app=app_name,
                details={"Domain": domain},
                console=console,
            )

        # ORCHESTRATOR MODE
        if is_orchestrator:
            # Load orchestrator config
            config_file = Path.cwd() / "shared" / "orchestrator" / "config.yml"
            if not config_file.exists():
                console.print(
                    f"[red]✗ Orchestrator config not found at {config_file}[/red]"
                )
                console.print("Run 'superdeploy orchestrator init' first")
                raise click.Abort()

            with open(config_file, "r") as f:
                config = yaml.safe_load(f)

            # Get orchestrator IP
            terraform_dir = Path.cwd() / "shared" / "terraform"
            try:
                subprocess.run(
                    ["terraform", "workspace", "select", "orchestrator"],
                    cwd=terraform_dir,
                    capture_output=True,
                    text=True,
                    check=True,
                )

                result = subprocess.run(
                    ["terraform", "output", "-json"],
                    cwd=terraform_dir,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                outputs = json.loads(result.stdout)
                vm_ip = outputs.get("orchestrator_ip", {}).get("value")

                if not vm_ip:
                    console.print("[red]✗ Could not find orchestrator IP[/red]")
                    raise click.Abort()
            except Exception as e:
                console.print(
                    "[red]✗ Failed to get orchestrator IP from Terraform[/red]"
                )
                console.print(f"[dim]Error: {e}[/dim]")
                raise click.Abort()

            # Show DNS instruction
            console.print()
            console.print(
                Panel(
                    f"[bold yellow]DNS Configuration Required[/bold yellow]\n\n"
                    f"Add the following A record to your DNS:\n\n"
                    f"[cyan]Host:[/cyan] {domain}\n"
                    f"[cyan]Type:[/cyan] A\n"
                    f"[cyan]Value:[/cyan] {vm_ip}\n"
                    f"[cyan]TTL:[/cyan] 3600 (or default)\n\n"
                    f"[dim]Note: DNS propagation may take a few minutes[/dim]",
                    title="📋 DNS Setup",
                    border_style="yellow",
                )
            )
            console.print()

            if not click.confirm(
                f"Have you added the DNS record for {domain}?", default=False
            ):
                console.print("Aborted. Add the DNS record and try again.")
                raise click.Abort()

            # Update orchestrator config
            console.print("Updating orchestrator config.yml...")
            config[app_name]["domain"] = domain

            with open(config_file, "w") as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)

            console.print(f"[green]✓ Updated {config_file}[/green]")

            # Redeploy Caddy on orchestrator
            console.print(
                "\n[bold yellow]▶[/bold yellow] Redeploying Caddy on orchestrator\n"
            )
            console.print("This will update Caddyfile and reload Caddy...")

            result = subprocess.run(
                ["superdeploy", "orchestrator", "up", "--addon", "caddy"],
                cwd=Path.cwd(),
            )

            if result.returncode != 0:
                console.print("[red]✗ Failed to redeploy Caddy[/red]")
                raise click.Abort()

            # Success message
            console.print()
            console.print(
                Panel(
                    f"[color(248)]Domain added successfully.[/color(248)]\n"
                    f"[cyan]Service:[/cyan] {app_name}\n"
                    f"[cyan]Domain:[/cyan] https://{domain}\n"
                    f"[cyan]VM:[/cyan] {vm_ip} (orchestrator)\n\n"
                    f"[dim]Caddy will automatically obtain a Let's Encrypt TLS certificate.[/dim]\n"
                    f"[dim]Your service is now accessible at: https://{domain}[/dim]",
                    title="🎉 Success",
                    border_style="green",
                )
            )
            return

        # PROJECT MODE (existing code)
        # Load project config
        project_dir = Path.cwd() / "projects" / project
        config_file = project_dir / "config.yml"

        if not config_file.exists():
            console.print(
                f"[red]✗ Project '{project}' not found at {config_file}[/red]"
            )
            raise click.Abort()

        # Read config
        with open(config_file, "r") as f:
            config = yaml.safe_load(f)

        # Find app
        apps = config.get("apps", {})
        if app_name not in apps:
            console.print(
                f"[red]✗ App '{app_name}' not found in project '{project}'[/red]"
            )
            console.print(f"Available apps: {', '.join(apps.keys())}")
            raise click.Abort()

        app = apps[app_name]
        vm_role = app.get("vm")

        # Get VM IP from Terraform
        terraform_dir = Path.cwd() / "shared" / "terraform"
        try:
            # Select workspace first
            subprocess.run(
                ["terraform", "workspace", "select", project],
                cwd=terraform_dir,
                capture_output=True,
                text=True,
                check=True,
            )

            # Get outputs
            result = subprocess.run(
                ["terraform", "output", "-json"],
                cwd=terraform_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            outputs = json.loads(result.stdout)
            vms_by_role = outputs.get("vms_by_role", {}).get("value", {})

            # Find VM IP
            vm_ip = None
            role_vms = vms_by_role.get(vm_role, [])
            if role_vms:
                vm_ip = role_vms[0].get("external_ip")

            if not vm_ip:
                console.print(f"[red]✗ Could not find IP for VM role '{vm_role}'[/red]")
                console.print(f"[dim]Available roles: {list(vms_by_role.keys())}[/dim]")
                raise click.Abort()
        except subprocess.CalledProcessError as e:
            console.print("[red]✗ Failed to get VM IP from Terraform[/red]")
            console.print(f"[dim]Error: {e.stderr}[/dim]")
            raise click.Abort()
        except Exception as e:
            console.print(f"[red]✗ Failed to get VM IP: {e}[/red]")
            raise click.Abort()

        # Show DNS instruction
        console.print()
        console.print(
            Panel(
                f"[bold yellow]DNS Configuration Required[/bold yellow]\n\n"
                f"Add the following A record to your DNS:\n\n"
                f"[cyan]Host:[/cyan] {domain}\n"
                f"[cyan]Type:[/cyan] A\n"
                f"[cyan]Value:[/cyan] {vm_ip}\n"
                f"[cyan]TTL:[/cyan] 3600 (or default)\n\n"
                f"[dim]Note: DNS propagation may take a few minutes[/dim]",
                title="📋 DNS Setup",
                border_style="yellow",
            )
        )
        console.print()

        # Ask for confirmation
        if not click.confirm(
            f"Have you added the DNS record for {domain}?", default=False
        ):
            console.print("Aborted. Add the DNS record and try again.")
            raise click.Abort()

        # Update config.yml
        console.print("Updating config.yml...")
        apps[app_name]["domain"] = domain

        with open(config_file, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        console.print(f"[green]✓ Updated {config_file}[/green]")

        # Redeploy Caddy addon
        console.print(
            "\n[bold yellow]▶[/bold yellow] Redeploying Caddy with new domain\n"
        )
        console.print("This will update Caddyfile and reload Caddy...")

        # Run superdeploy up with caddy addon only
        result = subprocess.run(
            [
                "superdeploy",
                f"{project}:up",
                "--skip-terraform",
                "--addon",
                "caddy",
            ],
            cwd=Path.cwd(),
        )

        if result.returncode != 0:
            console.print("[red]✗ Failed to redeploy Caddy[/red]")
            raise click.Abort()

        # Success message
        console.print()
        console.print(
            Panel(
                f"[color(248)]Domain added successfully.[/color(248)]\n"
                f"[cyan]App:[/cyan] {app_name}\n"
                f"[cyan]Domain:[/cyan] https://{domain}\n"
                f"[cyan]VM:[/cyan] {vm_ip} ({vm_role})\n\n"
                f"[dim]Caddy will automatically obtain a Let's Encrypt TLS certificate.[/dim]\n"
                f"[dim]Your app is now accessible at: https://{domain}[/dim]",
                title="🎉 Success",
                border_style="green",
            )
        )

    except Exception as e:
        console.print(f"[red]✗ Domain add failed: {e}[/red]")
        raise


@click.command(name="domain:list")
@click.option("-p", "--project", help="Project name (show only this project)")
def domain_list(project: str):
    """
    List all domains (orchestrator + all projects).

    Without -p flag: shows ALL domains (orchestrator + all projects)
    With -p flag: shows only that project's domains

    Examples:
        superdeploy domain:list              # all domains
        superdeploy domain:list -p cheapa    # only cheapa project
    """
    # Show header
    if project:
        show_header(
            title="Domain List",
            project=project,
            console=console,
        )
    else:
        show_header(
            title="Domain List",
            subtitle="All domains across orchestrator and projects",
            console=console,
        )

    try:
        # Get all available projects
        projects_dir = Path.cwd() / "projects"
        all_projects = (
            [
                d.name
                for d in projects_dir.iterdir()
                if d.is_dir() and (d / "config.yml").exists()
            ]
            if projects_dir.exists()
            else []
        )

        # If -p specified, show only that project
        if project:
            if project not in all_projects:
                console.print(f"[red]✗ Project '{project}' not found[/red]")
                raise click.Abort()
            projects_to_show = [project]
        else:
            # Show all projects
            projects_to_show = all_projects

        # Build single unified table
        from rich.box import ROUNDED

        main_table = Table(
            title="[bold white]All Domains[/bold white]",
            show_header=True,
            header_style="bold magenta",
            box=ROUNDED,
            title_style="bold cyan",
            title_justify="left",
            border_style="cyan",
            padding=(0, 1),
        )
        main_table.add_column("Type", style="cyan", width=15)
        main_table.add_column("Service/App", style="yellow", width=20)
        main_table.add_column("Domain", style="green", width=30)
        main_table.add_column("VM/Role", style="magenta", width=15)
        main_table.add_column("IP", style="blue")

        # ═══════════════════════════════════════════════════════
        # ORCHESTRATOR DOMAINS
        # ═══════════════════════════════════════════════════════
        if not project:  # Only show orchestrator when listing all
            # Load orchestrator config
            config_file = Path.cwd() / "shared" / "orchestrator" / "config.yml"
            if config_file.exists():
                with open(config_file, "r") as f:
                    config = yaml.safe_load(f)

                # Get orchestrator IP
                terraform_dir = Path.cwd() / "shared" / "terraform"
                try:
                    subprocess.run(
                        ["terraform", "workspace", "select", "orchestrator"],
                        cwd=terraform_dir,
                        capture_output=True,
                        text=True,
                        check=True,
                    )

                    result = subprocess.run(
                        ["terraform", "output", "-json"],
                        cwd=terraform_dir,
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    outputs = json.loads(result.stdout)
                    vm_ip = outputs.get("orchestrator_ip", {}).get("value", "-")
                except:
                    vm_ip = "-"

                # Add orchestrator section header
                main_table.add_row(
                    "[bold yellow]Orchestrator[/bold yellow]", "", "", "", ""
                )

                services = ["grafana", "prometheus"]
                for service in services:
                    service_config = config.get(service, {})
                    domain = service_config.get("domain", "") or "-"
                    main_table.add_row(
                        "  Service", f"  {service}", domain, "orchestrator", vm_ip
                    )

        # ═══════════════════════════════════════════════════════
        # PROJECT DOMAINS
        # ═══════════════════════════════════════════════════════
        terraform_dir = Path.cwd() / "shared" / "terraform"

        for proj_name in projects_to_show:
            project_dir = Path.cwd() / "projects" / proj_name
            config_file = project_dir / "config.yml"

            if not config_file.exists():
                continue

            with open(config_file, "r") as f:
                config = yaml.safe_load(f)

            # Get VM IPs for this project
            vms_by_role = {}
            try:
                # Select workspace
                subprocess.run(
                    ["terraform", "workspace", "select", proj_name],
                    cwd=terraform_dir,
                    capture_output=True,
                    text=True,
                    check=True,
                )

                # Get outputs
                result = subprocess.run(
                    ["terraform", "output", "-json"],
                    cwd=terraform_dir,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                outputs = json.loads(result.stdout)
                vms_by_role = outputs.get("vms_by_role", {}).get("value", {})
            except:
                pass

            # Add project section header
            main_table.add_row(
                f"[bold yellow]Project: {proj_name.title()}[/bold yellow]",
                "",
                "",
                "",
                "",
            )

            apps = config.get("apps", {})
            for app_name, app_config in apps.items():
                domain = app_config.get("domain", "") or "-"
                vm_role = app_config.get("vm", "-")

                # Find VM IP
                vm_ip = "-"
                role_vms = vms_by_role.get(vm_role, [])
                if role_vms:
                    vm_ip = role_vms[0].get("external_ip", "-")

                main_table.add_row("  App", f"  {app_name}", domain, vm_role, vm_ip)

        console.print()
        console.print(main_table)
        console.print()

    except Exception as e:
        console.print(f"[red]✗ Failed to list domains: {e}[/red]")
        raise


@click.command(name="domain:remove")
@click.option("-p", "--project", help="Project name (required for app domains)")
@click.argument("app_name")
def domain_remove(project: str, app_name: str):
    """
    Remove a domain from an application or orchestrator service.

    Orchestrator services (grafana, prometheus) are auto-detected.
    Project apps require -p flag.

    Examples:
        superdeploy domain:remove grafana                # orchestrator
        superdeploy domain:remove -p cheapa api          # project app
    """
    try:
        # Auto-detect orchestrator services by keyword
        ORCHESTRATOR_SERVICES = ["grafana", "prometheus"]
        is_orchestrator = app_name in ORCHESTRATOR_SERVICES

        # Validate inputs
        if is_orchestrator and project:
            console.print(f"[red]✗ '{app_name}' is an orchestrator service[/red]")
            console.print(
                "[yellow]Tip: Don't use -p flag for orchestrator services[/yellow]"
            )
            console.print(f"Usage: superdeploy domain:remove {app_name}")
            raise click.Abort()

        if not is_orchestrator and not project:
            console.print(f"[red]✗ '{app_name}' requires -p <project> flag[/red]")
            console.print(f"Usage: superdeploy domain:remove -p <project> {app_name}")
            raise click.Abort()

        # Show header
        if is_orchestrator:
            show_header(
                title="Remove Domain",
                details={"Service": app_name, "Type": "Orchestrator"},
                console=console,
            )
        else:
            show_header(
                title="Remove Domain",
                project=project,
                app=app_name,
                console=console,
            )

        # ORCHESTRATOR MODE
        if is_orchestrator:
            # Load orchestrator config
            config_file = Path.cwd() / "shared" / "orchestrator" / "config.yml"
            if not config_file.exists():
                console.print("[red]✗ Orchestrator config not found[/red]")
                raise click.Abort()

            with open(config_file, "r") as f:
                config = yaml.safe_load(f)

            service_config = config.get(app_name, {})
            old_domain = service_config.get("domain")

            if not old_domain:
                console.print(
                    f"[yellow]Service '{app_name}' has no domain configured[/yellow]"
                )
                return

            # Confirm removal
            if not click.confirm(
                f"Remove domain '{old_domain}' from {app_name}?", default=False
            ):
                console.print("Aborted")
                raise click.Abort()

            # Remove domain (set to empty string)
            config[app_name]["domain"] = ""

            with open(config_file, "w") as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)

            console.print(f"[green]✓ Removed domain from {config_file}[/green]")

            # Redeploy Caddy on orchestrator
            console.print(
                "\n[bold yellow]▶[/bold yellow] Redeploying Caddy on orchestrator\n"
            )

            result = subprocess.run(
                ["superdeploy", "orchestrator", "up", "--addon", "caddy"],
                cwd=Path.cwd(),
            )

            if result.returncode != 0:
                console.print("[red]✗ Failed to redeploy Caddy[/red]")
                raise click.Abort()

            console.print(
                f"[green]✓ Domain '{old_domain}' removed from {app_name}[/green]"
            )
            console.print("Service now accessible via port-based routing only")
            return

        # PROJECT MODE
        # Load project config
        project_dir = Path.cwd() / "projects" / project
        config_file = project_dir / "config.yml"

        if not config_file.exists():
            console.print(f"[red]✗ Project '{project}' not found[/red]")
            raise click.Abort()

        with open(config_file, "r") as f:
            config = yaml.safe_load(f)

        apps = config.get("apps", {})
        if app_name not in apps:
            console.print(f"[red]✗ App '{app_name}' not found[/red]")
            raise click.Abort()

        app = apps[app_name]
        old_domain = app.get("domain")

        if not old_domain:
            console.print(f"[yellow]App '{app_name}' has no domain configured[/yellow]")
            return

        # Confirm removal
        if not click.confirm(
            f"Remove domain '{old_domain}' from {app_name}?", default=False
        ):
            console.print("Aborted")
            raise click.Abort()

        # Remove domain
        del apps[app_name]["domain"]

        with open(config_file, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        console.print(f"[green]✓ Removed domain from {config_file}[/green]")

        # Redeploy Caddy
        console.print("\n[bold yellow]▶[/bold yellow] Redeploying Caddy\n")

        result = subprocess.run(
            [
                "superdeploy",
                "up",
                "-p",
                project,
                "--skip-terraform",
                "--addon",
                "caddy",
            ],
            cwd=Path.cwd(),
        )

        if result.returncode != 0:
            console.print("[red]✗ Failed to redeploy Caddy[/red]")
            raise click.Abort()

        console.print(f"[green]✓ Domain '{old_domain}' removed from {app_name}[/green]")
        console.print("App now accessible via port-based routing only")

    except Exception as e:
        console.print(f"[red]✗ Failed to remove domain: {e}[/red]")
        raise
