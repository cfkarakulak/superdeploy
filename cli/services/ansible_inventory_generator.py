"""Service for generating Ansible inventory files."""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional


class AnsibleInventoryGenerator:
    """Generates Ansible inventory files dynamically from environment variables."""

    def __init__(self, ansible_dir: Path):
        """
        Initialize inventory generator.

        Args:
            ansible_dir: Path to ansible directory
        """
        self.ansible_dir = Path(ansible_dir)

    def generate_inventory(
        self,
        env: Dict[str, str],
        project_name: str,
        orchestrator_ip: Optional[str] = None,
        orchestrator_internal_ip: Optional[str] = None,
        project_config: Optional[Any] = None,
    ) -> Path:
        """
        Generate Ansible inventory file dynamically from environment variables.

        Args:
            env: Environment variables dict
            project_name: Project name
            orchestrator_ip: Orchestrator VM IP (from global config)
            orchestrator_internal_ip: Orchestrator internal IP for VPC peering (optional)
            project_config: Project configuration object (to get VM services)

        Returns:
            Path to generated inventory file
        """
        # Extract VM groups from environment
        vm_groups = self._extract_vm_groups(env, project_name)

        # Get VM services and apps mapping
        vm_services_map, vm_apps_map = self._build_vm_mappings(project_config)

        # Build inventory content
        inventory_content = self._build_inventory_content(
            vm_groups,
            vm_services_map,
            vm_apps_map,
            orchestrator_ip,
            orchestrator_internal_ip,
        )

        # Write inventory file
        inventory_path = self.ansible_dir / "inventories" / f"{project_name}.ini"
        inventory_path.parent.mkdir(parents=True, exist_ok=True)

        with open(inventory_path, "w") as f:
            f.write(inventory_content)

        return inventory_path

    def _extract_vm_groups(
        self, env: Dict[str, str], project_name: str
    ) -> Dict[str, List[Dict[str, str]]]:
        """
        Extract VM groups from environment variables.

        Format: {ROLE}_{INDEX}_EXTERNAL_IP -> {role: [vm_info, ...]}

        Args:
            env: Environment variables dict
            project_name: Project name

        Returns:
            Dict mapping roles to VM info lists
        """
        vm_groups = {}

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

        return vm_groups

    def _build_vm_mappings(
        self, project_config: Optional[Any]
    ) -> tuple[Dict[str, List[str]], Dict[str, List[str]]]:
        """
        Build VM services and apps mapping from project config.

        Args:
            project_config: Project configuration object

        Returns:
            Tuple of (vm_services_map, vm_apps_map)
        """
        vm_services_map = {}
        vm_apps_map = {}

        if not project_config:
            return vm_services_map, vm_apps_map

        vms_config = project_config.raw_config.get("vms", {})
        apps_config = project_config.raw_config.get("apps", {})

        # Build services map per VM
        for vm_role, vm_def in vms_config.items():
            services = list(vm_def.get("services", []))

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

        return vm_services_map, vm_apps_map

    def _build_inventory_content(
        self,
        vm_groups: Dict[str, List[Dict[str, str]]],
        vm_services_map: Dict[str, List[str]],
        vm_apps_map: Dict[str, List[str]],
        orchestrator_ip: Optional[str],
        orchestrator_internal_ip: Optional[str] = None,
    ) -> str:
        """
        Build inventory file content.

        Args:
            vm_groups: VM groups dict
            vm_services_map: Services per VM role
            vm_apps_map: Apps per VM role
            orchestrator_ip: Orchestrator IP (optional)
            orchestrator_internal_ip: Orchestrator internal IP for VPC peering (optional)

        Returns:
            Inventory file content
        """
        inventory_lines = []

        # Add orchestrator group if available (for runner token generation)
        if orchestrator_ip:
            inventory_lines.append("[orchestrator]")
            # Include internal_ip for Promtail/Loki communication via VPC peering
            internal_ip_str = (
                f" internal_ip={orchestrator_internal_ip}"
                if orchestrator_internal_ip
                else ""
            )
            inventory_lines.append(
                f"orchestrator-main-0 ansible_host={orchestrator_ip} "
                f"ansible_user=superdeploy vm_role=orchestrator{internal_ip_str}"
            )
            inventory_lines.append("")

        # Add project VM groups
        for role in sorted(vm_groups.keys()):
            inventory_lines.append(f"[{role}]")
            for vm in sorted(vm_groups[role], key=lambda x: x["name"]):
                # Get services and apps for this VM role
                services = vm_services_map.get(role, [])
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

        # Add [all:vars] section with orchestrator_internal_ip for Promtail
        if orchestrator_internal_ip:
            inventory_lines.append("[all:vars]")
            inventory_lines.append("ansible_python_interpreter=/usr/bin/python3")
            inventory_lines.append(
                f"orchestrator_internal_ip={orchestrator_internal_ip}"
            )
            inventory_lines.append("")

        return "\n".join(inventory_lines)
