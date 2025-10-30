"""Monitoring utilities for updating Prometheus configuration"""

import subprocess
import tempfile
import yaml
from pathlib import Path
from typing import List


def update_orchestrator_monitoring(
    orchestrator_ip: str,
    project_name: str,
    project_targets: List[str],
    ssh_key_path: str = "~/.ssh/superdeploy_deploy",
    ssh_user: str = "superdeploy",
    vm_services_map: dict = None
) -> bool:
    """
    Update Prometheus configuration on orchestrator with new project targets
    
    Args:
        orchestrator_ip: IP address of orchestrator VM
        project_name: Name of the project
        project_targets: List of target endpoints (e.g., ["34.66.219.53:2019"])
        ssh_key_path: Path to SSH private key
        ssh_user: SSH username
        vm_services_map: Dict mapping VM IPs to service names (e.g., {"34.66.219.53:2019": {"service": "api", "vm": "api"}})
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Expand SSH key path
        ssh_key = Path(ssh_key_path).expanduser()
        
        # Path to Prometheus config on orchestrator
        prometheus_config_path = "/opt/superdeploy/projects/orchestrator/addons/monitoring/prometheus/prometheus.yml"
        
        # 1. Download current Prometheus config
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.yml', delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        # Download config
        download_cmd = [
            "scp",
            "-i", str(ssh_key),
            "-o", "StrictHostKeyChecking=no",
            f"{ssh_user}@{orchestrator_ip}:{prometheus_config_path}",
            tmp_path
        ]
        
        result = subprocess.run(download_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Failed to download Prometheus config: {result.stderr}")
            return False
        
        # 2. Parse YAML
        with open(tmp_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # 3. Update or add project scrape configs (one job per service)
        scrape_configs = config.get('scrape_configs', [])
        
        # Remove old project jobs
        scrape_configs = [job for job in scrape_configs if not job.get('job_name', '').startswith(f'{project_name}-')]
        
        # Create separate job for each target/service
        if vm_services_map:
            # Create one job per service
            for target in project_targets:
                service_info = vm_services_map.get(target, {})
                service_name = service_info.get('service', 'unknown')
                vm_name = service_info.get('vm', 'unknown')
                
                job_config = {
                    'job_name': f'{project_name}-{service_name}',
                    'static_configs': [{
                        'targets': [target],
                        'labels': {
                            'project': project_name,
                            'service': service_name,
                            'vm': vm_name,
                            'environment': 'production'
                        }
                    }]
                }
                scrape_configs.append(job_config)
        else:
            # Fallback: single job for all targets
            job_config = {
                'job_name': f'{project_name}-services',
                'static_configs': [{
                    'targets': project_targets,
                    'labels': {
                        'project': project_name,
                        'environment': 'production'
                    }
                }]
            }
            scrape_configs.append(job_config)
        
        config['scrape_configs'] = scrape_configs
        
        # 4. Write updated config
        with open(tmp_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        # 5. Upload updated config
        upload_cmd = [
            "scp",
            "-i", str(ssh_key),
            "-o", "StrictHostKeyChecking=no",
            tmp_path,
            f"{ssh_user}@{orchestrator_ip}:{prometheus_config_path}"
        ]
        
        result = subprocess.run(upload_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Failed to upload Prometheus config: {result.stderr}")
            Path(tmp_path).unlink(missing_ok=True)
            return False
        
        # 5.5. Copy config to Prometheus container
        copy_cmd = [
            "ssh",
            "-i", str(ssh_key),
            "-o", "StrictHostKeyChecking=no",
            f"{ssh_user}@{orchestrator_ip}",
            f"docker cp {prometheus_config_path} superdeploy-prometheus:/etc/prometheus/prometheus.yml"
        ]
        
        result = subprocess.run(copy_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Failed to copy config to container: {result.stderr}")
            # Non-critical, continue
        
        # 6. Reload Prometheus
        reload_cmd = [
            "ssh",
            "-i", str(ssh_key),
            "-o", "StrictHostKeyChecking=no",
            f"{ssh_user}@{orchestrator_ip}",
            "docker exec superdeploy-prometheus kill -HUP 1"
        ]
        
        result = subprocess.run(reload_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Failed to reload Prometheus: {result.stderr}")
            Path(tmp_path).unlink(missing_ok=True)
            return False
        
        # Cleanup
        Path(tmp_path).unlink(missing_ok=True)
        
        return True
        
    except Exception as e:
        print(f"Error updating monitoring: {e}")
        return False


def sync_all_projects_to_monitoring(
    orchestrator_ip: str,
    projects_dir: Path,
    ssh_key_path: str = "~/.ssh/superdeploy_deploy",
    ssh_user: str = "superdeploy"
) -> bool:
    """
    Sync all projects to monitoring (useful for manual sync)
    
    Args:
        orchestrator_ip: IP address of orchestrator VM
        projects_dir: Path to projects directory
        ssh_key_path: Path to SSH private key
        ssh_user: SSH username
        
    Returns:
        True if successful, False otherwise
    """
    try:
        from dotenv import dotenv_values
        
        all_targets = {}
        
        # Discover all projects
        for project_dir in projects_dir.iterdir():
            if not project_dir.is_dir():
                continue
            
            env_file = project_dir / ".env"
            if not env_file.exists():
                continue
            
            project_name = project_dir.name
            env_vars = dotenv_values(env_file)
            
            # Collect targets
            targets = []
            for key, value in env_vars.items():
                if key.endswith("_EXTERNAL_IP") and value:
                    targets.append(f"{value}:2019")
            
            if targets:
                all_targets[project_name] = targets
        
        # Update monitoring for each project
        success = True
        for project_name, targets in all_targets.items():
            result = update_orchestrator_monitoring(
                orchestrator_ip=orchestrator_ip,
                project_name=project_name,
                project_targets=targets,
                ssh_key_path=ssh_key_path,
                ssh_user=ssh_user
            )
            if not result:
                success = False
        
        return success
        
    except Exception as e:
        print(f"Error syncing projects to monitoring: {e}")
        return False
