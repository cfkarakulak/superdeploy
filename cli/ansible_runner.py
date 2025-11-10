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

        # SEQUENTIAL APPROACH: Run verbose process FIRST, then terminal
        # This prevents race conditions and VM conflicts
        
        if not self.verbose:
            # Show progress message for non-verbose mode
            print("  [dim]Running Ansible deployment (logging to file)...[/dim]", flush=True)
        
        # Run verbose process and WAIT for completion
        # Capture output to show dots for progress
        import threading
        import time
        
        verbose_process = subprocess.Popen(
            ansible_cmd,
            shell=True,
            cwd=str(cwd),
            env=env_verbose,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        
        # Show progress dots while waiting
        if not self.verbose:
            def show_progress():
                while verbose_process.poll() is None:
                    print(".", end="", flush=True)
                    time.sleep(5)
            
            progress_thread = threading.Thread(target=show_progress, daemon=True)
            progress_thread.start()
        
        # Wait for verbose process to complete
        verbose_returncode = verbose_process.wait()
        
        if not self.verbose:
            # Stop progress thread and clear line
            print("\r  [dim]✓ Deployment complete, showing results...[/dim]" + " " * 20, flush=True)
        
        # Store the actual result (this is the real deployment)
        actual_returncode = verbose_returncode
        
        self.logger.log(f"Ansible detailed log: {ansible_log_path}", "INFO")

        # Setup environment for TERMINAL output
        # IMPORTANT: Don't use ANSIBLE_LOG_PATH here (would overwrite verbose log)
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

        # Remove ANSIBLE_LOG_PATH from terminal env if it exists
        env_terminal.pop("ANSIBLE_LOG_PATH", None)

        if self.verbose:
            # VERBOSE MODE: Let Ansible write directly to terminal (no capture)
            # This preserves colors, formatting, and native Ansible output
            result = subprocess.run(
                ansible_cmd,
                shell=True,
                cwd=str(cwd),
                env=env_terminal,
            )
            # Ignore this returncode, use actual_returncode from verbose run
            returncode = actual_returncode
        else:
            # NON-VERBOSE MODE: Capture and display with tree_minimal
            import sys
            import selectors

            process = subprocess.Popen(
                ansible_cmd,
                shell=True,
                cwd=str(cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,  # Line buffered
                env=env_terminal,
            )

            # Use selectors for non-blocking read
            sel = selectors.DefaultSelector()
            sel.register(process.stdout, selectors.EVENT_READ)

            # Pass through output (to both main log and console)
            while True:
                # Check if process is still running
                if process.poll() is not None:
                    # Process finished, read any remaining output
                    break

                # Wait for data with timeout
                events = sel.select(timeout=0.1)
                if events:
                    line = process.stdout.readline()
                    if not line:
                        break

                    line_stripped = line.rstrip()

                    # Log to main log file
                    try:
                        self.logger.log_output(line_stripped, "ansible")
                    except (BlockingIOError, OSError):
                        pass

                    # Print to console WITH FLUSH
                    print(line_stripped, flush=True)
                    sys.stdout.flush()

            # Close selector
            sel.close()

            # Read any remaining output after process finished
            if process.stdout:
                remaining = process.stdout.read()
                if remaining:
                    for line in remaining.splitlines():
                        line_stripped = line.rstrip()
                        try:
                            self.logger.log_output(line_stripped, "ansible")
                        except (BlockingIOError, OSError):
                            pass
                        print(line_stripped, flush=True)

            returncode = process.wait()
            # Use actual_returncode from verbose run (that's the real deployment)
            returncode = actual_returncode

        return returncode
