"""
Ansible Runner

Executes Ansible playbooks with clean output formatting and logging.
"""

import subprocess
import sys
import os
import selectors
from pathlib import Path
from typing import Optional, Any
from cli.ansible_tree_renderer import AnsibleTreeRenderer


class AnsibleRunner:
    """
    Run Ansible playbooks with clean tree view using custom callback.

    Responsibilities:
    - Execute Ansible commands
    - Manage output formatting
    - Handle logging to file
    - Support verbose and quiet modes
    """

    def __init__(self, logger, title: str = "Configuring", verbose: bool = False):
        """
        Initialize Ansible runner.

        Args:
            logger: DeployLogger instance for logging
            title: Title for the operation
            verbose: Whether to show verbose output
        """
        self.logger = logger
        self.title = title
        self.verbose = verbose

    def run(self, ansible_cmd: str, cwd: Path) -> int:
        """
        Run Ansible command with appropriate output handling.

        Args:
            ansible_cmd: Complete Ansible command to execute
            cwd: Working directory for execution

        Returns:
            Exit code from Ansible

        Raises:
            AnsibleError: If Ansible execution fails critically
        """
        self.logger.log_command(ansible_cmd)

        # Create Ansible-specific log file (raw output, no prefixes)
        ansible_log_path = (
            self.logger.log_path.parent / f"{self.logger.log_path.stem}_ansible.log"
        )

        self.logger.log(f"Ansible detailed log: {ansible_log_path}", "INFO")

        # Setup environment
        env = self._build_environment(ansible_log_path)

        if self.verbose:
            return self._run_verbose(ansible_cmd, cwd, env)
        else:
            return self._run_quiet(ansible_cmd, cwd, env)

    def _build_environment(self, log_path: Path) -> dict:
        """
        Build environment variables for Ansible execution.

        Args:
            log_path: Path to Ansible log file

        Returns:
            Dictionary of environment variables
        """
        # Get Python version for collections path
        python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
        venv_root = Path(sys.executable).parent.parent

        # Build paths
        collections_path = (
            venv_root / "lib" / python_version / "site-packages" / "ansible_collections"
        )
        mitogen_strategy_path = (
            venv_root
            / "lib"
            / python_version
            / "site-packages"
            / "ansible_mitogen"
            / "plugins"
            / "strategy"
        )

        # Callback plugins path - find superdeploy root from this file
        superdeploy_root = Path(__file__).parent.parent
        callback_plugins_path = (
            superdeploy_root / "shared" / "ansible" / "plugins" / "callback"
        )

        env = os.environ.copy()
        env.update(
            {
                "PYTHONUNBUFFERED": "1",
                "ANSIBLE_STDOUT_CALLBACK": "default",  # Always use default, we parse it
                "ANSIBLE_CALLBACKS_ENABLED": "profile_tasks",  # Enable timing callback
                "ANSIBLE_DISPLAY_SKIPPED_HOSTS": "true",  # Show skipped tasks
                "ANSIBLE_FORCE_COLOR": "true" if self.verbose else "false",
                "ANSIBLE_LOG_PATH": str(log_path),
                "ANSIBLE_COLLECTIONS_PATH": str(collections_path),
                "ANSIBLE_COLLECTIONS_PATHS": str(collections_path),
                "ANSIBLE_STRATEGY_PLUGINS": str(mitogen_strategy_path),
            }
        )

        return env

    def _run_verbose(self, cmd: str, cwd: Path, env: dict) -> int:
        """
        Run Ansible in verbose mode (direct terminal output).

        Args:
            cmd: Ansible command
            cwd: Working directory
            env: Environment variables

        Returns:
            Exit code
        """
        # VERBOSE MODE: Let Ansible write directly to terminal
        # This preserves colors, formatting, and native Ansible output
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=str(cwd),
            env=env,
        )
        return result.returncode

    def _run_quiet(self, cmd: str, cwd: Path, env: dict) -> int:
        """
        Run Ansible in quiet mode (captured output with tree view).

        Args:
            cmd: Ansible command
            cwd: Working directory
            env: Environment variables

        Returns:
            Exit code
        """
        # Initialize tree renderer (no Rich needed - uses ANSI codes)
        tree_renderer = AnsibleTreeRenderer()

        # NON-VERBOSE MODE: Capture and display with custom tree rendering
        process = subprocess.Popen(
            cmd,
            shell=True,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,  # Line buffered
            env=env,
        )

        # Use selectors for non-blocking read
        sel = selectors.DefaultSelector()
        sel.register(process.stdout, selectors.EVENT_READ)

        # Pass through output with tree rendering
        while True:
            # Check if process is still running
            if process.poll() is not None:
                # Process finished, read any remaining output
                break

            # Wait for data with timeout
            events = sel.select(timeout=0.1)
            if events:
                line = process.stdout.readline()
                if not line:
                    break

                line_stripped = line.rstrip()

                # Log to main log file
                try:
                    self.logger.log_output(line_stripped, "ansible")
                except (BlockingIOError, OSError):
                    pass

                # Process line through tree renderer
                tree_renderer.process_line(line_stripped)

        # Close selector
        sel.close()

        # Read any remaining output after process finished
        if process.stdout:
            remaining = process.stdout.read()
            if remaining:
                for line in remaining.splitlines():
                    line_stripped = line.rstrip()
                    try:
                        self.logger.log_output(line_stripped, "ansible")
                    except (BlockingIOError, OSError):
                        pass
                    # Process remaining lines
                    tree_renderer.process_line(line_stripped)

        # Finalize tree rendering
        tree_renderer.finalize()

        returncode = process.wait()
        return returncode


