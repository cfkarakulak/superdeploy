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
        ansible_log_path = self.logger.log_path.parent / f"{self.logger.log_path.stem}_ansible.log"
        
        # Setup environment for VERBOSE logging to file
        env_verbose = os.environ.copy()
        env_verbose.update({
            "PYTHONUNBUFFERED": "1",
            "ANSIBLE_STDOUT_CALLBACK": "default",  # RAW output for log file
            "ANSIBLE_DISPLAY_SKIPPED_HOSTS": "false",
            "ANSIBLE_LOG_PATH": str(ansible_log_path),
            "ANSIBLE_NOCOLOR": "true",  # No colors in log file
        })
        
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
        env_terminal.update({
            "PYTHONUNBUFFERED": "1",
            "ANSIBLE_STDOUT_CALLBACK": "tree_minimal" if not self.verbose else "default",
            "ANSIBLE_DISPLAY_SKIPPED_HOSTS": "false",
            # Don't write to log file from this process
        })
        
        # Run Ansible for terminal output (tree_minimal or default)
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
                
                # Log to main log file (with tree_minimal or default output)
                try:
                    self.logger.log_output(line_stripped, "ansible")
                except (BlockingIOError, OSError):
                    pass
                
                # Print to console (always, both verbose and non-verbose)
                print(line_stripped)
        
        returncode = process.wait()
        
        # Wait for background logger to finish
        log_thread.join(timeout=5)
        
        return returncode
