"""
Ansible runner with custom callback plugin
"""

import subprocess
import os


class AnsibleRunner:
    """Run Ansible with clean tree view using custom callback"""

    def __init__(self, logger, title="Configuring", verbose=False):
        self.logger = logger
        self.title = title
        self.verbose = verbose

    def run(self, ansible_cmd, cwd):
        """Run Ansible command"""

        self.logger.log_command(ansible_cmd)

        # Create Ansible-specific log file (raw output, no prefixes)
        # This will contain full verbose Ansible output for debugging
        ansible_log_path = (
            self.logger.log_path.parent / f"{self.logger.log_path.stem}_ansible.log"
        )

        # PERFORMANCE: Use venv Python + collections for Mitogen
        import sys
        from pathlib import Path

        venv_python = sys.executable  # Current Python (from venv)
        venv_root = Path(sys.executable).parent.parent
        python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
        collections_path = (
            venv_root / "lib" / python_version / "site-packages" / "ansible_collections"
        )
        mitogen_strategy_path = (
            venv_root
            / "lib"
            / python_version
            / "site-packages"
            / "ansible_mitogen"
            / "plugins"
            / "strategy"
        )

        # Setup environment for VERBOSE logging to file
        env_verbose = os.environ.copy()
        env_verbose.update(
            {
                "PYTHONUNBUFFERED": "1",
                "ANSIBLE_STDOUT_CALLBACK": "default",  # RAW output for log file
                "ANSIBLE_DISPLAY_SKIPPED_HOSTS": "false",
                "ANSIBLE_LOG_PATH": str(ansible_log_path),
                "ANSIBLE_NOCOLOR": "true",  # No colors in log file
                # COLLECTIONS: Use venv collections (both singular and plural for compatibility)
                "ANSIBLE_COLLECTIONS_PATH": str(collections_path),
                "ANSIBLE_COLLECTIONS_PATHS": str(collections_path),
                # MITOGEN: Use venv Mitogen strategy plugins
                "ANSIBLE_STRATEGY_PLUGINS": str(mitogen_strategy_path),
            }
        )

        # Run Ansible in background for logging (captures to file)
        # This runs with default callback for full details
        import threading

        def run_ansible_logger():
            """Background thread to capture full Ansible output to log file"""
            subprocess.run(
                ansible_cmd,
                shell=True,
                cwd=str(cwd),
                env=env_verbose,
                stdout=subprocess.DEVNULL,  # We don't need this output
                stderr=subprocess.DEVNULL,
            )

        # Start background logging thread
        log_thread = threading.Thread(target=run_ansible_logger, daemon=True)
        log_thread.start()

        self.logger.log(f"Ansible detailed log: {ansible_log_path}", "INFO")

        # Setup environment for TERMINAL output
        env_terminal = os.environ.copy()
        env_terminal.update(
            {
                "PYTHONUNBUFFERED": "1",
                "ANSIBLE_STDOUT_CALLBACK": "tree_minimal"
                if not self.verbose
                else "default",
                "ANSIBLE_DISPLAY_SKIPPED_HOSTS": "false",
                # Verbose mode: keep colors for better readability
                "ANSIBLE_FORCE_COLOR": "true" if self.verbose else "false",
                # COLLECTIONS: Use venv collections (both singular and plural for compatibility)
                "ANSIBLE_COLLECTIONS_PATH": str(collections_path),
                "ANSIBLE_COLLECTIONS_PATHS": str(collections_path),
                # MITOGEN: Use venv Mitogen strategy plugins
                "ANSIBLE_STRATEGY_PLUGINS": str(mitogen_strategy_path),
            }
        )

        if self.verbose:
            # VERBOSE MODE: Let Ansible write directly to terminal (no capture)
            # This preserves colors, formatting, and native Ansible output
            result = subprocess.run(
                ansible_cmd,
                shell=True,
                cwd=str(cwd),
                env=env_terminal,
            )
            returncode = result.returncode
        else:
            # NON-VERBOSE MODE: Capture and display with tree_minimal
            process = subprocess.Popen(
                ansible_cmd,
                shell=True,
                cwd=str(cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env_terminal,
            )

            # Pass through output (to both main log and console)
            if process.stdout:
                for line in process.stdout:
                    line_stripped = line.rstrip()

                    # Log to main log file
                    try:
                        self.logger.log_output(line_stripped, "ansible")
                    except (BlockingIOError, OSError):
                        pass

                    # Print to console
                    print(line_stripped)

            returncode = process.wait()

        # Wait for background logger to finish
        log_thread.join(timeout=5)

        return returncode
