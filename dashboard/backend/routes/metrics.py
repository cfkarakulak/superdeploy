"""Metrics routes for fetching system metrics from Prometheus."""

from fastapi import APIRouter, HTTPException
from database import SessionLocal
from models import Project, App
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

        # Get VM name from app (can be role or full name)
        vm_identifier = app.vm
        if not vm_identifier:
            raise HTTPException(status_code=404, detail="App has no VM assigned")

        # Get VM from database - try by name first, then by role
        vm = (
            db.query(VM)
            .filter(VM.project_id == project.id, VM.name == vm_identifier)
            .first()
        )

        # If not found by name, try by role (e.g., app.vm = "app" -> find VM with role="app")
        if not vm:
            # Build full VM name: {project}-{role}-0
            vm_name = f"{project_name}-{vm_identifier}-0"
            vm = (
                db.query(VM)
                .filter(VM.project_id == project.id, VM.name == vm_name)
                .first()
            )

        if not vm or not vm.external_ip:
            raise HTTPException(
                status_code=404, detail=f"VM '{vm_identifier}' not found or has no IP"
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


@router.get("/{project_name}/vms")
async def get_project_vms_metrics(project_name: str):
    """
    Get real-time metrics for all VMs in a project from Prometheus.

    Returns metrics for each VM:
    - CPU usage (%)
    - Memory usage (%)
    - Disk usage (%)
    - Network I/O
    - Uptime
    - Status (up/down)
    """
    db = SessionLocal()

    try:
        # Verify project exists
        project = db.query(Project).filter(Project.name == project_name).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Get all VMs for this project
        vms = db.query(VM).filter(VM.project_id == project.id).all()
        if not vms:
            return {"project": project_name, "vms": []}

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

        # Collect metrics for all VMs
        vm_metrics_list = []

        for vm in vms:
            if not vm.external_ip:
                continue

            vm_ip = vm.external_ip
            instance_filter = f'instance=~".*{vm_ip}.*"'

            # Prometheus queries for this VM
            queries = {
                "cpu_usage": f'100 - (avg by (instance) (rate(node_cpu_seconds_total{{mode="idle",{instance_filter}}}[5m])) * 100)',
                "memory_usage": f"(1 - (node_memory_MemAvailable_bytes{{{instance_filter}}} / node_memory_MemTotal_bytes{{{instance_filter}}})) * 100",
                "disk_usage": f'(node_filesystem_size_bytes{{mountpoint="/",{instance_filter}}} - node_filesystem_avail_bytes{{mountpoint="/",{instance_filter}}}) / node_filesystem_size_bytes{{mountpoint="/",{instance_filter}}} * 100',
                "uptime": f"node_time_seconds{{{instance_filter}}} - node_boot_time_seconds{{{instance_filter}}}",
                "status": f'up{{instance=~".*{vm_ip}.*",job="project-nodes"}}',
                "network_rx": f'rate(node_network_receive_bytes_total{{device="eth0",{instance_filter}}}[5m])',
                "network_tx": f'rate(node_network_transmit_bytes_total{{device="eth0",{instance_filter}}}[5m])',
                "load_1m": f"node_load1{{{instance_filter}}}",
            }

            # Execute all queries in parallel
            results = await asyncio.gather(
                *[query_prometheus(prometheus_url, q) for q in queries.values()],
                return_exceptions=True,
            )

            # Map results back to query names
            metrics = {}
            for (key, _), result in zip(queries.items(), results):
                if isinstance(result, Exception):
                    metrics[key] = 0.0 if key != "status" else 0
                else:
                    metrics[key] = result

            vm_metrics_list.append(
                {
                    "name": vm.name,
                    "external_ip": vm.external_ip,
                    "internal_ip": vm.internal_ip,
                    "machine_type": vm.machine_type,
                    "status": "up" if metrics.get("status", 0) == 1 else "down",
                    "metrics": {
                        "cpu_usage": round(metrics.get("cpu_usage", 0.0), 1),
                        "memory_usage": round(metrics.get("memory_usage", 0.0), 1),
                        "disk_usage": round(metrics.get("disk_usage", 0.0), 1),
                        "uptime_seconds": int(metrics.get("uptime", 0)),
                        "load_1m": round(metrics.get("load_1m", 0.0), 2),
                        "network_rx_bytes_per_sec": round(
                            metrics.get("network_rx", 0.0), 0
                        ),
                        "network_tx_bytes_per_sec": round(
                            metrics.get("network_tx", 0.0), 0
                        ),
                    },
                }
            )

        return {
            "project": project_name,
            "prometheus_url": prometheus_url,
            "vms": vm_metrics_list,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.get("/{project_name}/{app_name}/containers")
async def get_app_container_metrics(
    project_name: str, app_name: str, include_addons: bool = False
):
    """
    Get cAdvisor container metrics for an app.

    Returns detailed container-level metrics:
    - CPU usage per container
    - Memory usage per container
    - Network I/O per container
    - Filesystem I/O per container

    Args:
        project_name: Name of the project
        app_name: Name of the app
        include_addons: If True, includes all project containers (app + addons).
                       If False (default), only returns app-specific containers.
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

        # Query cAdvisor metrics for Docker containers (systemd cgroup paths)
        # Filter: only docker-*.scope containers (not root, not system services)
        # Exclude cAdvisor itself
        # Note: App containers have "container_label_com_superdeploy_app" label
        #       Addon containers have "container_label_addon_type" label
        #       Both have "project" label

        if include_addons:
            # Include ALL containers in the project (app + addons)
            app_filter = f'id=~"/system.slice/docker-.*\\\\.scope",name!="",name!~".*cadvisor.*",project="{project_name}"'
        else:
            # Only app-specific containers (filter by superdeploy_app label)
            app_filter = f'id=~"/system.slice/docker-.*\\\\.scope",name!="",name!~".*cadvisor.*",project="{project_name}",container_label_com_superdeploy_app="{app_name}"'

        queries = {
            "cpu_usage": f"rate(container_cpu_usage_seconds_total{{{app_filter}}}[5m]) * 100",
            "memory_usage": f"container_memory_usage_bytes{{{app_filter}}}",
            "memory_limit": f"container_spec_memory_limit_bytes{{{app_filter}}}",
            "network_rx": f"rate(container_network_receive_bytes_total{{{app_filter}}}[5m])",
            "network_tx": f"rate(container_network_transmit_bytes_total{{{app_filter}}}[5m])",
            "fs_reads": f"rate(container_fs_reads_bytes_total{{{app_filter}}}[5m])",
            "fs_writes": f"rate(container_fs_writes_bytes_total{{{app_filter}}}[5m])",
        }

        # Execute queries
        results = {}
        async with httpx.AsyncClient(timeout=5.0) as client:
            for key, query in queries.items():
                try:
                    response = await client.get(
                        f"{prometheus_url}/api/v1/query", params={"query": query}
                    )

                    if response.status_code == 200:
                        data = response.json()
                        result = data.get("data", {}).get("result", [])
                        results[key] = result
                    else:
                        results[key] = []

                except Exception as e:
                    print(f"Container metrics query error ({key}): {e}")
                    results[key] = []

        # Helper to extract container name from cAdvisor metrics
        def get_container_name(metric: dict) -> str:
            """
            Extract container name from superdeploy custom labels or Docker name.

            App containers have these labels:
            - container_label_com_superdeploy_app: App name (e.g., "api", "services")
            - container_label_com_superdeploy_process: Process type (e.g., "web", "worker")

            Addon containers don't have these labels, so we use Docker container name directly.
            """
            superdeploy_app = metric.get("container_label_com_superdeploy_app", "")
            superdeploy_process = metric.get(
                "container_label_com_superdeploy_process", ""
            )

            # If has superdeploy labels, it's an app container
            if superdeploy_app:
                # Format: "app" for web processes, "app (process)" for others
                if superdeploy_process and superdeploy_process != "web":
                    return f"{superdeploy_app} ({superdeploy_process})"
                return superdeploy_app

            # No superdeploy labels = addon container
            # Use Docker container name directly (from cAdvisor "name" label)
            container_name = metric.get("name", "unknown")
            return container_name

        # Process results into container-specific metrics
        containers = {}

        for result in results.get("cpu_usage", []):
            metric = result.get("metric", {})
            container_name = get_container_name(metric)
            if container_name not in containers:
                containers[container_name] = {}
            containers[container_name]["cpu_percent"] = float(
                result.get("value", [None, "0"])[1]
            )

        for result in results.get("memory_usage", []):
            metric = result.get("metric", {})
            container_name = get_container_name(metric)
            if container_name not in containers:
                containers[container_name] = {}
            containers[container_name]["memory_bytes"] = int(
                float(result.get("value", [None, "0"])[1])
            )

        for result in results.get("memory_limit", []):
            metric = result.get("metric", {})
            container_name = get_container_name(metric)
            if container_name not in containers:
                containers[container_name] = {}
            limit = int(float(result.get("value", [None, "0"])[1]))
            containers[container_name]["memory_limit_bytes"] = limit
            if limit > 0 and "memory_bytes" in containers[container_name]:
                containers[container_name]["memory_percent"] = (
                    containers[container_name]["memory_bytes"] / limit * 100
                )

        for result in results.get("network_rx", []):
            metric = result.get("metric", {})
            container_name = get_container_name(metric)
            if container_name not in containers:
                containers[container_name] = {}
            containers[container_name]["network_rx_bytes_per_sec"] = float(
                result.get("value", [None, "0"])[1]
            )

        for result in results.get("network_tx", []):
            metric = result.get("metric", {})
            container_name = get_container_name(metric)
            if container_name not in containers:
                containers[container_name] = {}
            containers[container_name]["network_tx_bytes_per_sec"] = float(
                result.get("value", [None, "0"])[1]
            )

        for result in results.get("fs_reads", []):
            metric = result.get("metric", {})
            container_name = get_container_name(metric)
            if container_name not in containers:
                containers[container_name] = {}
            containers[container_name]["fs_read_bytes_per_sec"] = float(
                result.get("value", [None, "0"])[1]
            )

        for result in results.get("fs_writes", []):
            metric = result.get("metric", {})
            container_name = get_container_name(metric)
            if container_name not in containers:
                containers[container_name] = {}
            containers[container_name]["fs_write_bytes_per_sec"] = float(
                result.get("value", [None, "0"])[1]
            )

        return {
            "app": app_name,
            "project": project_name,
            "prometheus_url": prometheus_url,
            "containers": [
                {"name": name, **metrics} for name, metrics in containers.items()
            ],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.get("/{project_name}/{app_name}/application")
async def get_app_application_metrics(project_name: str, app_name: str):
    """
    Get application-level metrics from PrometheusMiddleware.

    Returns:
    - HTTP request rate (requests per second)
    - HTTP request latency (p50, p95, p99)
    - HTTP error rate (5xx errors)
    - Active requests (in-progress)
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

        # Get VM name from app (can be role or full name)
        vm_identifier = app.vm
        if not vm_identifier:
            raise HTTPException(status_code=404, detail="App has no VM assigned")

        # Get VM from database - try by name first, then by role
        vm = (
            db.query(VM)
            .filter(VM.project_id == project.id, VM.name == vm_identifier)
            .first()
        )

        # If not found by name, try by role (e.g., app.vm = "app" -> find VM with role="app")
        if not vm:
            # Build full VM name: {project}-{role}-0
            vm_name = f"{project_name}-{vm_identifier}-0"
            vm = (
                db.query(VM)
                .filter(VM.project_id == project.id, VM.name == vm_name)
                .first()
            )

        if not vm or not vm.external_ip:
            raise HTTPException(
                status_code=404, detail=f"VM '{vm_identifier}' not found or has no IP"
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

        # Application metrics queries (from PrometheusMiddleware)
        instance_filter = f'instance=~".*{vm_ip}.*"'

        queries = {
            "request_rate": f"sum(rate(app_http_requests_total{{{instance_filter}}}[5m]))",
            "error_rate": f'sum(rate(app_http_requests_total{{status=~"5..",{instance_filter}}}[5m]))',
            "latency_p50": f"histogram_quantile(0.50, sum(rate(app_http_request_duration_seconds_bucket{{{instance_filter}}}[5m])) by (le))",
            "latency_p95": f"histogram_quantile(0.95, sum(rate(app_http_request_duration_seconds_bucket{{{instance_filter}}}[5m])) by (le))",
            "latency_p99": f"histogram_quantile(0.99, sum(rate(app_http_request_duration_seconds_bucket{{{instance_filter}}}[5m])) by (le))",
            "active_requests": f"sum(app_http_requests_in_progress{{{instance_filter}}})",
        }

        # Execute queries in parallel
        results = await asyncio.gather(
            *[query_prometheus(prometheus_url, q) for q in queries.values()],
            return_exceptions=True,
        )

        # Map results
        metrics = {}
        for (key, _), result in zip(queries.items(), results):
            if isinstance(result, Exception):
                metrics[key] = 0.0
            else:
                metrics[key] = result

        return {
            "app": app_name,
            "project": project_name,
            "vm_ip": vm_ip,
            "prometheus_url": prometheus_url,
            "metrics": {
                "request_rate_per_sec": round(metrics.get("request_rate", 0.0), 2),
                "error_rate_per_sec": round(metrics.get("error_rate", 0.0), 2),
                "error_percentage": round(
                    (
                        metrics.get("error_rate", 0.0)
                        / metrics.get("request_rate", 1.0)
                        * 100
                    )
                    if metrics.get("request_rate", 0.0) > 0
                    else 0.0,
                    2,
                ),
                "latency_p50_ms": round(metrics.get("latency_p50", 0.0) * 1000, 1),
                "latency_p95_ms": round(metrics.get("latency_p95", 0.0) * 1000, 1),
                "latency_p99_ms": round(metrics.get("latency_p99", 0.0) * 1000, 1),
                "active_requests": int(metrics.get("active_requests", 0)),
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
