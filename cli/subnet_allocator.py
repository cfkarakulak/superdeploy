"""Subnet allocation for multi-project deployments

Ensures each project gets a unique subnet to avoid IP conflicts.
Uses a simple allocation scheme based on project index.
"""

import json
from pathlib import Path
from typing import Dict, Optional
from .utils import get_project_root


class SubnetAllocator:
    """Allocate unique subnets for each project"""
    
    # VPC Subnets: 10.0.0.0/8
    # Each project gets a /16 subnet: 10.X.0.0/16
    # This allows 256 projects (10.0.0.0/16 to 10.255.0.0/16)
    BASE_NETWORK = "10"
    SUBNET_MASK = "16"
    
    # Docker Subnets: 172.16.0.0/12 (Docker's default private range)
    # Each project gets a /24 subnet: 172.X.0.0/24
    # This allows 256 projects (172.16.0.0/24 to 172.31.255.0/24)
    DOCKER_BASE = "172"
    DOCKER_SUBNET_MASK = "24"
    
    # Reserved ranges:
    # VPC: 10.0.0.0/16 - Reserved for orchestrator
    # VPC: 10.1.0.0/16 - First project
    # Docker: 172.20.0.0/24 - Reserved for orchestrator
    # Docker: 172.30.0.0/24 - First project
    
    ORCHESTRATOR_SUBNET = "10.0.0.0/16"
    ORCHESTRATOR_DOCKER_SUBNET = "172.20.0.0/24"
    FIRST_PROJECT_INDEX = 1
    FIRST_DOCKER_INDEX = 30  # Start from 172.30.0.0/24
    
    def __init__(self):
        self.project_root = get_project_root()
        self.allocation_file = self.project_root / "shared" / "terraform" / "subnet_allocations.json"
        self.allocations = self._load_allocations()
        self.docker_allocations = self.allocations.get("docker_subnets", {})
    
    def _load_allocations(self) -> Dict:
        """Load existing subnet allocations from file"""
        if self.allocation_file.exists():
            with open(self.allocation_file, 'r') as f:
                data = json.load(f)
                # Migrate old format (flat dict) to new format
                if "docker_subnets" not in data and data:
                    return {"vpc_subnets": data, "docker_subnets": {}}
                return data
        return {"vpc_subnets": {}, "docker_subnets": {}}
    
    def _save_allocations(self):
        """Save subnet allocations to file"""
        self.allocation_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.allocation_file, 'w') as f:
            json.dump(self.allocations, f, indent=2)
    
    def get_subnet(self, project_name: str) -> str:
        """
        Get or allocate a VPC subnet for a project
        
        Args:
            project_name: Name of the project
            
        Returns:
            Subnet CIDR (e.g., "10.1.0.0/16")
        """
        vpc_subnets = self.allocations.get("vpc_subnets", {})
        
        # Check if already allocated
        if project_name in vpc_subnets:
            return vpc_subnets[project_name]
        
        # Find next available index
        used_indices = set()
        for subnet in vpc_subnets.values():
            # Parse subnet like "10.X.0.0/16"
            parts = subnet.split('.')
            if len(parts) >= 2:
                try:
                    index = int(parts[1])
                    used_indices.add(index)
                except ValueError:
                    pass
        
        # Find first available index starting from FIRST_PROJECT_INDEX
        next_index = self.FIRST_PROJECT_INDEX
        while next_index in used_indices:
            next_index += 1
        
        if next_index > 255:
            raise ValueError("No more VPC subnets available (max 255 projects)")
        
        # Allocate new subnet
        subnet = f"{self.BASE_NETWORK}.{next_index}.0.0/{self.SUBNET_MASK}"
        vpc_subnets[project_name] = subnet
        self.allocations["vpc_subnets"] = vpc_subnets
        self._save_allocations()
        
        return subnet
    
    def get_docker_subnet(self, project_name: str) -> str:
        """
        Get or allocate a Docker subnet for a project
        
        Args:
            project_name: Name of the project
            
        Returns:
            Docker subnet CIDR (e.g., "172.30.0.0/24")
        """
        docker_subnets = self.allocations.get("docker_subnets", {})
        
        # Check if already allocated
        if project_name in docker_subnets:
            return docker_subnets[project_name]
        
        # Find next available index
        used_indices = set()
        for subnet in docker_subnets.values():
            # Parse subnet like "172.X.0.0/24"
            parts = subnet.split('.')
            if len(parts) >= 2:
                try:
                    index = int(parts[1])
                    used_indices.add(index)
                except ValueError:
                    pass
        
        # Find first available index starting from FIRST_DOCKER_INDEX
        next_index = self.FIRST_DOCKER_INDEX
        while next_index in used_indices:
            next_index += 1
        
        if next_index > 31:  # Docker private range is 172.16-31
            raise ValueError("No more Docker subnets available (max 12 projects in 172.20-31 range)")
        
        # Allocate new subnet
        subnet = f"{self.DOCKER_BASE}.{next_index}.0.0/{self.DOCKER_SUBNET_MASK}"
        docker_subnets[project_name] = subnet
        self.allocations["docker_subnets"] = docker_subnets
        self._save_allocations()
        
        return subnet
    
    def release_subnet(self, project_name: str) -> bool:
        """
        Release VPC and Docker subnet allocations
        
        Args:
            project_name: Name of the project
            
        Returns:
            True if any subnet was released, False if not allocated
        """
        released = False
        
        vpc_subnets = self.allocations.get("vpc_subnets", {})
        if project_name in vpc_subnets:
            del vpc_subnets[project_name]
            self.allocations["vpc_subnets"] = vpc_subnets
            released = True
        
        docker_subnets = self.allocations.get("docker_subnets", {})
        if project_name in docker_subnets:
            del docker_subnets[project_name]
            self.allocations["docker_subnets"] = docker_subnets
            released = True
        
        if released:
            self._save_allocations()
        
        return released
    
    def list_allocations(self) -> Dict[str, str]:
        """
        List all subnet allocations
        
        Returns:
            Dictionary mapping project names to subnets
        """
        return dict(self.allocations)
    
    @classmethod
    def get_orchestrator_subnet(cls) -> str:
        """Get the reserved orchestrator VPC subnet"""
        return cls.ORCHESTRATOR_SUBNET
    
    @classmethod
    def get_orchestrator_docker_subnet(cls) -> str:
        """Get the reserved orchestrator Docker subnet"""
        return cls.ORCHESTRATOR_DOCKER_SUBNET
