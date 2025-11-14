"""Deployment validation service."""

from pathlib import Path
from typing import List
import yaml

from cli.secret_manager import SecretManager
from cli.services.config_service import ConfigService


class DeploymentValidator:
    """Validates deployment prerequisites and secrets."""

    def __init__(
        self, project_root: Path, config_service: ConfigService, project_name: str
    ):
        self.project_root = project_root
        self.config_service = config_service
        self.project_name = project_name
        self.secret_mgr = SecretManager(project_root, project_name)

    def validate_secrets(self, logger) -> List[str]:
        """
        Validate project secrets before deployment.

        Returns:
            List of error messages (empty list if validation passes)
        """
        errors = []

        # Check if secrets file exists
        if not self.secret_mgr.secrets_file.exists():
            errors.append("secrets.yml not found")
            errors.append(f"Run: superdeploy {self.project_name}:init")
            return errors

        # Load secrets
        try:
            secrets_data = self.secret_mgr.load_secrets()
        except Exception as e:
            errors.append(f"Failed to load secrets.yml: {e}")
            return errors

        if not secrets_data:
            errors.append("Invalid secrets.yml structure (missing secrets)")
            return errors

        shared_secrets = secrets_data.shared.values

        # Validate required credentials
        errors.extend(self._validate_docker_credentials(shared_secrets))
        errors.extend(self._validate_github_token(shared_secrets))
        self._check_orchestrator_ip(shared_secrets, logger)
        errors.extend(self._validate_addon_secrets(shared_secrets, logger))

        return errors

    def _validate_docker_credentials(self, shared_secrets: dict) -> List[str]:
        """Validate Docker credentials."""
        errors = []

        docker_username = shared_secrets.get("DOCKER_USERNAME", "").strip()
        docker_token = shared_secrets.get("DOCKER_TOKEN", "").strip()

        if not docker_username:
            errors.append("DOCKER_USERNAME is missing or empty in secrets.yml")
        if not docker_token:
            errors.append("DOCKER_TOKEN is missing or empty in secrets.yml")

        return errors

    def _validate_github_token(self, shared_secrets: dict) -> List[str]:
        """Validate GitHub token."""
        errors = []

        github_token = shared_secrets.get("REPOSITORY_TOKEN", "").strip()
        if not github_token:
            errors.append("REPOSITORY_TOKEN is missing or empty in secrets.yml")

        return errors

    def _check_orchestrator_ip(self, shared_secrets: dict, logger) -> None:
        """Check and warn about orchestrator IP."""
        orchestrator_ip = shared_secrets.get("ORCHESTRATOR_IP", "").strip()
        if not orchestrator_ip:
            logger.log("")
            logger.log("[yellow]⚠[/yellow] ORCHESTRATOR_IP not set in secrets.yml")
            logger.log(
                "[dim]   Run 'superdeploy orchestrator:up' first to set it automatically[/dim]"
            )
            logger.log("")

    def _validate_addon_secrets(self, shared_secrets: dict, logger) -> List[str]:
        """Validate addon-specific secrets."""
        errors = []

        try:
            project_config = self.config_service.load_project_config(self.project_name)
            enabled_addons = project_config.raw_config.get("addons", {})

            if enabled_addons:
                addons_dir = self.project_root / "addons"

                for addon_name in enabled_addons.keys():
                    addon_yml_path = addons_dir / addon_name / "addon.yml"

                    if not addon_yml_path.exists():
                        continue

                    # Load addon metadata
                    try:
                        with open(addon_yml_path, "r") as f:
                            addon_meta = yaml.safe_load(f)

                        # Check required secret env vars
                        env_vars = addon_meta.get("env_vars", [])

                        for env_var in env_vars:
                            var_name = env_var.get("name")
                            is_secret = env_var.get("secret", False)
                            is_required = env_var.get("required", False)

                            if is_secret and is_required:
                                var_value = shared_secrets.get(var_name, "").strip()

                                if not var_value:
                                    errors.append(
                                        f"{var_name} is missing or empty (required by {addon_name} addon)"
                                    )

                    except Exception as e:
                        logger.log(
                            f"[dim]Warning: Could not parse addon.yml for {addon_name}: {e}[/dim]"
                        )

        except Exception as e:
            logger.log(
                f"[dim]Warning: Could not load project config for addon validation: {e}[/dim]"
            )

        return errors
