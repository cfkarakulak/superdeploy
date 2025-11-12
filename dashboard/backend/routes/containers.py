"""Container monitoring and management routes."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pathlib import Path
import json

router = APIRouter(tags=["containers"])

# Get project root
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class ContainerRestartRequest(BaseModel):
    """Request to restart a container."""

    container_name: str


@router.get("/{project_name}/list")
async def list_containers(project_name: str):
    """
    List all containers for a project across all VMs.

    Returns container info with status, metrics, and health.
    """
    from services.ssh_service import SSHConnectionPool

    ssh_pool = SSHConnectionPool(PROJECT_ROOT)

    try:
        # Get VM information from state.yml
        vms = ssh_pool.get_vm_info_from_state(project_name)

        if not vms:
            return {"containers": [], "message": "No VMs found in state"}

        # Get SSH key path
        ssh_key_path = ssh_pool.get_ssh_key_path(project_name)

        all_containers = []

        # Query each VM for containers
        for vm_name, vm_info in vms.items():
            vm_ip = vm_info.get("external_ip")

            if not vm_ip:
                continue

            try:
                # Get containers list
                containers = await ssh_pool.get_containers_list(
                    vm_ip, ssh_key_path, project_name
                )

                # Get real-time stats
                stats = await ssh_pool.get_container_stats(vm_ip, ssh_key_path)
                stats_by_name = {s["name"]: s for s in stats}

                # Merge container info with stats
                for container in containers:
                    container["vm"] = vm_name
                    container["vm_ip"] = vm_ip

                    # Add stats if available
                    container_stats = stats_by_name.get(container["name"])
                    if container_stats:
                        container["cpu_percent"] = container_stats.get("cpu_percent")
                        container["memory_usage"] = container_stats.get("mem")
                        container["memory_percent"] = container_stats.get("mem_percent")
                        container["network_rx"] = container_stats.get("network_rx")
                        container["network_tx"] = container_stats.get("network_tx")

                    all_containers.append(container)

            except Exception as e:
                # Log error but continue with other VMs
                print(f"Error querying VM {vm_name}: {str(e)}")
                continue

        return {"containers": all_containers}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await ssh_pool.close_all()


@router.get("/{project_name}/containers/{container_name}/metrics")
async def get_container_metrics(project_name: str, container_name: str):
    """
    Get real-time metrics for a specific container.

    Returns CPU, memory, network stats.
    """
    from services.ssh_service import SSHConnectionPool

    ssh_pool = SSHConnectionPool(PROJECT_ROOT)

    try:
        # Get VM information
        vms = ssh_pool.get_vm_info_from_state(project_name)
        ssh_key_path = ssh_pool.get_ssh_key_path(project_name)

        # Find which VM has this container
        for vm_name, vm_info in vms.items():
            vm_ip = vm_info.get("external_ip")

            if not vm_ip:
                continue

            try:
                containers = await ssh_pool.get_containers_list(
                    vm_ip, ssh_key_path, project_name
                )

                # Check if container is on this VM
                container_found = any(c["name"] == container_name for c in containers)

                if container_found:
                    # Get stats
                    stats = await ssh_pool.get_container_stats(vm_ip, ssh_key_path)

                    # Find stats for this container
                    for stat in stats:
                        if stat["name"] == container_name:
                            return {
                                "container_name": container_name,
                                "vm": vm_name,
                                "metrics": {
                                    "cpu_percent": stat.get("cpu_percent"),
                                    "memory_usage": stat.get("mem"),
                                    "memory_percent": stat.get("mem_percent"),
                                    "network_rx": stat.get("network_rx"),
                                    "network_tx": stat.get("network_tx"),
                                    "block_io": stat.get("block_io"),
                                },
                            }

                    # Container found but no stats
                    raise HTTPException(
                        status_code=404,
                        detail=f"Container {container_name} found but no stats available",
                    )

            except Exception:
                continue

        # Container not found on any VM
        raise HTTPException(
            status_code=404, detail=f"Container {container_name} not found"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await ssh_pool.close_all()


@router.get("/{project_name}/containers/{container_name}/logs")
async def stream_container_logs(
    project_name: str, container_name: str, tail: int = 100
):
    """
    Stream container logs in real-time using Server-Sent Events.

    Args:
        project_name: Name of the project
        container_name: Name of the container
        tail: Number of lines to show from history
    """
    from services.ssh_service import SSHConnectionPool

    async def event_generator():
        ssh_pool = SSHConnectionPool(PROJECT_ROOT)

        try:
            # Get VM information
            vms = ssh_pool.get_vm_info_from_state(project_name)
            ssh_key_path = ssh_pool.get_ssh_key_path(project_name)

            # Find which VM has this container
            vm_ip = None
            for vm_name, vm_info in vms.items():
                vm_external_ip = vm_info.get("external_ip")

                if not vm_external_ip:
                    continue

                try:
                    containers = await ssh_pool.get_containers_list(
                        vm_external_ip, ssh_key_path, project_name
                    )

                    if any(c["name"] == container_name for c in containers):
                        vm_ip = vm_external_ip
                        break

                except Exception:
                    continue

            if not vm_ip:
                yield f"data: {json.dumps({'type': 'error', 'message': f'Container {container_name} not found'})}\n\n"
                return

            # Stream logs
            yield f"data: {json.dumps({'type': 'info', 'message': f'Streaming logs for {container_name}...'})}\n\n"

            async for log_line in ssh_pool.stream_logs(
                vm_ip, ssh_key_path, container_name, tail
            ):
                # Send log line as SSE event
                yield f"data: {json.dumps({'type': 'log', 'message': log_line.rstrip()})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            await ssh_pool.close_all()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.post("/{project_name}/containers/{container_name}/restart")
async def restart_container(project_name: str, container_name: str):
    """
    Restart a specific container.

    Returns success message and container status.
    """
    from services.ssh_service import SSHConnectionPool

    ssh_pool = SSHConnectionPool(PROJECT_ROOT)

    try:
        # Get VM information
        vms = ssh_pool.get_vm_info_from_state(project_name)
        ssh_key_path = ssh_pool.get_ssh_key_path(project_name)

        # Find which VM has this container
        for vm_name, vm_info in vms.items():
            vm_ip = vm_info.get("external_ip")

            if not vm_ip:
                continue

            try:
                containers = await ssh_pool.get_containers_list(
                    vm_ip, ssh_key_path, project_name
                )

                # Check if container is on this VM
                if any(c["name"] == container_name for c in containers):
                    # Restart container
                    success = await ssh_pool.restart_container(
                        vm_ip, ssh_key_path, container_name
                    )

                    if success:
                        return {
                            "success": True,
                            "message": f"Container {container_name} restarted successfully",
                            "container_name": container_name,
                            "vm": vm_name,
                        }

            except Exception:
                continue

        # Container not found
        raise HTTPException(
            status_code=404, detail=f"Container {container_name} not found"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await ssh_pool.close_all()


@router.post("/{project_name}/containers/restart-all")
async def restart_all_containers(project_name: str):
    """
    Restart all containers for a project.

    Useful for applying configuration changes.
    """
    from services.ssh_service import SSHConnectionPool

    ssh_pool = SSHConnectionPool(PROJECT_ROOT)

    try:
        # Get VM information
        vms = ssh_pool.get_vm_info_from_state(project_name)
        ssh_key_path = ssh_pool.get_ssh_key_path(project_name)

        restarted_containers = []
        failed_containers = []

        # Restart containers on each VM
        for vm_name, vm_info in vms.items():
            vm_ip = vm_info.get("external_ip")

            if not vm_ip:
                continue

            try:
                # Get all containers
                containers = await ssh_pool.get_containers_list(
                    vm_ip, ssh_key_path, project_name
                )

                # Restart each container
                for container in containers:
                    container_name = container["name"]

                    try:
                        await ssh_pool.restart_container(
                            vm_ip, ssh_key_path, container_name
                        )
                        restarted_containers.append(
                            {"name": container_name, "vm": vm_name}
                        )
                    except Exception as e:
                        failed_containers.append(
                            {"name": container_name, "vm": vm_name, "error": str(e)}
                        )

            except Exception as e:
                print(f"Error restarting containers on VM {vm_name}: {str(e)}")
                continue

        return {
            "success": len(failed_containers) == 0,
            "restarted": restarted_containers,
            "failed": failed_containers,
            "total": len(restarted_containers) + len(failed_containers),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await ssh_pool.close_all()
