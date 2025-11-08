"""Orchestrator state management"""

import yaml
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional


class OrchestratorStateManager:
    """Manages orchestrator deployment state"""

    def __init__(self, shared_dir: Path):
        self.shared_dir = Path(shared_dir)
        self.state_file = shared_dir / "orchestrator" / "state.yml"
        self.config_file = shared_dir / "orchestrator" / "config.yml"

    def load_state(self) -> Dict[str, Any]:
        """Load orchestrator state"""
        if not self.state_file.exists():
            return {}

        with open(self.state_file, "r") as f:
            return yaml.safe_load(f) or {}

    def save_state(self, state: Dict[str, Any]):
        """Save state to file with config hash"""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # Add timestamp and config hash (like project state manager)
        state["last_applied"] = {
            "timestamp": datetime.now().isoformat(),
            "config_hash": self._calculate_config_hash(),
        }

        with open(self.state_file, "w") as f:
            yaml.dump(state, f, default_flow_style=False, sort_keys=False)

    def _calculate_config_hash(self) -> str:
        """Calculate hash of config.yml for change detection"""
        if not self.config_file.exists():
            return ""

        with open(self.config_file, "rb") as f:
            content = f.read()
            return hashlib.sha256(content).hexdigest()[:12]

    def mark_deployed(
        self,
        ip: str,
        vm_name: str = "orchestrator-main-0",
        vm_config: dict = None,
        config: dict = None,
    ):
        """Mark orchestrator as deployed with IP, VM details, and full config"""
        state = self.load_state()

        # Save VM details similar to project state
        vm_data = {
            "name": vm_name,
            "external_ip": ip,
            "deployed_at": datetime.now().isoformat(),
            "status": "running",
        }

        # Add VM config if provided
        if vm_config:
            vm_data.update(
                {
                    "machine_type": vm_config.get("machine_type"),
                    "disk_size": vm_config.get("disk_size"),
                    "services": ["monitoring"],
                }
            )

        state.update(
            {
                "deployed": True,
                "orchestrator_ip": ip,
                "vm": vm_data,
                "addons": {
                    "monitoring": {"status": "installed"},
                },
            }
        )

        # Store full config for change detection (like project state manager)
        if config:
            state["config"] = config

        self.save_state(state)

        # Also update all project secrets.yml files
        self._update_project_secrets(ip)

    def _update_project_secrets(self, ip: str):
        """Update ORCHESTRATOR_IP in all project secrets.yml"""
        projects_dir = self.shared_dir.parent / "projects"

        if not projects_dir.exists():
            return

        for project_dir in projects_dir.iterdir():
            if not project_dir.is_dir():
                continue

            secrets_file = project_dir / "secrets.yml"
            if not secrets_file.exists():
                continue

            try:
                with open(secrets_file, "r") as f:
                    secrets_data = yaml.safe_load(f) or {}

                if "secrets" not in secrets_data:
                    secrets_data["secrets"] = {}
                if "shared" not in secrets_data["secrets"]:
                    secrets_data["secrets"]["shared"] = {}

                secrets_data["secrets"]["shared"]["ORCHESTRATOR_IP"] = ip

                with open(secrets_file, "w") as f:
                    yaml.dump(
                        secrets_data, f, default_flow_style=False, sort_keys=False
                    )

            except Exception as e:
                print(f"Warning: Could not update {secrets_file}: {e}")

    def get_ip(self) -> Optional[str]:
        """Get orchestrator IP from state"""
        state = self.load_state()
        return state.get("orchestrator_ip")

    def is_deployed(self) -> bool:
        """Check if orchestrator is deployed"""
        state = self.load_state()
        return state.get("deployed", False) and bool(state.get("orchestrator_ip"))

    def mark_destroyed(self):
        """Mark orchestrator as destroyed"""
        state = {"deployed": False, "destroyed_at": datetime.now().isoformat()}
        self.save_state(state)

        # Remove ORCHESTRATOR_IP from all project secrets
        self._remove_orchestrator_ip_from_projects()

    def _remove_orchestrator_ip_from_projects(self):
        """Remove ORCHESTRATOR_IP from all project secrets.yml"""
        projects_dir = self.shared_dir.parent / "projects"

        if not projects_dir.exists():
            return

        for project_dir in projects_dir.iterdir():
            if not project_dir.is_dir():
                continue

            secrets_file = project_dir / "secrets.yml"
            if not secrets_file.exists():
                continue

            try:
                with open(secrets_file, "r") as f:
                    secrets_data = yaml.safe_load(f) or {}

                # Remove ORCHESTRATOR_IP from shared secrets
                if (
                    "secrets" in secrets_data
                    and "shared" in secrets_data["secrets"]
                    and "ORCHESTRATOR_IP" in secrets_data["secrets"]["shared"]
                ):
                    del secrets_data["secrets"]["shared"]["ORCHESTRATOR_IP"]

                    with open(secrets_file, "w") as f:
                        yaml.dump(
                            secrets_data, f, default_flow_style=False, sort_keys=False
                        )

            except Exception as e:
                print(f"Warning: Could not update {secrets_file}: {e}")
