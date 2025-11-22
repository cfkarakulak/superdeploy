"""Metrics routes for fetching system metrics from Prometheus."""

from fastapi import APIRouter, HTTPException
import subprocess
import json
from cache import get_cache, set_cache
import httpx
import asyncio

router = APIRouter(tags=["metrics"])


def get_orchestrator_ip():
    """Get orchestrator IP from state.yml or CLI (5 min cache)."""
    cache_key = "orchestrator_ip"
    cached = get_cache(cache_key)
    if cached:
        return cached

    try:
        # Try state.yml first (fastest, no external calls)
        from pathlib import Path

        # Get project root dynamically (dashboard/backend/routes/metrics.py -> ../../../../)
        project_root = Path(__file__).parent.parent.parent.parent
        state_file = project_root / "shared" / "orchestrator" / "state.yml"

        if state_file.exists():
            import yaml

            with open(state_file, "r") as f:
                state = yaml.safe_load(f)
                if state and state.get("orchestrator_ip"):
                    orch_ip = state["orchestrator_ip"]
                    set_cache(cache_key, orch_ip, 300)
                    return orch_ip

        # Fallback to CLI
        result = subprocess.run(
            ["./superdeploy.sh", "orchestrator:status", "--json"],
            capture_output=True,
            text=True,
            cwd=str(project_root),
            timeout=30,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            if data.get("vms"):
                for vm in data["vms"]:
                    if vm.get("name") == "orchestrator":
                        orch_ip = vm.get("ip")
                        set_cache(cache_key, orch_ip, 300)
                        return orch_ip
        return None
    except Exception as e:
        print(f"Failed to get orchestrator IP: {e}")
        return None


def get_project_vms(project_name: str):
    """Get VMs for project from database or CLI (5 min cache)."""
    cache_key = f"project_vms:{project_name}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    try:
        # Try database first (faster)
        import os

        os.environ.setdefault(
            "SUPERDEPLOY_DB_URL",
            "postgresql://postgres:postgres@localhost:5432/superdeploy",
        )
        from cli.database import get_db_session
        from sqlalchemy import text

        db = get_db_session()
        try:
            result = db.execute(
                text("""
                SELECT v.name, v.external_ip, v.internal_ip, v.role
                FROM vms v
                JOIN projects p ON v.project_id = p.id
                WHERE p.name = :project_name
                ORDER BY v.name
            """),
                {"project_name": project_name},
            )
            vms = []
            for row in result.fetchall():
                vms.append(
                    {
                        "name": row[0],
                        "ip": row[1],
                        "external_ip": row[1],
                        "internal_ip": row[2],
                        "role": row[3] or row[0].split("-")[0]
                        if "-" in row[0]
                        else row[0],
                    }
                )
            if vms:
                set_cache(cache_key, vms, 300)
                return vms
        finally:
            db.close()

        # Fallback to CLI (slower)
        from pathlib import Path

        project_root = Path(__file__).parent.parent.parent.parent
        result = subprocess.run(
            ["./superdeploy.sh", f"{project_name}:status", "--json"],
            capture_output=True,
            text=True,
            cwd=str(project_root),
            timeout=5,  # Reduced timeout
        )
        if result.returncode == 0:
            project_data = json.loads(result.stdout)
            vms = project_data.get("vms", [])
            set_cache(cache_key, vms, 300)
            return vms
        return []
    except Exception as e:
        print(f"Failed to get project VMs: {e}")
        return []


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
    try:
        # Wrap in timeout - max 5 seconds for entire endpoint
        async def _fetch_metrics():
            # Get project VMs from CLI
            vms = get_project_vms(project_name)
            if not vms:
                raise HTTPException(status_code=404, detail="Project not found")

            # Verify app exists in project (just check if VMs exist)
            if not vms:
                raise HTTPException(status_code=404, detail="App not found")

            # Find app VM
            app_vm = next((vm for vm in vms if vm.get("role") == "app"), None)
            if not app_vm:
                app_vm = vms[0]  # Fallback to first VM

            vm_ip = app_vm.get("ip")
            if not vm_ip:
                raise HTTPException(status_code=404, detail="VM has no IP")

            # Get orchestrator IP from CLI
            orch_ip = get_orchestrator_ip()
            if not orch_ip:
                raise HTTPException(status_code=500, detail="Orchestrator not found")

            prometheus_url = f"http://{orch_ip}:9090"

            # Get internal IP for accurate metrics (node-exporter uses internal IP)
            vm_internal_ip = app_vm.get("internal_ip")
            
            # Prometheus queries - use internal IP for node-exporter
            if vm_internal_ip and vm_internal_ip.startswith("10."):
                instance_filter = f'instance="{vm_internal_ip}:9100"'
            else:
                # Fallback: use external IP pattern matching
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

            cpu_usage, memory_usage, disk_usage, uptime_seconds, container_count = (
                results
            )

            # Handle any exceptions
            metrics = {
                "cpu_usage": cpu_usage if not isinstance(cpu_usage, Exception) else 0.0,
                "memory_usage": memory_usage
                if not isinstance(memory_usage, Exception)
                else 0.0,
                "disk_usage": disk_usage
                if not isinstance(disk_usage, Exception)
                else 0.0,
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

        # Apply 10 second timeout to entire endpoint
        return await asyncio.wait_for(_fetch_metrics(), timeout=10.0)

    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504, detail="Request timeout - Prometheus not responding"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
    try:
        # Get project VMs from CLI
        vms_data = get_project_vms(project_name)
        if not vms_data:
            raise HTTPException(status_code=404, detail="Project not found or no VMs")

        # get_project_vms returns dict with 'vms' key OR just a list
        if isinstance(vms_data, dict):
            vms = vms_data.get("vms", [])
        else:
            vms = vms_data if isinstance(vms_data, list) else []

        if not vms:
            return {"project": project_name, "vms": []}

        # Get orchestrator IP from CLI
        orch_ip = get_orchestrator_ip()
        if not orch_ip:
            raise HTTPException(status_code=500, detail="Orchestrator not found")

        prometheus_url = f"http://{orch_ip}:9090"

        # Collect metrics for all VMs
        vm_metrics_list = []

        # Get internal IPs from Prometheus targets for this project
        vm_instances = {}  # {instance: {internal_ip, role}}
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                targets_response = await client.get(f"{prometheus_url}/api/v1/targets")
                if targets_response.status_code == 200:
                    targets_data = targets_response.json()
                    for target in targets_data.get("data", {}).get("activeTargets", []):
                        labels = target.get("labels", {})
                        if (
                            labels.get("project") == project_name
                            and labels.get("job") == "project-nodes"
                        ):
                            instance = labels.get("instance", "")
                            if instance:
                                # Extract internal IP (format: "10.1.0.3:9100")
                                internal_ip = (
                                    instance.split(":")[0]
                                    if ":" in instance
                                    else instance
                                )
                                vm_instances[instance] = {
                                    "internal_ip": internal_ip,
                                    "instance": instance,
                                }
        except Exception as e:
            print(f"Failed to get VM instances from Prometheus: {e}")

        # Match VMs with their Prometheus instances
        for i, vm in enumerate(vms):
            vm_name = vm.get("name")
            if not vm_name:
                continue

            # Try to find matching instance by order (same order as targets)
            if i < len(vm_instances):
                instance_data = list(vm_instances.values())[i]
                instance_filter = f'instance="{instance_data["instance"]}"'
            else:
                # Fallback: use project filter
                instance_filter = f'project="{project_name}"'

            # Prometheus queries for this VM
            queries = {
                "cpu_usage": f'100 - (avg by (instance) (rate(node_cpu_seconds_total{{mode="idle",{instance_filter}}}[5m])) * 100)',
                "memory_usage": f"(1 - (node_memory_MemAvailable_bytes{{{instance_filter}}} / node_memory_MemTotal_bytes{{{instance_filter}}})) * 100",
                "disk_usage": f'(node_filesystem_size_bytes{{mountpoint="/",{instance_filter}}} - node_filesystem_avail_bytes{{mountpoint="/",{instance_filter}}}) / node_filesystem_size_bytes{{mountpoint="/",{instance_filter}}} * 100',
                "uptime": f"node_time_seconds{{{instance_filter}}} - node_boot_time_seconds{{{instance_filter}}}",
                "status": f'up{{{instance_filter},job="project-nodes"}}',
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
                    "name": vm.get("name"),
                    "ip": vm.get("ip") or vm.get("external_ip"),
                    "role": vm.get("role"),
                    "status": "up" if metrics.get("status", 0) == 1 else "down",
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
                }
            )

        return {
            "project": project_name,
            "prometheus_url": prometheus_url,
            "vms": vm_metrics_list,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
    try:
        # Get project VMs from CLI
        vms = get_project_vms(project_name)
        if not vms:
            raise HTTPException(status_code=404, detail="Project not found")

        # Verify app exists in project (just check if VMs exist)
        if not vms:
            raise HTTPException(status_code=404, detail="App not found")

        # Get orchestrator IP from CLI
        orch_ip = get_orchestrator_ip()
        if not orch_ip:
            raise HTTPException(status_code=500, detail="Orchestrator not found")

        prometheus_url = f"http://{orch_ip}:9090"

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

        def safe_float(value_str: str) -> float:
            """Safely convert string to float, returning 0.0 for invalid values."""
            try:
                val = float(value_str)
                return 0.0 if (val != val or val < 0) else val  # NaN or negative check
            except (ValueError, TypeError):
                return 0.0

        for result in results.get("cpu_usage", []):
            metric = result.get("metric", {})
            container_name = get_container_name(metric)
            if container_name not in containers:
                containers[container_name] = {}
            containers[container_name]["cpu_percent"] = safe_float(
                result.get("value", [None, "0"])[1]
            )

        for result in results.get("memory_usage", []):
            metric = result.get("metric", {})
            container_name = get_container_name(metric)
            if container_name not in containers:
                containers[container_name] = {}
            containers[container_name]["memory_bytes"] = int(
                safe_float(result.get("value", [None, "0"])[1])
            )

        for result in results.get("memory_limit", []):
            metric = result.get("metric", {})
            container_name = get_container_name(metric)
            if container_name not in containers:
                containers[container_name] = {}
            limit = int(safe_float(result.get("value", [None, "0"])[1]))
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
            containers[container_name]["network_rx_bytes_per_sec"] = safe_float(
                result.get("value", [None, "0"])[1]
            )

        for result in results.get("network_tx", []):
            metric = result.get("metric", {})
            container_name = get_container_name(metric)
            if container_name not in containers:
                containers[container_name] = {}
            containers[container_name]["network_tx_bytes_per_sec"] = safe_float(
                result.get("value", [None, "0"])[1]
            )

        for result in results.get("fs_reads", []):
            metric = result.get("metric", {})
            container_name = get_container_name(metric)
            if container_name not in containers:
                containers[container_name] = {}
            containers[container_name]["fs_read_bytes_per_sec"] = safe_float(
                result.get("value", [None, "0"])[1]
            )

        for result in results.get("fs_writes", []):
            metric = result.get("metric", {})
            container_name = get_container_name(metric)
            if container_name not in containers:
                containers[container_name] = {}
            containers[container_name]["fs_write_bytes_per_sec"] = safe_float(
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
    try:
        # Get project VMs from CLI
        vms = get_project_vms(project_name)
        if not vms:
            raise HTTPException(status_code=404, detail="Project not found")

        # Find app VM
        app_vm = next((vm for vm in vms if vm.get("role") == "app"), None)
        if not app_vm:
            app_vm = vms[0]  # Fallback to first VM

        vm_ip = app_vm.get("ip")
        if not vm_ip:
            raise HTTPException(status_code=404, detail="VM has no IP")

        # Get orchestrator IP from CLI
        orch_ip = get_orchestrator_ip()
        if not orch_ip:
            raise HTTPException(status_code=500, detail="Orchestrator not found")

        prometheus_url = f"http://{orch_ip}:9090"

        # Get internal IP from Prometheus targets (same approach as VM metrics)
        app_instance = None
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                targets_response = await client.get(f"{prometheus_url}/api/v1/targets")
                if targets_response.status_code == 200:
                    targets_data = targets_response.json()
                    for target in targets_data.get("data", {}).get("activeTargets", []):
                        labels = target.get("labels", {})
                        if (
                            labels.get("project") == project_name
                            and labels.get("job") == "project-apps"
                        ):
                            app_instance = labels.get("instance", "")
                            if app_instance:
                                break
        except Exception as e:
            print(f"Failed to get app instance from Prometheus: {e}")

        # Use exact instance if found, otherwise use project filter
        if app_instance:
            instance_filter = f'instance="{app_instance}"'
        else:
            instance_filter = f'project="{project_name}",job="project-apps"'

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
