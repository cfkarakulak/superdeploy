# Addon System Core

This directory contains the core components of the SuperDeploy addon system.

## Components

### Addon (`addon.py`)

The `Addon` class represents a loaded addon with all its metadata, templates, and configuration.

**Key Methods:**
- `render_compose(context)` - Renders the Docker compose template with project-specific variables
- `get_env_vars(project_config)` - Generates environment variables with substitutions
- `get_github_secrets()` - Returns list of GitHub secrets needed
- `get_dependencies()` - Returns list of required addons
- `get_conflicts()` - Returns list of conflicting addons
- `is_shared()` - Checks if addon is shared across projects

### AddonLoader (`addon_loader.py`)

The `AddonLoader` class handles dynamic addon discovery, loading, and dependency resolution.

**Key Methods:**
- `load_addon(addon_name)` - Loads a single addon by name (with caching)
- `load_addons_for_project(project_config)` - Loads all addons for a project including dependencies
- `discover_available_addons()` - Lists all available addons in the addons directory
- `clear_cache()` - Clears the addon cache

**Features:**
- Automatic dependency resolution
- Circular dependency detection
- Addon caching for performance
- Comprehensive error handling

### Exceptions

- `AddonNotFoundError` - Raised when an addon cannot be found
- `AddonValidationError` - Raised when addon metadata is invalid
- `CircularDependencyError` - Raised when circular dependencies are detected

## Usage Example

```python
from cli.core import AddonLoader

# Initialize loader
loader = AddonLoader(Path("superdeploy/addons"))

# Discover available addons
available = loader.discover_available_addons()
print(f"Available addons: {available}")

# Load addons for a project
project_config = {
    'project': 'myproject',
    'core_services': {
        'postgres': {},
        'redis': {}
    },
    'network': {
        'subnet': '172.20.0.0/24'
    }
}

addons = loader.load_addons_for_project(project_config)

# Use loaded addons
for name, addon in addons.items():
    print(f"Loaded: {name} v{addon.get_version()}")
    env_vars = addon.get_env_vars(project_config)
    compose = addon.render_compose({
        'project_name': project_config['project'],
        'addon_name': name,
        **addon.metadata
    })
```

## Addon Structure

Each addon must have the following files:

```
addon-name/
├── addon.yml           # Metadata and configuration
├── compose.yml.j2      # Docker compose template
├── env.yml             # Environment variables
└── ansible.yml         # Ansible deployment tasks
```

See `superdeploy/addons/README.md` for detailed addon creation guide.
