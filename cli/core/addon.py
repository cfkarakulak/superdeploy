"""Addon data model and rendering logic"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
import yaml
from jinja2 import Template


@dataclass
class Addon:
    """Represents a loaded addon with metadata, templates, and rendering methods"""
    
    name: str
    metadata: dict
    compose_template: Template
    env_schema: dict
    ansible_tasks: dict
    addon_path: Path
    
    def render_compose(self, context: dict) -> dict:
        """
        Render compose template with context variables.
        
        Args:
            context: Dictionary containing template variables like project_name, addon_name, etc.
            
        Returns:
            Dictionary containing the rendered Docker compose service configuration
        """
        rendered = self.compose_template.render(**context)
        return yaml.safe_load(rendered)
    
    def get_env_vars(self, project_config: dict) -> Dict[str, str]:
        """
        Get environment variables for this addon with project-specific substitutions.
        
        Args:
            project_config: Project configuration dictionary
            
        Returns:
            Dictionary of environment variable names to values
        """
        env_vars = {}
        project_name = project_config.get('project', '')
        
        for var_name, var_config in self.env_schema.get('variables', {}).items():
            value = var_config.get('value', '')
            
            # Substitute placeholders
            value = value.replace('${PROJECT}', project_name)
            
            # Handle CORE_INTERNAL_IP substitution
            if '${CORE_INTERNAL_IP}' in value:
                core_ip = self._get_core_ip(project_config)
                value = value.replace('${CORE_INTERNAL_IP}', core_ip)
            
            env_vars[var_name] = value
        
        return env_vars
    
    def get_github_secrets(self) -> List[str]:
        """
        Get list of GitHub secrets this addon needs.
        
        Returns:
            List of secret names
        """
        return self.env_schema.get('github_secrets', [])
    
    def get_dependencies(self) -> List[str]:
        """
        Get list of addon dependencies.
        
        Returns:
            List of addon names that this addon requires
        """
        return self.metadata.get('requires', [])
    
    def get_conflicts(self) -> List[str]:
        """
        Get list of conflicting addons.
        
        Returns:
            List of addon names that conflict with this addon
        """
        return self.metadata.get('conflicts', [])
    
    def is_shared(self) -> bool:
        """
        Check if this is a shared addon (single instance across all projects).
        
        Returns:
            True if addon is shared, False otherwise
        """
        return self.metadata.get('shared', False)
    
    def get_version(self) -> str:
        """
        Get addon version.
        
        Returns:
            Version string
        """
        return self.metadata.get('version', 'latest')
    
    def get_category(self) -> str:
        """
        Get addon category.
        
        Returns:
            Category string (database, cache, queue, proxy, monitoring, etc.)
        """
        return self.metadata.get('category', 'other')
    
    def get_description(self) -> str:
        """
        Get addon description.
        
        Returns:
            Description string
        """
        return self.metadata.get('description', '')
    
    def _get_core_ip(self, project_config: dict) -> str:
        """
        Extract core VM internal IP from project configuration.
        
        Args:
            project_config: Project configuration dictionary
            
        Returns:
            Core VM IP address or placeholder
        """
        # Extract from network subnet if available
        subnet = project_config.get('network', {}).get('subnet', '')
        if subnet:
            # Parse subnet and return first usable IP (e.g., 172.20.0.0/24 -> 172.20.0.2)
            base = subnet.split('/')[0]
            parts = base.split('.')
            parts[-1] = '2'  # Use .2 as core VM IP
            return '.'.join(parts)
        
        return '${CORE_INTERNAL_IP}'  # Fallback placeholder
