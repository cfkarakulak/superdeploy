"""Orchestrator configuration loader"""

from pathlib import Path
from typing import Dict, Any, Optional
import yaml


class OrchestratorConfig:
    """Manages global orchestrator configuration"""

    def __init__(self, config_path: Path):
        """
        Initialize orchestrator config

        Args:
            config_path: Path to orchestrator.yml
        """
        self.config_path = config_path
        self.base_path = (
            config_path.parent.parent
        )  # shared/orchestrator/config.yml -> shared/
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load orchestrator configuration from YAML"""
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Orchestrator config not found: {self.config_path}\n"
                f"This file should exist in shared/orchestrator.yml"
            )

        with open(self.config_path, "r") as f:
            config = yaml.safe_load(f)

        if not config:
            raise ValueError(f"Empty orchestrator config: {self.config_path}")

        # Auto-allocate subnets if not specified
        if "network" not in config:
            config["network"] = {}

        subnet_allocated = False
        if "docker_subnet" not in config["network"]:
            from cli.subnet_allocator import SubnetAllocator

            config["network"]["docker_subnet"] = (
                SubnetAllocator.get_orchestrator_docker_subnet()
            )
            subnet_allocated = True

        # Save allocated subnet back to config file for transparency
        if subnet_allocated:
            self._save_config(config)

        return config

    def _save_config(self, config: Dict[str, Any]) -> None:
        """Save configuration back to yaml file"""
        try:
            with open(self.config_path, "w") as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        except Exception:
            # Silently fail - not critical
            pass

    def is_deployed(self) -> bool:
        """Check if orchestrator is already deployed by checking if IP exists in .env"""
        return self.get_ip() is not None

    def get_ip(self) -> Optional[str]:
        """Get orchestrator IP from .env file"""
        env_path = self.base_path / "orchestrator" / ".env"
        if env_path.exists():
            try:
                with open(env_path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("ORCHESTRATOR_IP="):
                            ip = line.split("=", 1)[1].strip()
                            if ip:
                                return ip
            except:
                pass

        return None

    def get_vm_config(self) -> Dict[str, Any]:
        """Get VM configuration for orchestrator"""
        return self.config.get("vm", {})

    def get_forgejo_config(self) -> Dict[str, Any]:
        """Get Forgejo configuration"""
        return self.config.get("forgejo", {})

    def get_network_config(self) -> Dict[str, Any]:
        """Get network configuration"""
        return self.config.get("network", {})

    def mark_deployed(self, ip: str) -> None:
        """
        Mark orchestrator as deployed and save IP to .env + all project secrets.yml

        Args:
            ip: External IP of orchestrator VM
        """
        # 1. Save to shared/orchestrator/.env (backward compatibility)
        env_path = self.base_path / "orchestrator" / ".env"

        # Read existing .env content
        env_lines = []
        ip_found = False

        if env_path.exists():
            with open(env_path, "r") as f:
                for line in f:
                    if line.strip().startswith("ORCHESTRATOR_IP="):
                        env_lines.append(f"ORCHESTRATOR_IP={ip}\n")
                        ip_found = True
                    else:
                        env_lines.append(line)

        # If ORCHESTRATOR_IP not found, append it
        if not ip_found:
            env_lines.append(f"ORCHESTRATOR_IP={ip}\n")

        # Write back to .env
        with open(env_path, "w") as f:
            f.writelines(env_lines)

        # 2. Update all project secrets.yml files
        self._update_project_secrets(ip)

    def _update_project_secrets(self, ip: str) -> None:
        """
        Update ORCHESTRATOR_IP in all project secrets.yml files

        Args:
            ip: Orchestrator IP address
        """
        projects_dir = self.base_path.parent / "projects"

        if not projects_dir.exists():
            return

        # Find all secrets.yml files
        for project_dir in projects_dir.iterdir():
            if not project_dir.is_dir():
                continue

            secrets_file = project_dir / "secrets.yml"
            if not secrets_file.exists():
                continue

            try:
                # Load existing passwords
                with open(secrets_file, "r") as f:
                    secrets_data = yaml.safe_load(f) or {}

                # Ensure secrets.shared exists
                if "secrets" not in secrets_data:
                    secrets_data["secrets"] = {}
                if "shared" not in secrets_data["secrets"]:
                    secrets_data["secrets"]["shared"] = {}

                # Update ORCHESTRATOR_IP
                secrets_data["secrets"]["shared"]["ORCHESTRATOR_IP"] = ip

                # Save back
                with open(secrets_file, "w") as f:
                    yaml.dump(
                        secrets_data, f, default_flow_style=False, sort_keys=False
                    )

            except Exception as e:
                # Don't fail if one project fails
                print(f"Warning: Could not update {secrets_file}: {e}")
                continue

    def to_terraform_vars(
        self, project_id: str, ssh_pub_key_path: str
    ) -> Dict[str, Any]:
        """
        Convert to Terraform variables format

        Args:
            project_id: GCP project ID (from config)
            ssh_pub_key_path: Path to SSH public key (from config)

        Returns:
            Dictionary suitable for Terraform tfvars
        """
        vm_config = self.get_vm_config()
        network_config = self.get_network_config()
        gcp_config = self.config.get("gcp", {})

        # Use reserved orchestrator subnet
        from cli.subnet_allocator import SubnetAllocator

        orchestrator_subnet = SubnetAllocator.get_orchestrator_subnet()

        return {
            "project_id": project_id,
            "project_name": "orchestrator",
            "region": gcp_config.get("region", "us-central1"),
            "zone": gcp_config.get("zone", "us-central1-a"),
            "vm_groups": {
                "main-0": {
                    "role": "main",
                    "index": 0,
                    "machine_type": vm_config.get("machine_type", "e2-medium"),
                    "disk_size": vm_config.get("disk_size", 50),
                    "tags": ["main", "orchestrator", "forgejo", "ssh"],
                    "labels": {
                        "role": "orchestrator",
                        "shared": "true",
                        "has_forgejo": "true",
                    },
                }
            },
            "subnet_cidr": orchestrator_subnet,  # Use reserved subnet
            "network_name": network_config.get("vpc_name", "superdeploy-network"),
            "ssh_pub_key_path": ssh_pub_key_path,
        }

    def to_ansible_vars(self) -> Dict[str, Any]:
        """
        Convert to Ansible variables format

        Returns:
            Dictionary suitable for Ansible extra vars
        """
        forgejo_config = self.get_forgejo_config()

        # Monitoring is always enabled
        grafana_config = self.config.get("grafana", {})
        prometheus_config = self.config.get("prometheus", {})
        caddy_config = self.config.get("caddy", {})

        enabled_addons = ["forgejo", "monitoring"]
        addon_configs = {
            "forgejo": forgejo_config,
            "monitoring": {"grafana": grafana_config, "prometheus": prometheus_config},
        }

        # Add Caddy if enabled (for monitoring reverse proxy)
        if caddy_config.get("enabled", False):
            enabled_addons.append("caddy")
            addon_configs["caddy"] = caddy_config

        # Get project info for ssl_email
        project_config = self.config.get("project", {})

        # Get network config
        network_config = self.config.get("network", {})

        return {
            "project_name": "orchestrator",
            "project_config": {
                "project": {
                    "name": "orchestrator",
                    "ssl_email": project_config.get("ssl_email", ""),
                },
                "network": network_config,  # Add network config for subnet allocation
                "addons": {"forgejo": forgejo_config},
                "grafana": grafana_config,
                "prometheus": prometheus_config,
                "forgejo": forgejo_config,  # Add forgejo at root level for env.yml path resolution
            },
            "enabled_addons": enabled_addons,
            "addon_configs": addon_configs,
        }


class OrchestratorLoader:
    """Loads orchestrator configuration"""

    def __init__(self, shared_dir: Path):
        """
        Initialize orchestrator loader

        Args:
            shared_dir: Path to shared directory
        """
        self.shared_dir = Path(shared_dir)
        self.orchestrator_dir = self.shared_dir / "orchestrator"
        self.config_path = self.orchestrator_dir / "config.yml"
        self.env_path = self.orchestrator_dir / ".env"

    def load(self) -> OrchestratorConfig:
        """
        Load orchestrator configuration

        Returns:
            OrchestratorConfig instance

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If configuration is invalid
        """
        return OrchestratorConfig(self.config_path)

    def exists(self) -> bool:
        """Check if orchestrator config exists"""
        return self.config_path.exists()
