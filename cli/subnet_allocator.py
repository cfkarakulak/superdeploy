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
    
    # Base network: 10.0.0.0/8
    # Each project gets a /16 subnet: 10.X.0.0/16
    # This allows 256 projects (10.0.0.0/16 to 10.255.0.0/16)
    BASE_NETWORK = "10"
    SUBNET_MASK = "16"
    
    # Reserved ranges:
    # 10.0.0.0/16 - Reserved for orchestrator
    # 10.1.0.0/16 - First project
    # 10.2.0.0/16 - Second project
    # etc.
    
    ORCHESTRATOR_SUBNET = "10.0.0.0/16"
    FIRST_PROJECT_INDEX = 1
    
    def __init__(self):
        self.project_root = get_project_root()
        self.allocation_file = self.project_root / "shared" / "terraform" / "subnet_allocations.json"
        self.allocations = self._load_allocations()
    
    def _load_allocations(self) -> Dict[str, str]:
        """Load existing subnet allocations from file"""
        if self.allocation_file.exists():
            with open(self.allocation_file, 'r') as f:
                return json.load(f)
        return {}
    
    def _save_allocations(self):
        """Save subnet allocations to file"""
        self.allocation_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.allocation_file, 'w') as f:
            json.dump(self.allocations, f, indent=2)
    
    def get_subnet(self, project_name: str) -> str:
        """
        Get or allocate a subnet for a project
        
        Args:
            project_name: Name of the project
            
        Returns:
            Subnet CIDR (e.g., "10.1.0.0/16")
        """
        # Check if already allocated
        if project_name in self.allocations:
            return self.allocations[project_name]
        
        # Find next available index
        used_indices = set()
        for subnet in self.allocations.values():
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
            raise ValueError("No more subnets available (max 255 projects)")
        
        # Allocate new subnet
        subnet = f"{self.BASE_NETWORK}.{next_index}.0.0/{self.SUBNET_MASK}"
        self.allocations[project_name] = subnet
        self._save_allocations()
        
        return subnet
    
    def release_subnet(self, project_name: str) -> bool:
        """
        Release a subnet allocation
        
        Args:
            project_name: Name of the project
            
        Returns:
            True if subnet was released, False if not allocated
        """
        if project_name in self.allocations:
            del self.allocations[project_name]
            self._save_allocations()
            return True
        return False
    
    def list_allocations(self) -> Dict[str, str]:
        """
        List all subnet allocations
        
        Returns:
            Dictionary mapping project names to subnets
        """
        return dict(self.allocations)
    
    @classmethod
    def get_orchestrator_subnet(cls) -> str:
        """Get the reserved orchestrator subnet"""
        return cls.ORCHESTRATOR_SUBNET