class AnsibleInventoryGenerator:
    """
    Generates Ansible inventory files from project configuration.

    Responsibilities:
    - Generate INI format inventory
    - Map VMs to groups
    - Assign services to VMs
    - Handle orchestrator inclusion
    """

    @staticmethod
    def generate(
        env: dict,
        ansible_dir: Path,
        project_name: str,
        orchestrator_ip: Optional[str] = None,
        project_config: Optional[Any] = None,
    ) -> Path:
        """
        Generate Ansible inventory file dynamically from environment variables.

        Args:
            env: Environment variables dict
            ansible_dir: Path to ansible directory
            project_name: Project name
            orchestrator_ip: Orchestrator VM IP (from global config)
            project_config: Project configuration object

        Returns:
            Path to generated inventory file
        """
        import json

        # Extract VM groups from environment variables
        # Format: {ROLE}_{INDEX}_EXTERNAL_IP
        vm_groups: dict = {}

        for key, value in env.items():
            if key.endswith("_EXTERNAL_IP"):
                # Parse VM key from env var (e.g., "CORE_0_EXTERNAL_IP" -> "core-0")
                vm_key = key.replace("_EXTERNAL_IP", "").lower().replace("_", "-")
                # Extract role from vm_key (e.g., "core-0" -> "core")
                role = vm_key.rsplit("-", 1)[0]

                if role not in vm_groups:
                    vm_groups[role] = []

                vm_info = {
                    "name": f"{project_name}-{vm_key}",
                    "host": value,
                    "user": env.get("SSH_USER", "superdeploy"),
                    "role": role,
                }

                vm_groups[role].append(vm_info)

        # Get VM services and apps from project config
        vm_services_map: dict = {}
        vm_apps_map: dict = {}

        if project_config:
            vms_config = project_config.raw_config.get("vms", {})
            apps_config = project_config.raw_config.get("apps", {})

            # Build services map per VM
            for vm_role, vm_def in vms_config.items():
                services = list(vm_def.get("services", []))  # Make a copy

                # Always add caddy to every VM (for domain management and reverse proxy)
                if "caddy" not in services:
                    services.append("caddy")

                vm_services_map[vm_role] = services

            # Build apps map per VM (which apps are assigned to which VM)
            for app_name, app_config in apps_config.items():
                app_vm = app_config.get("vm", "app")  # Default to 'app' VM
                if app_vm not in vm_apps_map:
                    vm_apps_map[app_vm] = []
                vm_apps_map[app_vm].append(app_name)

        # Build inventory content
        inventory_lines = []

        # Add orchestrator group if available (for runner token generation)
        if orchestrator_ip:
            inventory_lines.append("[orchestrator]")
            inventory_lines.append(
                f"orchestrator-main-0 ansible_host={orchestrator_ip} "
                f"ansible_user=superdeploy vm_role=orchestrator"
            )
            inventory_lines.append("")

        # Add project VM groups
        for role in sorted(vm_groups.keys()):
            inventory_lines.append(f"[{role}]")
            for vm in sorted(vm_groups[role], key=lambda x: x["name"]):
                # Get services for this VM role
                services = vm_services_map.get(role, [])
                # Get apps for this VM role
                apps = vm_apps_map.get(role, [])

                # Convert to JSON and properly quote for INI format
                services_json = json.dumps(services).replace('"', '\\"')
                apps_json = json.dumps(apps).replace('"', '\\"')

                inventory_lines.append(
                    f"{vm['name']} ansible_host={vm['host']} "
                    f"ansible_user={vm['user']} vm_role={role} "
                    f'vm_services="{services_json}" vm_apps="{apps_json}"'
                )
            inventory_lines.append("")  # Empty line between groups

        inventory_content = "\n".join(inventory_lines)

        # Write inventory file
        inventory_path = ansible_dir / "inventories" / f"{project_name}.ini"
        inventory_path.parent.mkdir(parents=True, exist_ok=True)

        with open(inventory_path, "w") as f:
            f.write(inventory_content)

        return inventory_path
