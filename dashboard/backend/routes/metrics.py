"""Metrics routes for fetching system metrics from Prometheus."""

from fastapi import APIRouter, HTTPException
from database import SessionLocal
from models import Project, App, VM
import httpx
import asyncio

router = APIRouter(tags=["metrics"])


async def query_prometheus(prometheus_url: str, query: str) -> float:
    """Query Prometheus and return the metric value."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{prometheus_url}/api/v1/query", params={"query": query}
            )

            if response.status_code != 200:
                return 0.0

            data = response.json()
            result = data.get("data", {}).get("result", [])

            if not result:
                return 0.0

            # Get first result value
            value = result[0].get("value", [None, "0"])[1]
            return float(value)

    except Exception as e:
        print(f"Prometheus query error: {e}")
        return 0.0


@router.get("/{project_name}/{app_name}/metrics")
async def get_app_metrics(project_name: str, app_name: str):
    """
    Get real-time metrics for an app from Prometheus.

    Returns:
    - CPU usage
    - Memory usage
    - Disk usage
    - Container count
    - Uptime
    """
    db = SessionLocal()

    try:
        # Verify project exists
        project = db.query(Project).filter(Project.name == project_name).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Get app
        app = (
            db.query(App)
            .filter(App.project_id == project.id, App.name == app_name)
            .first()
        )
        if not app:
            raise HTTPException(status_code=404, detail="App not found")

        # Get VM name from app
        vm_name = app.vm
        if not vm_name:
            raise HTTPException(status_code=404, detail="App has no VM assigned")

        # Get VM from database
        vm = (
            db.query(VM).filter(VM.project_id == project.id, VM.name == vm_name).first()
        )
        if not vm or not vm.external_ip:
            raise HTTPException(
                status_code=404, detail=f"VM '{vm_name}' not found or has no IP"
            )

        vm_ip = vm.external_ip

        # Get orchestrator VM for Prometheus
        orchestrator_project = (
            db.query(Project).filter(Project.name == "orchestrator").first()
        )
        if not orchestrator_project:
            raise HTTPException(status_code=500, detail="Orchestrator not found")

        orchestrator_vm = (
            db.query(VM)
            .filter(VM.project_id == orchestrator_project.id, VM.name == "orchestrator")
            .first()
        )
        if not orchestrator_vm or not orchestrator_vm.external_ip:
            raise HTTPException(status_code=500, detail="Orchestrator VM not found")

        prometheus_url = f"http://{orchestrator_vm.external_ip}:9090"

        # Prometheus queries for the specific VM
        instance_filter = f'instance=~".*{vm_ip}.*"'

        # Query metrics from Prometheus in parallel
        cpu_query = f'100 - (avg by (instance) (rate(node_cpu_seconds_total{{mode="idle",{instance_filter}}}[5m])) * 100)'
        memory_query = f"(1 - (node_memory_MemAvailable_bytes{{{instance_filter}}} / node_memory_MemTotal_bytes{{{instance_filter}}})) * 100"
        disk_query = f'(node_filesystem_size_bytes{{mountpoint="/",{instance_filter}}} - node_filesystem_avail_bytes{{mountpoint="/",{instance_filter}}}) / node_filesystem_size_bytes{{mountpoint="/",{instance_filter}}} * 100'
        uptime_query = f"node_time_seconds{{{instance_filter}}} - node_boot_time_seconds{{{instance_filter}}}"

        # Container count - count running containers for this app
        container_query = f'count(container_last_seen{{name=~".*{app_name}.*"}})'

        # Execute all queries in parallel
        results = await asyncio.gather(
            query_prometheus(prometheus_url, cpu_query),
            query_prometheus(prometheus_url, memory_query),
            query_prometheus(prometheus_url, disk_query),
            query_prometheus(prometheus_url, uptime_query),
            query_prometheus(prometheus_url, container_query),
            return_exceptions=True,
        )

        cpu_usage, memory_usage, disk_usage, uptime_seconds, container_count = results

        # Handle any exceptions
        metrics = {
            "cpu_usage": cpu_usage if not isinstance(cpu_usage, Exception) else 0.0,
            "memory_usage": memory_usage
            if not isinstance(memory_usage, Exception)
            else 0.0,
            "disk_usage": disk_usage if not isinstance(disk_usage, Exception) else 0.0,
            "container_count": int(container_count)
            if not isinstance(container_count, Exception)
            else 0,
            "uptime_seconds": uptime_seconds
            if not isinstance(uptime_seconds, Exception)
            else 0.0,
        }

        return {
            "app": app_name,
            "project": project_name,
            "vm_ip": vm_ip,
            "prometheus_url": prometheus_url,
            "metrics": metrics,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
