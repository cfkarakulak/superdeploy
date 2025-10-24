"""
Configuration generators for shared monitoring addon.
Generates Prometheus scrape configs and Grafana datasources for all projects.
"""

from typing import List, Dict, Any
from pathlib import Path
import yaml


class PrometheusConfigGenerator:
    """Generates Prometheus scrape configurations for all projects"""
    
    def __init__(self, scrape_interval: str = "15s", evaluation_interval: str = "15s"):
        self.scrape_interval = scrape_interval
        self.evaluation_interval = evaluation_interval
    
    def generate_config(self, projects: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate Prometheus configuration for all projects.
        
        Args:
            projects: List of project configurations with structure:
                {
                    'name': 'project-name',
                    'host': '10.0.1.2',
                    'environment': 'production',
                    'vm': 'core',
                    'tags': ['api', 'production'],
                    'targets': ['10.0.1.2:8000', '10.0.1.2:8001'],
                    'node_exporter_enabled': True,
                    'docker_metrics_enabled': True
                }
        
        Returns:
            Prometheus configuration dictionary
        """
        config = {
            'global': {
                'scrape_interval': self.scrape_interval,
                'evaluation_interval': self.evaluation_interval,
                'scrape_timeout': '10s',
                'external_labels': {
                    'monitor': 'superdeploy-monitor',
                    'environment': 'production'
                }
            },
            'scrape_configs': []
        }
        
        # Add Prometheus self-monitoring
        config['scrape_configs'].append({
            'job_name': 'prometheus',
            'static_configs': [{
                'targets': ['localhost:9090'],
                'labels': {
                    'service': 'prometheus',
                    'component': 'monitoring'
                }
            }]
        })
        
        # Add Grafana monitoring
        config['scrape_configs'].append({
            'job_name': 'grafana',
            'static_configs': [{
                'targets': ['grafana:3000'],
                'labels': {
                    'service': 'grafana',
                    'component': 'monitoring'
                }
            }]
        })
        
        # Add project-specific scrape configs
        for project in projects:
            self._add_project_scrape_configs(config, project)
        
        # Add Docker service discovery
        config['scrape_configs'].append(self._get_docker_sd_config())
        
        return config
    
    def _add_project_scrape_configs(self, config: Dict[str, Any], project: Dict[str, Any]):
        """Add scrape configurations for a single project"""
        project_name = project['name']
        
        # Main project services
        if project.get('targets'):
            labels = {
                'project': project_name,
                'environment': project.get('environment', 'production'),
                'vm': project.get('vm', 'core')
            }
            
            # Add tags as labels
            if project.get('tags'):
                for idx, tag in enumerate(project['tags'], 1):
                    labels[f'tag_{idx}'] = tag
            
            config['scrape_configs'].append({
                'job_name': f'{project_name}-services',
                'static_configs': [{
                    'targets': project['targets'],
                    'labels': labels
                }],
                'relabel_configs': [
                    {
                        'source_labels': ['__address__'],
                        'target_label': 'instance',
                        'replacement': f'{project_name}-${{1}}'
                    }
                ]
            })
        
        # Node exporter (system metrics)
        if project.get('node_exporter_enabled', True):
            config['scrape_configs'].append({
                'job_name': f'{project_name}-node',
                'static_configs': [{
                    'targets': [f"{project['host']}:9100"],
                    'labels': {
                        'project': project_name,
                        'environment': project.get('environment', 'production'),
                        'vm': project.get('vm', 'core'),
                        'service': 'node-exporter'
                    }
                }]
            })
        
        # Docker metrics
        if project.get('docker_metrics_enabled', True):
            config['scrape_configs'].append({
                'job_name': f'{project_name}-docker',
                'static_configs': [{
                    'targets': [f"{project['host']}:9323"],
                    'labels': {
                        'project': project_name,
                        'environment': project.get('environment', 'production'),
                        'vm': project.get('vm', 'core'),
                        'service': 'docker'
                    }
                }]
            })
    
    def _get_docker_sd_config(self) -> Dict[str, Any]:
        """Get Docker service discovery configuration"""
        return {
            'job_name': 'docker-services',
            'docker_sd_configs': [{
                'host': 'unix:///var/run/docker.sock'
            }],
            'relabel_configs': [
                # Only scrape containers with prometheus.scrape=true label
                {
                    'source_labels': ['__meta_docker_container_label_prometheus_scrape'],
                    'action': 'keep',
                    'regex': 'true'
                },
                # Use custom port if specified
                {
                    'source_labels': ['__meta_docker_container_label_prometheus_port'],
                    'action': 'replace',
                    'target_label': '__address__',
                    'regex': '(.+)',
                    'replacement': '${1}'
                },
                # Use custom path if specified
                {
                    'source_labels': ['__meta_docker_container_label_prometheus_path'],
                    'action': 'replace',
                    'target_label': '__metrics_path__',
                    'regex': '(.+)',
                    'replacement': '${1}'
                },
                # Add container name as instance
                {
                    'source_labels': ['__meta_docker_container_name'],
                    'action': 'replace',
                    'target_label': 'instance',
                    'regex': '/(.+)',
                    'replacement': '${1}'
                },
                # Add project label from container label
                {
                    'source_labels': ['__meta_docker_container_label_superdeploy_project'],
                    'action': 'replace',
                    'target_label': 'project'
                },
                # Add service label from container label
                {
                    'source_labels': ['__meta_docker_container_label_superdeploy_service'],
                    'action': 'replace',
                    'target_label': 'service'
                }
            ]
        }
    
    def save_config(self, config: Dict[str, Any], output_path: Path):
        """Save Prometheus configuration to file"""
        with open(output_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)


class GrafanaDatasourceGenerator:
    """Generates Grafana datasource provisioning for all projects"""
    
    def generate_datasources(self, projects: List[Dict[str, Any]], 
                            loki_enabled: bool = False) -> Dict[str, Any]:
        """
        Generate Grafana datasource configuration for all projects.
        
        Args:
            projects: List of project configurations
            loki_enabled: Whether to include Loki datasource
        
        Returns:
            Grafana datasource provisioning configuration
        """
        config = {
            'apiVersion': 1,
            'datasources': []
        }
        
        # Add main Prometheus datasource
        config['datasources'].append({
            'name': 'Prometheus',
            'type': 'prometheus',
            'access': 'proxy',
            'url': 'http://prometheus:9090',
            'isDefault': True,
            'editable': False,
            'jsonData': {
                'timeInterval': '15s',
                'queryTimeout': '60s',
                'httpMethod': 'POST'
            },
            'uid': 'prometheus-main'
        })
        
        # Add project-specific datasources
        for project in projects:
            config['datasources'].append(self._create_project_datasource(project))
        
        # Add Loki if enabled
        if loki_enabled:
            config['datasources'].append({
                'name': 'Loki',
                'type': 'loki',
                'access': 'proxy',
                'url': 'http://loki:3100',
                'isDefault': False,
                'editable': False,
                'jsonData': {
                    'maxLines': 1000
                },
                'uid': 'loki-main'
            })
        
        return config
    
    def _create_project_datasource(self, project: Dict[str, Any]) -> Dict[str, Any]:
        """Create a project-specific datasource configuration"""
        project_name = project['name']
        
        datasource = {
            'name': f"{project_name.title()} - Prometheus",
            'type': 'prometheus',
            'access': 'proxy',
            'url': 'http://prometheus:9090',
            'isDefault': False,
            'editable': False,
            'jsonData': {
                'timeInterval': '15s',
                'queryTimeout': '60s',
                'httpMethod': 'POST',
                'customQueryParameters': f'project={project_name}'
            },
            'uid': f'prometheus-{project_name}'
        }
        
        # Add custom labels for filtering
        custom_labels = {
            'project': project_name,
            'environment': project.get('environment', 'production')
        }
        
        if project.get('tags'):
            for idx, tag in enumerate(project['tags'], 1):
                custom_labels[f'tag_{idx}'] = tag
        
        datasource['jsonData']['customLabels'] = custom_labels
        
        return datasource
    
    def save_datasources(self, config: Dict[str, Any], output_path: Path):
        """Save Grafana datasource configuration to file"""
        with open(output_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)


class GrafanaDashboardGenerator:
    """Generates Grafana dashboard provisioning for all projects"""
    
    def generate_dashboard_config(self, projects: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate Grafana dashboard provisioning configuration.
        
        Args:
            projects: List of project configurations
        
        Returns:
            Grafana dashboard provisioning configuration
        """
        config = {
            'apiVersion': 1,
            'providers': []
        }
        
        # Add default dashboards provider
        config['providers'].append({
            'name': 'SuperDeploy Dashboards',
            'orgId': 1,
            'folder': 'SuperDeploy',
            'type': 'file',
            'disableDeletion': False,
            'updateIntervalSeconds': 30,
            'allowUiUpdates': True,
            'options': {
                'path': '/etc/grafana/provisioning/dashboards/json',
                'foldersFromFilesStructure': True
            }
        })
        
        # Add project-specific dashboard providers
        for project in projects:
            config['providers'].append({
                'name': f"{project['name'].title()} Dashboards",
                'orgId': 1,
                'folder': project['name'].title(),
                'type': 'file',
                'disableDeletion': False,
                'updateIntervalSeconds': 30,
                'allowUiUpdates': True,
                'options': {
                    'path': f"/etc/grafana/provisioning/dashboards/projects/{project['name']}",
                    'foldersFromFilesStructure': False
                }
            })
        
        return config
    
    def save_dashboard_config(self, config: Dict[str, Any], output_path: Path):
        """Save Grafana dashboard configuration to file"""
        with open(output_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)


# Example usage
if __name__ == '__main__':
    # Example projects
    projects = [
        {
            'name': 'cheapa',
            'host': '10.0.1.2',
            'environment': 'production',
            'vm': 'core',
            'tags': ['api', 'production'],
            'targets': ['10.0.1.2:8000', '10.0.1.2:8010'],
            'node_exporter_enabled': True,
            'docker_metrics_enabled': True
        },
        {
            'name': 'testproject',
            'host': '10.0.2.2',
            'environment': 'staging',
            'vm': 'core',
            'tags': ['test', 'staging'],
            'targets': ['10.0.2.2:8000'],
            'node_exporter_enabled': True,
            'docker_metrics_enabled': False
        }
    ]
    
    # Generate Prometheus config
    prom_gen = PrometheusConfigGenerator()
    prom_config = prom_gen.generate_config(projects)
    print("Prometheus Config:")
    print(yaml.dump(prom_config, default_flow_style=False))
    
    # Generate Grafana datasources
    grafana_ds_gen = GrafanaDatasourceGenerator()
    datasources = grafana_ds_gen.generate_datasources(projects)
    print("\nGrafana Datasources:")
    print(yaml.dump(datasources, default_flow_style=False))
    
    # Generate Grafana dashboards
    grafana_dash_gen = GrafanaDashboardGenerator()
    dashboards = grafana_dash_gen.generate_dashboard_config(projects)
    print("\nGrafana Dashboards:")
    print(yaml.dump(dashboards, default_flow_style=False))
