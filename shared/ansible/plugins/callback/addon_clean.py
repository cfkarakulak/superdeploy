"""
Addon Clean Output Callback Plugin

Shows clean addon deployment output with tree view:
- Each addon as main-level play
- Hide internal config tasks
- Show only key milestones
"""

from ansible.plugins.callback.minimal import CallbackModule as MinimalCallback

DOCUMENTATION = """
    callback: addon_clean
    type: stdout
    short_description: Clean addon deployment output with tree view
    description:
        - Filters out internal addon config tasks
        - Shows only key deployment milestones
        - Uses tree-style output format
    extends_documentation_fragment:
      - default_callback
"""


class CallbackModule(MinimalCallback):
    """Clean addon deployment output callback with tree view."""

    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = "stdout"
    CALLBACK_NAME = "addon_clean"

    def __init__(self):
        super().__init__()
        self._hidden_task_patterns = [
            "Set instance paths",
            "Display instance deployment info",
            "Check if addon type exists",
            "Fail if addon type does not exist",
            "Load addon metadata",
            "Fail if addon.yml",
            "Get addon instance credentials",
            "Validate instance credentials",
            "Set instance-specific environment",
            "Add common instance variables",
            "Get resource limits",
            "Add resource variables",
            "Generate .env file",
            "Check if addon has templates",
            "Set addon has templates",
            "Check if addon has compose",
            "Set metadata variables",
            "Flatten environment variables",
            "Find additional templates",
            "Check if addon has ansible.yml",
            "Deploy addon instance tasks",
        ]

    def _task_should_be_shown(self, task_name):
        """Check if task should be displayed."""
        if not task_name:
            return True

        # Always show tasks starting with emoji or special chars
        if task_name.startswith(("✓", "▶", "🗄️", "🐰", "🌐", "✅")):
            return True

        # Hide internal config tasks
        for pattern in self._hidden_task_patterns:
            if pattern in task_name:
                return False

        return True

    def v2_runner_on_ok(self, result, **kwargs):
        """Handle successful task."""
        task_name = result._task.get_name()

        if self._task_should_be_shown(task_name):
            super().v2_runner_on_ok(result, **kwargs)

    def v2_runner_on_failed(self, result, **kwargs):
        """Handle failed task - always show failures."""
        super().v2_runner_on_failed(result, **kwargs)

    def v2_runner_on_skipped(self, result, **kwargs):
        """Handle skipped task."""
        task_name = result._task.get_name()

        if self._task_should_be_shown(task_name):
            super().v2_runner_on_skipped(result, **kwargs)
