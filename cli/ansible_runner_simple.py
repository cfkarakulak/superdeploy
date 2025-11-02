"""Simple Ansible runner - just logs, no tree view"""
import subprocess

class AnsibleRunner:
    def __init__(self, logger, title="Configuring", verbose=False):
        self.logger = logger
        self.verbose = verbose
    
    def run(self, ansible_cmd, cwd):
        self.logger.log_command(ansible_cmd)
        result = subprocess.run(
            ansible_cmd,
            shell=True,
            cwd=str(cwd),
        )
        return result.returncode
