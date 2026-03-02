"""Rich terminal output and markdown formatting."""

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

console = Console()


def print_brief(brief: str, output_format: str = "terminal") -> None:
    """Render the meeting prep brief in the requested format."""
    if output_format == "markdown":
        print(brief)
    else:
        console.print(
            Panel(
                Markdown(brief),
                title="[bold blue]Meeting Prep Brief[/bold blue]",
                border_style="blue",
                padding=(1, 2),
            )
        )
