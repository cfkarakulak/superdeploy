"""
Utility for executing superdeploy CLI commands from backend.
"""

import asyncio
import os
from pathlib import Path
from typing import AsyncIterator, List, Optional


class SuperdeployCLI:
    """
    Centralized CLI executor for superdeploy commands.
    Uses the venv from superdeploy root to avoid ModuleNotFoundError.
    """

    def __init__(self):
        # Get superdeploy root (cli.py -> utils -> backend -> dashboard -> superdeploy)
        self.superdeploy_root = Path(__file__).parent.parent.parent.parent
        self.venv_python = self.superdeploy_root / "venv" / "bin" / "python"

        # Validate venv exists
        if not self.venv_python.exists():
            raise RuntimeError(
                f"Superdeploy venv not found at: {self.venv_python}\n"
                f"Please run: cd {self.superdeploy_root} && python3 -m venv venv && "
                f"source venv/bin/activate && pip install -r requirements.txt && pip install -e ."
            )

    async def execute(
        self,
        command: str,
        args: Optional[List[str]] = None,
        stream_output: bool = True,
    ) -> AsyncIterator[str]:
        """
        Execute a superdeploy CLI command.

        Args:
            command: The superdeploy command (e.g., "cheapa:logs", "cheapa:up")
            args: Additional arguments for the command
            stream_output: Whether to stream output line by line

        Yields:
            Output lines from the command

        Example:
            cli = SuperdeployCLI()
            async for line in cli.execute("cheapa:logs", ["-a", "api", "-n", "100"]):
                print(line)
        """
        # Build command
        cmd = [str(self.venv_python), "-m", "cli.main", command]
        if args:
            cmd.extend(args)

        # Set environment variables for proper output formatting
        env = {
            **os.environ,
            "COLUMNS": "200",  # Wide terminal to avoid line wrapping
            "LINES": "50",
        }

        # Execute
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(self.superdeploy_root),
            env=env,
        )

        # Stream output
        while True:
            line = await process.stdout.readline()
            if not line:
                break

            decoded_line = line.decode("utf-8", errors="replace")
            yield decoded_line

        await process.wait()

        # Raise error if command failed
        if process.returncode != 0:
            raise RuntimeError(
                f"Command '{' '.join(cmd)}' failed with exit code {process.returncode}"
            )

    async def execute_simple(
        self, command: str, args: Optional[List[str]] = None
    ) -> tuple[str, int]:
        """
        Execute a superdeploy CLI command and return full output.

        Args:
            command: The superdeploy command (e.g., "cheapa:logs")
            args: Additional arguments for the command

        Returns:
            Tuple of (output, exit_code)

        Example:
            cli = SuperdeployCLI()
            output, code = await cli.execute_simple("cheapa:ps")
            print(output)
        """
        # Build command
        cmd = [str(self.venv_python), "-m", "cli.main", command]
        if args:
            cmd.extend(args)

        # Set environment variables for proper output formatting
        env = {
            **os.environ,
            "COLUMNS": "200",  # Wide terminal to avoid line wrapping
            "LINES": "50",
        }

        # Execute
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(self.superdeploy_root),
            env=env,
        )

        stdout, _ = await process.communicate()
        output = stdout.decode("utf-8", errors="replace")

        return output, process.returncode

    async def execute_json(
        self, command: str, args: Optional[List[str]] = None, timeout: int = 30
    ) -> dict:
        """
        Execute a superdeploy CLI command with --json flag and return parsed JSON.

        Args:
            command: The superdeploy command (e.g., "cheapa:ps")
            args: Additional arguments for the command (--json will be added automatically)
            timeout: Maximum seconds to wait for command (default: 30)

        Returns:
            Parsed JSON dictionary

        Raises:
            RuntimeError: If command fails or output is not valid JSON
            asyncio.TimeoutError: If command exceeds timeout

        Example:
            cli = SuperdeployCLI()
            data = await cli.execute_json("cheapa:ps", timeout=15)
            print(data)
        """
        import json

        # Build command with --json flag
        cmd = [str(self.venv_python), "-m", "cli.main", command]
        if args:
            cmd.extend(args)
        
        # Add --json flag if not already present
        if "--json" not in cmd:
            cmd.append("--json")

        # Set environment variables
        env = {
            **os.environ,
            "COLUMNS": "200",
            "LINES": "50",
        }

        # Execute with timeout
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.superdeploy_root),
            env=env,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise RuntimeError(
                f"Command '{' '.join(cmd)}' timed out after {timeout} seconds"
            )

        # Check for errors
        if process.returncode != 0:
            error_output = stderr.decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Command '{' '.join(cmd)}' failed with exit code {process.returncode}\n{error_output}"
            )

        # Parse JSON output
        output = stdout.decode("utf-8", errors="replace").strip()
        
        try:
            return json.loads(output)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"Failed to parse JSON output from command '{' '.join(cmd)}': {e}\nOutput: {output[:200]}"
            )


# Global singleton instance
_cli_instance: Optional[SuperdeployCLI] = None


def get_cli() -> SuperdeployCLI:
    """Get or create the global CLI executor instance."""
    global _cli_instance
    if _cli_instance is None:
        _cli_instance = SuperdeployCLI()
    return _cli_instance
