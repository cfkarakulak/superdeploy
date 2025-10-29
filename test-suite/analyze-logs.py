#!/usr/bin/env python3
"""
SuperDeploy Test Log Analyzer
Analyzes test suite logs and generates detailed insights
"""

import os
import re
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict


class LogAnalyzer:
    def __init__(self, log_dir):
        self.log_dir = Path(log_dir)
        self.results = {
            "phases": {},
            "errors": [],
            "warnings": [],
            "timings": {},
            "ip_changes": {},
            "docker_status": {},
            "ssh_status": {},
        }

    def analyze_all(self):
        """Run all analysis phases"""
        print("🔍 Analyzing test logs...")
        print(f"📁 Log directory: {self.log_dir}")
        print()

        self.analyze_down_log()
        self.analyze_generate_log()
        self.analyze_up_log()
        self.analyze_ssh_logs()
        self.analyze_docker_logs()
        self.analyze_ip_preservation()

        self.generate_report()

    def analyze_down_log(self):
        """Analyze infrastructure destruction log"""
        log_file = self.log_dir / "01_down.log"
        if not log_file.exists():
            return

        print("📋 Analyzing down phase...")
        content = log_file.read_text()

        # Extract timing
        timing_match = re.search(r"real\s+(\d+)m([\d.]+)s", content)
        if timing_match:
            minutes = int(timing_match.group(1))
            seconds = float(timing_match.group(2))
            self.results["timings"]["down"] = minutes * 60 + seconds

        # Check for errors
        errors = re.findall(r"Error:.*", content)
        self.results["errors"].extend([f"[DOWN] {e}" for e in errors])

        # Check Terraform destroy
        if "Destroy complete!" in content:
            self.results["phases"]["down"] = "✓ Success"
        elif "Error" in content:
            self.results["phases"]["down"] = "✗ Failed"
        else:
            self.results["phases"]["down"] = "⚠ Unknown"

    def analyze_generate_log(self):
        """Analyze configuration generation log"""
        log_file = self.log_dir / "02_generate.log"
        if not log_file.exists():
            return

        print("📋 Analyzing generate phase...")
        content = log_file.read_text()

        # Extract timing
        timing_match = re.search(r"real\s+(\d+)m([\d.]+)s", content)
        if timing_match:
            minutes = int(timing_match.group(1))
            seconds = float(timing_match.group(2))
            self.results["timings"]["generate"] = minutes * 60 + seconds

        # Check for success
        if "Generation complete!" in content:
            self.results["phases"]["generate"] = "✓ Success"
        elif "Error" in content or "Failed" in content:
            self.results["phases"]["generate"] = "✗ Failed"
            errors = re.findall(r"Error:.*", content)
            self.results["errors"].extend([f"[GENERATE] {e}" for e in errors])
        else:
            self.results["phases"]["generate"] = "⚠ Unknown"

    def analyze_up_log(self):
        """Analyze infrastructure deployment log"""
        log_file = self.log_dir / "03_up.log"
        if not log_file.exists():
            return

        print("📋 Analyzing up phase...")
        content = log_file.read_text()

        # Extract timing
        timing_match = re.search(r"real\s+(\d+)m([\d.]+)s", content)
        if timing_match:
            minutes = int(timing_match.group(1))
            seconds = float(timing_match.group(2))
            self.results["timings"]["up"] = minutes * 60 + seconds

        # Check Terraform apply
        if "Apply complete!" in content:
            self.results["phases"]["terraform"] = "✓ Success"
        elif "Error" in content and "Terraform" in content:
            self.results["phases"]["terraform"] = "✗ Failed"

        # Check Ansible deployment
        if "PLAY RECAP" in content:
            # Parse Ansible recap
            recap_section = content.split("PLAY RECAP")[1].split("\n\n")[0]
            
            failed_count = len(re.findall(r"failed=([1-9]\d*)", recap_section))
            unreachable_count = len(re.findall(r"unreachable=([1-9]\d*)", recap_section))
            
            if failed_count > 0 or unreachable_count > 0:
                self.results["phases"]["ansible"] = f"✗ Failed ({failed_count} failed, {unreachable_count} unreachable)"
            else:
                self.results["phases"]["ansible"] = "✓ Success"
        
        # Extract errors
        errors = re.findall(r"Error:.*", content)
        self.results["errors"].extend([f"[UP] {e}" for e in errors])

        # Extract warnings
        warnings = re.findall(r"Warning:.*", content)
        self.results["warnings"].extend([f"[UP] {w}" for w in warnings])

    def analyze_ssh_logs(self):
        """Analyze SSH connectivity logs"""
        print("📋 Analyzing SSH connectivity...")
        
        for vm in ["web", "api", "worker"]:
            log_file = self.log_dir / f"04_ssh_{vm}.log"
            if not log_file.exists():
                continue
            
            content = log_file.read_text()
            if "SSH OK" in content:
                self.results["ssh_status"][vm] = "✓ Connected"
            else:
                self.results["ssh_status"][vm] = "✗ Failed"

    def analyze_docker_logs(self):
        """Analyze Docker container status logs"""
        print("📋 Analyzing Docker containers...")
        
        for vm in ["web", "api", "worker"]:
            log_file = self.log_dir / f"05_docker_{vm}.log"
            if not log_file.exists():
                continue
            
            content = log_file.read_text()
            
            # Count containers
            containers = []
            for line in content.split("\n")[1:]:  # Skip header
                if line.strip():
                    parts = line.split()
                    if parts:
                        container_name = parts[0]
                        status = " ".join(parts[1:])
                        containers.append({
                            "name": container_name,
                            "status": status,
                            "healthy": "healthy" in status.lower() or "Up" in status
                        })
            
            self.results["docker_status"][vm] = containers

    def analyze_ip_preservation(self):
        """Analyze IP preservation results"""
        print("📋 Analyzing IP preservation...")
        
        expected_file = self.log_dir / "expected_ips.txt"
        actual_file = self.log_dir / "actual_ips.txt"
        
        if not expected_file.exists() or not actual_file.exists():
            return
        
        expected = {}
        for line in expected_file.read_text().split("\n"):
            if "=" in line:
                key, value = line.split("=")
                expected[key] = value
        
        actual = {}
        for line in actual_file.read_text().split("\n"):
            if "=" in line:
                key, value = line.split("=")
                vm = key.replace("NEW_", "").replace("_IP", "").lower()
                actual[vm] = value
        
        for vm in ["web", "api", "worker"]:
            old_key = f"{vm.upper()}_IP"
            if old_key in expected and vm in actual:
                old_ip = expected[old_key]
                new_ip = actual[vm]
                
                if old_ip == new_ip:
                    self.results["ip_changes"][vm] = f"✓ Preserved ({old_ip})"
                else:
                    self.results["ip_changes"][vm] = f"✗ Changed ({old_ip} → {new_ip})"

    def generate_report(self):
        """Generate analysis report"""
        print()
        print("=" * 80)
        print("📊 TEST ANALYSIS REPORT")
        print("=" * 80)
        print()

        # Phase Results
        print("🔄 DEPLOYMENT PHASES")
        print("-" * 80)
        for phase, status in self.results["phases"].items():
            print(f"  {phase.ljust(15)}: {status}")
        print()

        # Timings
        if self.results["timings"]:
            print("⏱️  EXECUTION TIMES")
            print("-" * 80)
            total_time = 0
            for phase, seconds in self.results["timings"].items():
                minutes = int(seconds // 60)
                secs = int(seconds % 60)
                print(f"  {phase.ljust(15)}: {minutes}m {secs}s")
                total_time += seconds
            
            total_minutes = int(total_time // 60)
            total_secs = int(total_time % 60)
            print(f"  {'TOTAL'.ljust(15)}: {total_minutes}m {total_secs}s")
            print()

        # IP Preservation
        if self.results["ip_changes"]:
            print("🌐 IP PRESERVATION")
            print("-" * 80)
            all_preserved = all("✓" in status for status in self.results["ip_changes"].values())
            for vm, status in self.results["ip_changes"].items():
                print(f"  {vm.ljust(15)}: {status}")
            
            if all_preserved:
                print()
                print("  ✓ All IPs preserved successfully!")
            print()

        # SSH Status
        if self.results["ssh_status"]:
            print("🔐 SSH CONNECTIVITY")
            print("-" * 80)
            for vm, status in self.results["ssh_status"].items():
                print(f"  {vm.ljust(15)}: {status}")
            print()

        # Docker Status
        if self.results["docker_status"]:
            print("🐳 DOCKER CONTAINERS")
            print("-" * 80)
            for vm, containers in self.results["docker_status"].items():
                print(f"  {vm.upper()} VM:")
                if containers:
                    for container in containers:
                        health_icon = "✓" if container["healthy"] else "✗"
                        print(f"    {health_icon} {container['name']}: {container['status']}")
                else:
                    print("    (no containers found)")
            print()

        # Errors
        if self.results["errors"]:
            print("❌ ERRORS")
            print("-" * 80)
            for error in self.results["errors"][:10]:  # Show first 10
                print(f"  • {error}")
            if len(self.results["errors"]) > 10:
                print(f"  ... and {len(self.results['errors']) - 10} more")
            print()

        # Warnings
        if self.results["warnings"]:
            print("⚠️  WARNINGS")
            print("-" * 80)
            for warning in self.results["warnings"][:10]:  # Show first 10
                print(f"  • {warning}")
            if len(self.results["warnings"]) > 10:
                print(f"  ... and {len(self.results['warnings']) - 10} more")
            print()

        # Summary
        print("=" * 80)
        print("📝 SUMMARY")
        print("=" * 80)
        
        success_count = sum(1 for status in self.results["phases"].values() if "✓" in status)
        total_phases = len(self.results["phases"])
        error_count = len(self.results["errors"])
        warning_count = len(self.results["warnings"])
        
        print(f"  Phases completed: {success_count}/{total_phases}")
        print(f"  Errors: {error_count}")
        print(f"  Warnings: {warning_count}")
        
        if success_count == total_phases and error_count == 0:
            print()
            print("  ✅ ALL TESTS PASSED!")
        elif error_count > 0:
            print()
            print("  ❌ TESTS FAILED - Review errors above")
        else:
            print()
            print("  ⚠️  TESTS COMPLETED WITH WARNINGS")
        
        print("=" * 80)


def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze-logs.py <log_directory>")
        print()
        print("Example:")
        print("  python analyze-logs.py superdeploy/test-suite/logs/20251029_143022")
        sys.exit(1)
    
    log_dir = sys.argv[1]
    
    if not os.path.exists(log_dir):
        print(f"Error: Log directory not found: {log_dir}")
        sys.exit(1)
    
    analyzer = LogAnalyzer(log_dir)
    analyzer.analyze_all()


if __name__ == "__main__":
    main()
