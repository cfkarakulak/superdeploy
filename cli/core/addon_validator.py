"""Addon validation system for SuperDeploy"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml
import re


@dataclass
class ValidationCheck:
    """Represents a single validation check result"""
    name: str
    passed: bool
    message: str
    severity: str = "error"  # error, warning, info
    fixable: bool = False
    fix_suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    """Represents the complete validation result for an addon"""
    addon_name: str
    addon_path: Path
    checks: List[ValidationCheck] = field(default_factory=list)
    
    @property
    def passed(self) -> bool:
        """Check if all critical validations passed"""
        return all(check.passed or check.severity != "error" for check in self.checks)
    
    @property
    def error_count(self) -> int:
        """Count of failed error-level checks"""
        return sum(1 for check in self.checks if not check.passed and check.severity == "error")
    
    @property
    def warning_count(self) -> int:
        """Count of failed warning-level checks"""
        return sum(1 for check in self.checks if not check.passed and check.severity == "warning")
    
    def add_check(self, check: ValidationCheck) -> None:
        """Add a validation check to the result"""
        self.checks.append(check)


class AddonValidator:
    """Validates addon structure and configuration"""
    
    REQUIRED_FILES = ["addon.yml"]
    COMPOSE_FILE_NAMES = ["docker-compose.yml.j2", "compose.yml.j2"]
    REQUIRED_METADATA_FIELDS = ["name", "description", "version", "category"]
    VALID_CATEGORIES = ["database", "cache", "queue", "proxy", "infrastructure", "monitoring", "storage"]
    
    # Anti-patterns to detect in Ansible tasks
    ANSIBLE_ANTI_PATTERNS = [
        (r"docker\s+compose\s+up", "Use docker compose in detached mode: docker compose up -d"),
        (r"sleep\s+\d+", "Avoid hardcoded sleep, use wait_for or proper health checks"),
        (r"curl.*\|\s*bash", "Avoid piping curl to bash, download and verify scripts first"),
        (r"rm\s+-rf\s+/", "Dangerous recursive delete detected"),
    ]
    
    def __init__(self, addons_path: Path):
        """
        Initialize validator
        
        Args:
            addons_path: Path to addons directory
        """
        self.addons_path = Path(addons_path)
    
    def validate_addon(self, addon_name: str) -> ValidationResult:
        """
        Validate a single addon
        
        Args:
            addon_name: Name of the addon to validate
            
        Returns:
            ValidationResult with all checks
        """
        addon_path = self.addons_path / addon_name
        result = ValidationResult(addon_name=addon_name, addon_path=addon_path)
        
        # Check if addon directory exists
        if not addon_path.exists():
            result.add_check(ValidationCheck(
                name="addon_exists",
                passed=False,
                message=f"Addon directory not found: {addon_path}",
                severity="error"
            ))
            return result
        
        result.add_check(ValidationCheck(
            name="addon_exists",
            passed=True,
            message="Addon directory exists",
            severity="info"
        ))
        
        # Validate required files
        self._validate_required_files(addon_path, result)
        
        # Validate addon.yml metadata
        addon_yml_path = addon_path / "addon.yml"
        if addon_yml_path.exists():
            self._validate_metadata(addon_yml_path, result)
            
            # Validate compose template (check both possible names)
            compose_path = None
            for compose_name in self.COMPOSE_FILE_NAMES:
                potential_path = addon_path / compose_name
                if potential_path.exists():
                    compose_path = potential_path
                    break
            
            if compose_path:
                self._validate_compose_template(compose_path, result)
            
            # Validate healthcheck configuration
            self._validate_healthcheck(addon_yml_path, result)
        
        # Validate Ansible tasks if they exist
        ansible_path = addon_path / "ansible.yml"
        if ansible_path.exists():
            self._validate_ansible_tasks(ansible_path, result)
        
        return result
    
    def validate_all_addons(self) -> List[ValidationResult]:
        """
        Validate all addons in the addons directory
        
        Returns:
            List of ValidationResult for each addon
        """
        results = []
        
        if not self.addons_path.exists():
            return results
        
        # Directories to skip (apps are deployed via GitHub push, not part of addon system)
        skip_dirs = {'apps', '.git', '__pycache__'}
        
        for addon_dir in self.addons_path.iterdir():
            if addon_dir.is_dir() and not addon_dir.name.startswith('.') and addon_dir.name not in skip_dirs:
                result = self.validate_addon(addon_dir.name)
                results.append(result)
        
        return results
    
    def _validate_required_files(self, addon_path: Path, result: ValidationResult) -> None:
        """Validate that required files exist"""
        for required_file in self.REQUIRED_FILES:
            file_path = addon_path / required_file
            passed = file_path.exists()
            
            result.add_check(ValidationCheck(
                name=f"required_file_{required_file}",
                passed=passed,
                message=f"Required file {'exists' if passed else 'missing'}: {required_file}",
                severity="error" if not passed else "info",
                fixable=not passed,
                fix_suggestion=f"Create {required_file} in {addon_path}" if not passed else None
            ))
        
        # Check for compose file (accept either name)
        compose_exists = any((addon_path / name).exists() for name in self.COMPOSE_FILE_NAMES)
        compose_file = next((name for name in self.COMPOSE_FILE_NAMES if (addon_path / name).exists()), None)
        
        result.add_check(ValidationCheck(
            name="required_file_compose",
            passed=compose_exists,
            message=f"Compose file {'exists' if compose_exists else 'missing'}: {compose_file or 'docker-compose.yml.j2 or compose.yml.j2'}",
            severity="error" if not compose_exists else "info",
            fixable=not compose_exists,
            fix_suggestion=f"Create docker-compose.yml.j2 or compose.yml.j2 in {addon_path}" if not compose_exists else None
        ))
    
    def _validate_metadata(self, addon_yml_path: Path, result: ValidationResult) -> None:
        """Validate addon.yml metadata fields"""
        try:
            with open(addon_yml_path) as f:
                metadata = yaml.safe_load(f)
            
            if not metadata:
                result.add_check(ValidationCheck(
                    name="metadata_not_empty",
                    passed=False,
                    message="addon.yml is empty",
                    severity="error"
                ))
                return
            
            # Check required fields
            for field in self.REQUIRED_METADATA_FIELDS:
                passed = field in metadata and metadata[field]
                
                result.add_check(ValidationCheck(
                    name=f"metadata_field_{field}",
                    passed=passed,
                    message=f"Required field {'present' if passed else 'missing'}: {field}",
                    severity="error" if not passed else "info",
                    fixable=not passed,
                    fix_suggestion=f"Add '{field}' field to addon.yml" if not passed else None
                ))
            
            # Validate category
            if "category" in metadata:
                category = metadata["category"]
                passed = category in self.VALID_CATEGORIES
                
                result.add_check(ValidationCheck(
                    name="metadata_valid_category",
                    passed=passed,
                    message=f"Category '{category}' is {'valid' if passed else 'invalid'}",
                    severity="warning" if not passed else "info",
                    fixable=not passed,
                    fix_suggestion=f"Use one of: {', '.join(self.VALID_CATEGORIES)}" if not passed else None
                ))
            
            # Check env_vars structure
            if "env_vars" in metadata:
                self._validate_env_vars(metadata["env_vars"], result)
            
        except yaml.YAMLError as e:
            result.add_check(ValidationCheck(
                name="metadata_valid_yaml",
                passed=False,
                message=f"Invalid YAML in addon.yml: {e}",
                severity="error"
            ))
        except Exception as e:
            result.add_check(ValidationCheck(
                name="metadata_readable",
                passed=False,
                message=f"Error reading addon.yml: {e}",
                severity="error"
            ))
    
    def _validate_env_vars(self, env_vars: List[Dict], result: ValidationResult) -> None:
        """Validate environment variables structure"""
        if not isinstance(env_vars, list):
            result.add_check(ValidationCheck(
                name="env_vars_is_list",
                passed=False,
                message="env_vars must be a list",
                severity="error"
            ))
            return
        
        for i, env_var in enumerate(env_vars):
            if not isinstance(env_var, dict):
                result.add_check(ValidationCheck(
                    name=f"env_var_{i}_is_dict",
                    passed=False,
                    message=f"env_vars[{i}] must be a dictionary",
                    severity="error"
                ))
                continue
            
            # Check required fields for env_var
            required_env_fields = ["name", "description", "required"]
            for field in required_env_fields:
                if field not in env_var:
                    result.add_check(ValidationCheck(
                        name=f"env_var_{i}_has_{field}",
                        passed=False,
                        message=f"env_vars[{i}] missing required field: {field}",
                        severity="warning",
                        fixable=True,
                        fix_suggestion=f"Add '{field}' to env_var definition"
                    ))
    
    def _validate_compose_template(self, compose_path: Path, result: ValidationResult) -> None:
        """Validate docker-compose.yml.j2 template"""
        try:
            with open(compose_path) as f:
                content = f.read()
            
            # Check for basic Jinja2 syntax
            if "{{" not in content and "{%" not in content:
                result.add_check(ValidationCheck(
                    name="compose_has_jinja",
                    passed=False,
                    message="docker-compose.yml.j2 appears to have no Jinja2 variables",
                    severity="warning"
                ))
            
            # Check for common issues
            if "version:" in content:
                result.add_check(ValidationCheck(
                    name="compose_no_version",
                    passed=False,
                    message="docker-compose.yml should not include 'version' field (deprecated in Compose v2)",
                    severity="warning",
                    fixable=True,
                    fix_suggestion="Remove 'version:' line from docker-compose.yml.j2"
                ))
            
            # Check for healthcheck definition
            has_healthcheck = "healthcheck:" in content
            result.add_check(ValidationCheck(
                name="compose_has_healthcheck",
                passed=has_healthcheck,
                message=f"Healthcheck {'defined' if has_healthcheck else 'not defined'} in compose file",
                severity="info" if has_healthcheck else "warning",
                fixable=not has_healthcheck,
                fix_suggestion="Add healthcheck section to service definition" if not has_healthcheck else None
            ))
            
        except Exception as e:
            result.add_check(ValidationCheck(
                name="compose_readable",
                passed=False,
                message=f"Error reading docker-compose.yml.j2: {e}",
                severity="error"
            ))
    
    def _validate_healthcheck(self, addon_yml_path: Path, result: ValidationResult) -> None:
        """Validate healthcheck configuration in addon.yml"""
        try:
            with open(addon_yml_path) as f:
                metadata = yaml.safe_load(f)
            
            if not metadata or "healthcheck" not in metadata:
                result.add_check(ValidationCheck(
                    name="healthcheck_defined",
                    passed=False,
                    message="No healthcheck defined in addon.yml",
                    severity="warning",
                    fixable=True,
                    fix_suggestion="Add healthcheck section with command or url"
                ))
                return
            
            healthcheck = metadata["healthcheck"]
            
            # Check if either command or url is defined
            has_method = "command" in healthcheck or "url" in healthcheck
            result.add_check(ValidationCheck(
                name="healthcheck_has_method",
                passed=has_method,
                message=f"Healthcheck method {'defined' if has_method else 'missing'} (command or url)",
                severity="error" if not has_method else "info",
                fixable=not has_method,
                fix_suggestion="Add 'command' or 'url' to healthcheck section" if not has_method else None
            ))
            
            # Check for recommended fields
            recommended_fields = ["interval", "timeout", "retries", "start_period"]
            for field in recommended_fields:
                if field not in healthcheck:
                    result.add_check(ValidationCheck(
                        name=f"healthcheck_has_{field}",
                        passed=False,
                        message=f"Healthcheck missing recommended field: {field}",
                        severity="info",
                        fixable=True,
                        fix_suggestion=f"Add '{field}' to healthcheck section"
                    ))
            
        except Exception as e:
            result.add_check(ValidationCheck(
                name="healthcheck_validation_error",
                passed=False,
                message=f"Error validating healthcheck: {e}",
                severity="warning"
            ))
    
    def _validate_ansible_tasks(self, ansible_path: Path, result: ValidationResult) -> None:
        """Validate Ansible tasks for anti-patterns"""
        try:
            with open(ansible_path) as f:
                content = f.read()
            
            # Check for anti-patterns
            for pattern, suggestion in self.ANSIBLE_ANTI_PATTERNS:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    result.add_check(ValidationCheck(
                        name=f"ansible_antipattern_{pattern[:20]}",
                        passed=False,
                        message=f"Anti-pattern detected: {pattern}",
                        severity="warning",
                        fixable=True,
                        fix_suggestion=suggestion
                    ))
            
            # Check for proper task structure
            try:
                tasks = yaml.safe_load(content)
                if tasks and isinstance(tasks, list):
                    for i, task in enumerate(tasks):
                        if isinstance(task, dict) and "name" not in task:
                            result.add_check(ValidationCheck(
                                name=f"ansible_task_{i}_has_name",
                                passed=False,
                                message=f"Task {i} missing 'name' field",
                                severity="warning",
                                fixable=True,
                                fix_suggestion="Add descriptive 'name' to each task"
                            ))
            except yaml.YAMLError:
                pass  # YAML validation will be caught separately
            
        except Exception as e:
            result.add_check(ValidationCheck(
                name="ansible_readable",
                passed=False,
                message=f"Error reading ansible.yml: {e}",
                severity="warning"
            ))
