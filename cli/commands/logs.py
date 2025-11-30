"""
Logs Command - View logs via Loki centralized log aggregation
"""

import click
import sys
import time
import requests
import subprocess
import socket
from datetime import datetime
from typing import Optional
from rich.console import Console
from pathlib import Path


console = Console()


@click.command("logs")
@click.option(
    "-p",
    "--project",
    help="Project name (auto-injected when using namespace syntax)",
)
@click.option("-a", "--app", help="Filter by app name (e.g., api, worker)")
@click.option("-c", "--container", help="Filter by container name")
@click.option(
    "--level",
    type=click.Choice(["debug", "info", "warn", "error"], case_sensitive=False),
    help="Filter by log level",
)
@click.option(
    "-f",
    "--follow",
    is_flag=True,
    default=True,
    help="Stream logs in real-time (default: true, use --no-follow to disable)",
)
@click.option("--no-follow", is_flag=True, help="Disable real-time streaming")
@click.option("--since", default="5m", help="Show logs since (e.g., 5m, 1h, 2d)")
@click.option("-n", "--lines", type=int, default=100, help="Number of lines")
def logs(project, app, container, level, follow, no_follow, since, lines):
    """📜 View logs via Loki (centralized log aggregation)"""

    if not project:
        console.print("[red]✗ Project name required[/red]")
        console.print("[dim]Usage: superdeploy <project>:logs[/dim]")
        sys.exit(1)

    # Handle no-follow flag
    if no_follow:
        follow = False

    try:
        # Get orchestrator IP from database (shared orchestrator project)
        from cli.database import get_db_session, Project

        db = get_db_session()
        try:
            # First check if project exists
            project_record = db.query(Project).filter(Project.name == project).first()
            if not project_record:
                console.print(f"[red]✗ Project '{project}' not found in database[/red]")
                sys.exit(1)

            # Get orchestrator IP from 'orchestrator' project (shared)
            orchestrator_project = (
                db.query(Project).filter(Project.name == "orchestrator").first()
            )
            orchestrator_ip = None
            if orchestrator_project and orchestrator_project.actual_state:
                orchestrator_ip = orchestrator_project.actual_state.get(
                    "orchestrator_ip"
                )

            if not orchestrator_ip:
                console.print("[red]✗ Orchestrator not deployed[/red]")
                console.print("[dim]Run: superdeploy orchestrator:up[/dim]")
                sys.exit(1)
        finally:
            db.close()

        # Create SSH tunnel to Loki (port 3100 is not publicly accessible)
        local_port = _find_free_port()
        ssh_key = Path.home() / ".ssh" / "superdeploy_deploy"

        console.print(f"[dim]Creating SSH tunnel to {orchestrator_ip}:3100...[/dim]")

        tunnel_cmd = [
            "ssh",
            "-N",
            "-L",
            f"{local_port}:localhost:3100",
            "-i",
            str(ssh_key),
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-o",
            "LogLevel=ERROR",
            f"superdeploy@{orchestrator_ip}",
        ]

        tunnel_proc = subprocess.Popen(
            tunnel_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

        # Wait for tunnel to establish
        max_retries = 10
        for i in range(max_retries):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex(("localhost", local_port))
                sock.close()
                if result == 0:
                    break
            except:
                pass
            time.sleep(0.5)
        else:
            console.print("[red]✗ SSH tunnel failed to establish[/red]")
            tunnel_proc.terminate()
            sys.exit(1)

        # Initialize Loki via tunnel
        loki = LokiClient(f"http://localhost:{local_port}", project)

        # Build query
        query = loki.build_query(app=app, container=container, level=level)

        console.print("[cyan]📜 Loki logs[/cyan]")
        console.print(f"[dim]{query}[/dim]\n")

        # Fetch or stream
        if follow:
            loki.stream_logs(query, since=since)
        else:
            loki.fetch_logs(query, since=since, limit=lines)

    except KeyboardInterrupt:
        console.print("\n[yellow]⏸ Stopped[/yellow]")
    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        sys.exit(1)
    finally:
        # Clean up tunnel
        if "tunnel_proc" in locals():
            tunnel_proc.terminate()
            tunnel_proc.wait()


class LokiClient:
    """Loki API client"""

    def __init__(self, base_url: str, project: str):
        self.base_url = base_url.rstrip("/")
        self.project = project

        # Test connection
        try:
            r = requests.get(f"{self.base_url}/ready", timeout=5)
            r.raise_for_status()
        except Exception as e:
            raise ConnectionError(f"Cannot reach Loki at {base_url}: {e}")

    def build_query(self, app=None, container=None, level=None) -> str:
        """Build LogQL query"""

        labels = []

        if container:
            labels.append(f'container="{container}"')
        elif app:
            labels.append(f'container=~".*{app}.*"')
        else:
            labels.append('container=~".+"')

        query = "{" + ", ".join(labels) + "}"

        if level:
            query += f' |= "{level.upper()}"'

        return query

    def fetch_logs(self, query: str, since: str = "5m", limit: int = 100):
        """Fetch logs"""

        start_ns = self._parse_since(since)
        end_ns = int(time.time() * 1e9)

        params = {
            "query": query,
            "start": start_ns,
            "end": end_ns,
            "limit": limit,
            "direction": "BACKWARD",
        }

        try:
            r = requests.get(
                f"{self.base_url}/loki/api/v1/query_range", params=params, timeout=30
            )
            r.raise_for_status()
            self._display_logs(r.json())
        except Exception as e:
            raise Exception(f"Loki API error: {e}")

    def stream_logs(self, query: str, since: str = "5m"):
        """Stream logs"""

        last_ts = self._parse_since(since)

        try:
            while True:
                end_ns = int(time.time() * 1e9)

                params = {
                    "query": query,
                    "start": last_ts,
                    "end": end_ns,
                    "limit": 100,
                    "direction": "FORWARD",
                }

                r = requests.get(
                    f"{self.base_url}/loki/api/v1/query_range",
                    params=params,
                    timeout=10,
                )

                if r.status_code == 200:
                    new_ts = self._display_logs(r.json(), stream=True)
                    if new_ts:
                        last_ts = new_ts

                time.sleep(1)
        except KeyboardInterrupt:
            raise

    def _display_logs(self, data: dict, stream: bool = False) -> Optional[int]:
        """Display logs"""

        if data.get("status") != "success":
            return None

        results = data.get("data", {}).get("result", [])
        if not results:
            if not stream:
                console.print("[yellow]No logs[/yellow]")
            return None

        last_ts = None

        for result in results:
            labels = result.get("stream", {})
            container = labels.get("container", "?")
            vm = labels.get("vm", "")

            for ts_ns, log_line in result.get("values", []):
                # Format timestamp
                ts = int(ts_ns) / 1e9
                dt = datetime.fromtimestamp(ts)
                time_str = dt.strftime("%H:%M:%S.%f")[:-3]

                # Smart colorization based on log content
                log_lower = log_line.lower()

                if "error" in log_lower or "[e]" in log_line or "✗" in log_line:
                    log_color = "\033[91m"  # Bright red
                elif "warn" in log_lower or "[w]" in log_line or "⚠" in log_line:
                    log_color = "\033[93m"  # Bright yellow
                elif "info" in log_lower or "[i]" in log_line or "✓" in log_line:
                    log_color = "\033[96m"  # Bright cyan
                elif "debug" in log_lower or "[d]" in log_line:
                    log_color = "\033[90m"  # Dark gray
                elif "http" in log_lower or "get" in log_lower or "post" in log_lower:
                    log_color = "\033[94m"  # Blue
                elif "response" in log_lower or "📦" in log_line or "🚀" in log_line:
                    log_color = "\033[95m"  # Magenta
                else:
                    log_color = "\033[97m"  # White

                # Build colorized output
                prefix = f"\033[2m{time_str}\033[0m "
                if vm:
                    prefix += f"\033[34m{vm}/\033[0m"
                prefix += f"\033[35m{container}\033[0m "

                output = f"{prefix}{log_color}{log_line}\033[0m"

                sys.stdout.write(f"{output}\n")
                sys.stdout.flush()

                last_ts = int(ts_ns)

        return last_ts

    def _parse_since(self, since: str) -> int:
        """Parse duration to timestamp"""

        units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        unit = since[-1]

        if unit not in units:
            raise ValueError(f"Invalid unit: {unit}")

        value = int(since[:-1])
        seconds = value * units[unit]

        return int((time.time() - seconds) * 1e9)


def _find_free_port() -> int:
    """Find a free port for SSH tunnel"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


if __name__ == "__main__":
    logs()
