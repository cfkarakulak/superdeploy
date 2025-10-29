"""Orchestrator configuration loader"""

from pathlib import Path
from typing import Dict, Any, Optional
import yaml
from datetime import datetime


class OrchestratorConfig:
    """Manages global orchestrator configuration"""

    def __init__(self, config_path: Path):
        """
        Initialize orchestrator config

        Args:
            config_path: Path to orchestrator.yml
        """
        self.config_path = config_path
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

        return config

    def is_deployed(self) -> bool:
        """Check if orchestrator is already deployed"""
        # Check both config state and Terraform state
        config_deployed = self.config.get("state", {}).get("deployed", False)
        
        # Also check if Terraform state exists
        from pathlib import Path
        terraform_state = Path(__file__).parent.parent.parent / "shared" / "terraform" / "terraform.tfstate.d" / "orchestrator" / "terraform.tfstate"
        
        if terraform_state.exists():
            import json
            try:
                with open(terraform_state, 'r') as f:
                    state_data = json.load(f)
                    # Check if there are any resources
                    resources = state_data.get('resources', [])
                    if resources:
                        return True
            except:
                pass
        
        return config_deployed

    def get_ip(self) -> Optional[str]:
        """Get orchestrator IP if deployed"""
        # First try config
        config_ip = self.config.get("state", {}).get("ip")
        if config_ip:
            return config_ip
        
        # Fallback: Try to get from Terraform state
        from pathlib import Path
        terraform_state = Path(__file__).parent.parent.parent / "shared" / "terraform" / "terraform.tfstate.d" / "orchestrator" / "terraform.tfstate"
        
        if terraform_state.exists():
            import json
            try:
                with open(terraform_state, 'r') as f:
                    state_data = json.load(f)
                    # Get IP from outputs
                    outputs = state_data.get('outputs', {})
                    vm_ips = outputs.get('vm_public_ips', {}).get('value', {})
                    ip = vm_ips.get('main-0')
                    if ip:
                        # Update config with this IP
                        self.mark_deployed(ip)
                        return ip
            except:
                pass
        
        return None

    def should_deploy(self) -> bool:
        """Check if orchestrator should be deployed"""
        mode = self.config.get("deployment_mode", "auto")
        
        if mode == "skip":
            return False
        elif mode == "manual":
            return False
        elif mode == "auto":
            return not self.is_deployed()
        
        return False

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
        Mark orchestrator as deployed and save IP

        Args:
            ip: External IP of orchestrator VM
        """
        if "state" not in self.config:
            self.config["state"] = {}

        self.config["state"]["deployed"] = True
        self.config["state"]["ip"] = ip
        self.config["state"]["last_updated"] = datetime.utcnow().isoformat()

        # Save to file
        with open(self.config_path, "w") as f:
            yaml.dump(self.config, f, default_flow_style=False, sort_keys=False)

    def to_terraform_vars(self, project_id: str, ssh_pub_key_path: str) -> Dict[str, Any]:
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
        gcp_config = self.config.get('gcp', {})

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
            "subnet_cidr": network_config.get("subnet_cidr", "10.128.0.0/20"),
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

        return {
            "project_name": "orchestrator",
            "project_config": {
                "project": "orchestrator",
                "addons": {
                    "forgejo": forgejo_config
                },
            },
            "enabled_addons": ["forgejo"],
            "addon_configs": {
                "forgejo": forgejo_config
            },
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
