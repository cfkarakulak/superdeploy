"""Orchestrator state management"""

import yaml
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class OrchestratorState:
    """Orchestrator deployment state."""

    deployed: bool
    orchestrator_ip: Optional[str] = None
    vm: Optional[Dict[str, Any]] = None
    addons: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = None
    last_applied: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OrchestratorState":
        """Create from dict."""
        return cls(
            deployed=data.get("deployed", False),
            orchestrator_ip=data.get("orchestrator_ip"),
            vm=data.get("vm"),
            addons=data.get("addons"),
            config=data.get("config"),
            last_applied=data.get("last_applied"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        result = {"deployed": self.deployed}
        if self.orchestrator_ip:
            result["orchestrator_ip"] = self.orchestrator_ip
        if self.vm:
            result["vm"] = self.vm
        if self.addons:
            result["addons"] = self.addons
        if self.config:
            result["config"] = self.config
        if self.last_applied:
            result["last_applied"] = self.last_applied
        return result


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
        """Save state to file with config hash and nice formatting"""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # Add timestamp and config hash (like project state manager)
        state["last_applied"] = {
            "timestamp": datetime.now().isoformat(),
            "config_hash": self._calculate_config_hash(),
        }

        # Build formatted YAML manually for better readability
        lines = []

        # Header
        lines.append("# " + "=" * 77)
        lines.append("# Orchestrator - Deployment State")
        lines.append("# " + "=" * 77)
        lines.append(
            "# This file tracks the current state of orchestrator infrastructure"
        )
        lines.append("# WARNING: Do not manually edit this file")
        lines.append("# " + "=" * 77)
        lines.append("")

        # Basic info
        if "deployed" in state:
            lines.append(f"deployed: {str(state['deployed']).lower()}")
        if "orchestrator_ip" in state:
            lines.append(f"orchestrator_ip: {state['orchestrator_ip']}")
            lines.append("")

        # VM section
        if "vm" in state and state["vm"]:
            lines.append("# " + "=" * 77)
            lines.append("# Virtual Machine")
            lines.append("# " + "=" * 77)
            lines.append("vm:")
            for key, value in state["vm"].items():
                if isinstance(value, list):
                    if value:
                        lines.append(f"  {key}:")
                        for item in value:
                            lines.append(f"    - {item}")
                    else:
                        lines.append(f"  {key}: []")
                elif isinstance(value, bool):
                    lines.append(f"  {key}: {str(value).lower()}")
                else:
                    lines.append(f"  {key}: {value}")
            lines.append("")

        # Addons section
        if "addons" in state and state["addons"]:
            lines.append("# " + "=" * 77)
            lines.append("# Installed Addons")
            lines.append("# " + "=" * 77)
            lines.append("addons:")
            for addon_name, addon_data in state["addons"].items():
                lines.append(f"  {addon_name}:")
                if isinstance(addon_data, dict):
                    for key, value in addon_data.items():
                        lines.append(f"    {key}: {value}")
            lines.append("")

        # Config section
        if "config" in state and state["config"]:
            lines.append("# " + "=" * 77)
            lines.append("# Applied Configuration")
            lines.append("# " + "=" * 77)
            lines.append("config:")
            lines.append(self._format_dict_section(state["config"], indent=1))
            lines.append("")

        # Last applied section
        if "last_applied" in state:
            lines.append("# " + "=" * 77)
            lines.append("# Last Applied")
            lines.append("# " + "=" * 77)
            lines.append("last_applied:")
            for key, value in state["last_applied"].items():
                lines.append(f"  {key}: {value}")
            lines.append("")

        # Write formatted content
        with open(self.state_file, "w") as f:
            f.write("\n".join(lines))

    def _format_dict_section(self, data: dict, indent: int = 0) -> str:
        """Recursively format dict to YAML string"""
        lines = []
        prefix = "  " * indent

        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"{prefix}{key}:")
                lines.append(self._format_dict_section(value, indent + 1))
            elif isinstance(value, list):
                if value:
                    lines.append(f"{prefix}{key}:")
                    for item in value:
                        if isinstance(item, dict):
                            lines.append(f"{prefix}  -")
                            for k, v in item.items():
                                lines.append(f"{prefix}    {k}: {v}")
                        else:
                            lines.append(f"{prefix}  - {item}")
                else:
                    lines.append(f"{prefix}{key}: []")
            elif isinstance(value, bool):
                lines.append(f"{prefix}{key}: {str(value).lower()}")
            else:
                lines.append(f"{prefix}{key}: {value}")

        return "\n".join(lines)

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
