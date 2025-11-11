"""Orchestrator secret management"""

import yaml
import secrets as py_secrets
from pathlib import Path
from typing import Dict, Any


class OrchestratorSecretManager:
    """Manages orchestrator secrets (Grafana passwords)"""

    def __init__(self, shared_dir: Path):
        self.shared_dir = Path(shared_dir)
        self.secrets_file = shared_dir / "orchestrator" / "secrets.yml"

    def load_secrets(self) -> Dict[str, Any]:
        """Load orchestrator secrets.yml"""
        if not self.secrets_file.exists():
            return {}

        with open(self.secrets_file, "r") as f:
            return yaml.safe_load(f) or {}

    def save_secrets(self, secrets: Dict[str, Any]):
        """Save secrets to secrets.yml with nice formatting (flat structure)"""
        self.secrets_file.parent.mkdir(parents=True, exist_ok=True)

        # Build formatted YAML manually for better readability
        lines = []
        lines.append("# " + "=" * 77)
        lines.append("# Orchestrator - Secrets Configuration")
        lines.append("# " + "=" * 77)
        lines.append("# WARNING: This file contains sensitive information")
        lines.append("# Keep this file secure and never commit to version control")
        lines.append("# " + "=" * 77)
        lines.append("#")
        lines.append("# Required Secrets:")
        lines.append("#   - GRAFANA_ADMIN_PASSWORD: Auto-generated on first deployment")
        lines.append("#")
        lines.append("# Optional Secrets (for email alerts):")
        lines.append(
            "#   - SMTP_PASSWORD: Add if you want Grafana to send email alerts"
        )
        lines.append("#")
        lines.append(
            "# Note: GRAFANA_ADMIN_USER is configured in config.yml (default: 'admin')"
        )
        lines.append("# Note: Monitoring addon reads from flat secrets (not nested)")
        lines.append("# " + "=" * 77)
        lines.append("")
        lines.append("secrets:")

        secrets_data = secrets.get("secrets", {})
        if secrets_data:
            for key, value in sorted(secrets_data.items()):
                lines.append(f"  {key}: {value}")
        else:
            lines.append("  GRAFANA_ADMIN_PASSWORD: ''  # Will be auto-generated")
            lines.append("  SMTP_PASSWORD: ''  # Optional")

        # Write formatted content
        with open(self.secrets_file, "w") as f:
            f.write("\n".join(lines))

        # Restrictive permissions
        self.secrets_file.chmod(0o600)

    def initialize_secrets(self) -> Dict[str, str]:
        """Generate and save initial secrets if they don't exist"""
        secrets_data = self.load_secrets()

        # If secrets already exist, return them
        if secrets_data.get("secrets"):
            return secrets_data["secrets"]

        # Generate new secrets
        secrets = {
            "GRAFANA_ADMIN_PASSWORD": py_secrets.token_urlsafe(32),
        }

        secrets_data = {"secrets": secrets}

        self.save_secrets(secrets_data)
        return secrets

    def get_secret(self, key: str) -> str:
        """Get specific secret"""
        secrets_data = self.load_secrets()
        return secrets_data.get("secrets", {}).get(key, "")

    def add_secret(self, key: str, value: str):
        """Add or update secret"""
        secrets_data = self.load_secrets()

        if "secrets" not in secrets_data:
            secrets_data["secrets"] = {}

        secrets_data["secrets"][key] = value
        self.save_secrets(secrets_data)

    def get_all_secrets(self) -> Dict[str, str]:
        """Get all secrets"""
        secrets_data = self.load_secrets()
        return secrets_data.get("secrets", {})
