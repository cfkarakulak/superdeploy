"""SSH connection service for VM operations."""

import asyncio
import asyncssh
import json
from typing import Dict, List, AsyncIterator
from pathlib import Path
import yaml


class SSHConnectionPool:
    """Manages SSH connections to VMs with connection pooling."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.connections: Dict[str, asyncssh.SSHClientConnection] = {}
        self.ssh_user = "superdeploy"

    async def get_connection(
        self, vm_ip: str, ssh_key_path: str
    ) -> asyncssh.SSHClientConnection:
        """
        Get or create SSH connection to VM.

        Args:
            vm_ip: IP address of the VM
            ssh_key_path: Path to SSH private key

        Returns:
            Active SSH connection
        """
        # Check if we have an active connection
        if vm_ip in self.connections:
            try:
                # Test if connection is still alive
                await self.connections[vm_ip].run("echo test", check=True, timeout=5)
                return self.connections[vm_ip]
            except:
                # Connection dead, remove it
                del self.connections[vm_ip]

        # Create new connection
        try:
            conn = await asyncssh.connect(
                host=vm_ip,
                username=self.ssh_user,
                client_keys=[ssh_key_path],
                known_hosts=None,  # Disable host key checking for simplicity
                connect_timeout=10,
            )
            self.connections[vm_ip] = conn
            return conn
        except Exception as e:
            raise Exception(f"Failed to connect to {vm_ip}: {str(e)}")

    async def execute_command(
        self, vm_ip: str, ssh_key_path: str, command: str, timeout: int = 30
    ) -> tuple[str, str, int]:
        """
        Execute command on VM and return output.

        Args:
            vm_ip: IP address of the VM
            ssh_key_path: Path to SSH private key
            command: Command to execute
            timeout: Command timeout in seconds

        Returns:
            Tuple of (stdout, stderr, exit_code)
        """
        conn = await self.get_connection(vm_ip, ssh_key_path)

        try:
            result = await conn.run(command, check=False, timeout=timeout)
            return (result.stdout, result.stderr, result.exit_status)
        except asyncio.TimeoutError:
            raise Exception(f"Command timed out after {timeout}s: {command}")
        except Exception as e:
            raise Exception(f"Command execution failed: {str(e)}")

    async def stream_logs(
        self, vm_ip: str, ssh_key_path: str, container_name: str, tail: int = 100
    ) -> AsyncIterator[str]:
        """
        Stream container logs in real-time.

        Args:
            vm_ip: IP address of the VM
            ssh_key_path: Path to SSH private key
            container_name: Name of the container
            tail: Number of lines to show from history

        Yields:
            Log lines as they arrive
        """
        conn = await self.get_connection(vm_ip, ssh_key_path)

        command = f"docker logs -f --tail {tail} {container_name}"

        try:
            async with conn.create_process(command) as process:
                # Stream stdout
                async for line in process.stdout:
                    yield line
        except Exception as e:
            yield f"[ERROR] Log streaming failed: {str(e)}\n"

    async def get_container_stats(self, vm_ip: str, ssh_key_path: str) -> List[Dict]:
        """
        Get real-time stats for all containers on VM.

        Args:
            vm_ip: IP address of the VM
            ssh_key_path: Path to SSH private key

        Returns:
            List of container stats dictionaries
        """
        # Docker stats command with JSON format
        command = (
            "docker stats --no-stream --format "
            '"{\\"container\\":\\"{{.Container}}\\",\\"name\\":\\"{{.Name}}\\",\\"cpu\\":\\"{{.CPUPerc}}\\",\\"mem\\":\\"{{.MemUsage}}\\",\\"mem_perc\\":\\"{{.MemPerc}}\\",\\"net_io\\":\\"{{.NetIO}}\\",\\"block_io\\":\\"{{.BlockIO}}\\"}"'
        )

        stdout, stderr, exit_code = await self.execute_command(
            vm_ip, ssh_key_path, command
        )

        if exit_code != 0:
            raise Exception(f"Failed to get container stats: {stderr}")

        # Parse JSON lines
        stats = []
        for line in stdout.strip().split("\n"):
            if line:
                try:
                    stat = json.loads(line)
                    # Clean up percentage values
                    stat["cpu_percent"] = float(stat["cpu"].rstrip("%"))
                    stat["mem_percent"] = float(stat["mem_perc"].rstrip("%"))

                    # Parse network I/O
                    net_parts = stat["net_io"].split(" / ")
                    stat["network_rx"] = net_parts[0] if len(net_parts) > 0 else "0B"
                    stat["network_tx"] = net_parts[1] if len(net_parts) > 1 else "0B"

                    stats.append(stat)
                except json.JSONDecodeError:
                    continue

        return stats

    async def get_containers_list(
        self, vm_ip: str, ssh_key_path: str, project_name: str
    ) -> List[Dict]:
        """
        Get list of containers for a project.

        Args:
            vm_ip: IP address of the VM
            ssh_key_path: Path to SSH private key
            project_name: Name of the project

        Returns:
            List of container info dictionaries
        """
        # Get containers with JSON format
        command = (
            "docker ps -a --format "
            '"{\\"id\\":\\"{{.ID}}\\",\\"name\\":\\"{{.Names}}\\",\\"image\\":\\"{{.Image}}\\",\\"status\\":\\"{{.Status}}\\",\\"ports\\":\\"{{.Ports}}\\"}" '
            f'--filter "label=com.docker.compose.project={project_name}"'
        )

        stdout, stderr, exit_code = await self.execute_command(
            vm_ip, ssh_key_path, command
        )

        if exit_code != 0:
            raise Exception(f"Failed to list containers: {stderr}")

        containers = []
        for line in stdout.strip().split("\n"):
            if line:
                try:
                    container = json.loads(line)

                    # Parse status to determine if healthy
                    status_lower = container["status"].lower()
                    if "up" in status_lower:
                        if "unhealthy" in status_lower:
                            container["state"] = "unhealthy"
                        else:
                            container["state"] = "running"
                    elif "exited" in status_lower:
                        container["state"] = "exited"
                    elif "restarting" in status_lower:
                        container["state"] = "restarting"
                    else:
                        container["state"] = "unknown"

                    containers.append(container)
                except json.JSONDecodeError:
                    continue

        return containers

    async def restart_container(
        self, vm_ip: str, ssh_key_path: str, container_name: str
    ) -> bool:
        """
        Restart a container.

        Args:
            vm_ip: IP address of the VM
            ssh_key_path: Path to SSH private key
            container_name: Name of the container

        Returns:
            True if successful
        """
        command = f"docker restart {container_name}"

        stdout, stderr, exit_code = await self.execute_command(
            vm_ip, ssh_key_path, command
        )

        if exit_code != 0:
            raise Exception(f"Failed to restart container: {stderr}")

        return True

    async def get_vm_metrics(self, vm_ip: str, ssh_key_path: str) -> Dict:
        """
        Get VM system metrics.

        Args:
            vm_ip: IP address of the VM
            ssh_key_path: Path to SSH private key

        Returns:
            Dictionary with CPU, memory, disk metrics
        """
        metrics = {}

        # Get load average (CPU)
        stdout, _, _ = await self.execute_command(
            vm_ip, ssh_key_path, "cat /proc/loadavg"
        )
        load_parts = stdout.strip().split()
        metrics["load_average"] = {
            "1min": float(load_parts[0]) if len(load_parts) > 0 else 0.0,
            "5min": float(load_parts[1]) if len(load_parts) > 1 else 0.0,
            "15min": float(load_parts[2]) if len(load_parts) > 2 else 0.0,
        }

        # Get memory usage
        stdout, _, _ = await self.execute_command(vm_ip, ssh_key_path, "free -m")
        lines = stdout.strip().split("\n")
        if len(lines) > 1:
            mem_parts = lines[1].split()
            if len(mem_parts) >= 7:
                total = int(mem_parts[1])
                used = int(mem_parts[2])
                metrics["memory"] = {
                    "total_mb": total,
                    "used_mb": used,
                    "free_mb": int(mem_parts[3]),
                    "percent": round((used / total) * 100, 1) if total > 0 else 0,
                }

        # Get disk usage
        stdout, _, _ = await self.execute_command(vm_ip, ssh_key_path, "df -h /")
        lines = stdout.strip().split("\n")
        if len(lines) > 1:
            disk_parts = lines[1].split()
            if len(disk_parts) >= 5:
                metrics["disk"] = {
                    "total": disk_parts[1],
                    "used": disk_parts[2],
                    "available": disk_parts[3],
                    "percent": disk_parts[4].rstrip("%"),
                }

        # Get uptime
        stdout, _, _ = await self.execute_command(vm_ip, ssh_key_path, "uptime -p")
        metrics["uptime"] = stdout.strip()

        return metrics

    async def close_all(self):
        """Close all SSH connections."""
        for conn in self.connections.values():
            conn.close()
        self.connections.clear()

    def get_vm_info_from_state(self, project_name: str) -> Dict[str, Dict]:
        """
        Read VM information from state.yml.

        Args:
            project_name: Name of the project

        Returns:
            Dictionary mapping VM names to their info (IP, role, etc.)
        """
        state_file = self.project_root / "projects" / project_name / "state.yml"

        if not state_file.exists():
            return {}

        try:
            with open(state_file, "r") as f:
                state = yaml.safe_load(f)

            vms = {}
            if "vms" in state:
                for vm_name, vm_data in state["vms"].items():
                    vms[vm_name] = {
                        "name": vm_name,
                        "external_ip": vm_data.get("external_ip"),
                        "internal_ip": vm_data.get("internal_ip"),
                        "role": vm_data.get("role", vm_name),
                        "status": vm_data.get("status", "unknown"),
                    }

            return vms
        except Exception as e:
            raise Exception(f"Failed to read state.yml: {str(e)}")

    def get_ssh_key_path(self, project_name: str) -> str:
        """
        Get SSH key path from config.yml.

        Args:
            project_name: Name of the project

        Returns:
            Path to SSH private key
        """
        config_file = self.project_root / "projects" / project_name / "config.yml"

        if not config_file.exists():
            raise Exception(f"Config file not found for project {project_name}")

        try:
            with open(config_file, "r") as f:
                config = yaml.safe_load(f)

            # Get SSH key path from cloud.ssh.key_path
            ssh_key_path = config.get("cloud", {}).get("ssh", {}).get("key_path")

            if not ssh_key_path:
                raise Exception(
                    "SSH key_path not found in config.yml cloud.ssh section"
                )

            # Expand home directory if needed
            ssh_key_path = Path(ssh_key_path).expanduser()

            return str(ssh_key_path)
        except Exception as e:
            raise Exception(f"Failed to read SSH key path: {str(e)}")
