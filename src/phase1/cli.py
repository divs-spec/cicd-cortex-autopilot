import click
import os
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from dotenv import load_dotenv

from .github_client import GitHubClient
from .llm_analyzer import LLMAnalyzer
from .models import FailureAnalysis

# Load environment variables
load_dotenv()

console = Console()


@click.group()
def cli():
    """AEIA - Autonomous Engineering Intelligence Agent (Phase 1)"""
    pass


@cli.command()
@click.option('--owner', '-o', required=True, help='Repository owner')
@click.option('--repo', '-r', required=True, help='Repository name')
@click.option('--run-id', '-i', type=int, help='Workflow run ID (optional, uses latest failed if not provided)')
def analyze(owner: str, repo: str, run_id: int = None):
    """Analyze a failed GitHub Actions workflow run"""
    
    console.print(f"\n[bold cyan]AEIA Phase 1: Workflow Failure Analysis[/bold cyan]\n")
    
    try:
        # Initialize clients
        with console.status("[bold yellow]Initializing GitHub client..."):
            github_client = GitHubClient()
        
        # Fetch workflow run
        if run_id:
            console.print(f"[cyan]Fetching workflow run {run_id}...[/cyan]")
            workflow_run = github_client.get_workflow_run(owner, repo, run_id)
        else:
            console.print(f"[cyan]Fetching latest failed workflow run...[/cyan]")
            workflow_run = github_client.get_latest_failed_run(owner, repo)
            
            if not workflow_run:
                console.print("[red]No failed workflow runs found.[/red]")
                return
        
        # Display workflow info
        _display_workflow_info(workflow_run)
        
        # Analyze with LLM
        with console.status("[bold yellow]Analyzing failure with LLM..."):
            analyzer = LLMAnalyzer()
            analysis = analyzer.analyze_workflow_failure(workflow_run)
        
        # Display analysis
        _display_analysis(analysis)
        
        console.print(f"\n[green]✓ Analysis complete![/green]")
        console.print(f"[dim]View full workflow: {workflow_run.html_url}[/dim]\n")
        
    except Exception as e:
        console.print(f"\n[red]Error: {str(e)}[/red]\n")
        raise


def _display_workflow_info(workflow_run):
    """Display workflow run information"""
    info_table = Table(show_header=False, box=None)
    info_table.add_row("[bold]Repository:[/bold]", workflow_run.repository)
    info_table.add_row("[bold]Workflow:[/bold]", workflow_run.name)
    info_table.add_row("[bold]Branch:[/bold]", workflow_run.head_branch)
    info_table.add_row("[bold]Commit:[/bold]", workflow_run.head_sha[:8])
    info_table.add_row("[bold]Status:[/bold]", f"[red]{workflow_run.conclusion}[/red]")
    
    console.print(Panel(info_table, title="[bold]Workflow Information[/bold]", border_style="cyan"))


def _display_analysis(analysis: FailureAnalysis):
    """Display failure analysis results"""
    
    # Summary
    console.print(f"\n[bold yellow]Summary[/bold yellow]")
    console.print(Panel(analysis.summary, border_style="yellow"))
    
    # Failed jobs and steps
    if analysis.failed_jobs:
        console.print(f"\n[bold red]Failed Jobs[/bold red]")
        for job in analysis.failed_jobs:
            console.print(f"  • {job}")
    
    if analysis.failed_steps:
        console.print(f"\n[bold red]Failed Steps[/bold red]")
        for step in analysis.failed_steps[:5]:  # Show first 5
            console.print(f"  • {step}")
    
    # Root cause
    console.print(f"\n[bold magenta]Likely Cause[/bold magenta]")
    console.print(Panel(analysis.likely_cause, border_style="magenta"))
    
    # Suggested actions
    if analysis.suggested_actions:
        console.print(f"\n[bold green]Suggested Actions[/bold green]")
        for i, action in enumerate(analysis.suggested_actions, 1):
            console.print(f"  {i}. {action}")
    
    # Confidence
    confidence_color = "green" if analysis.confidence > 0.7 else "yellow" if analysis.confidence > 0.4 else "red"
    console.print(f"\n[bold]Confidence:[/bold] [{confidence_color}]{analysis.confidence:.0%}[/{confidence_color}]")
    
    # Error details
    if analysis.error_contexts:
        console.print(f"\n[bold]Error Details[/bold]")
        for i, error in enumerate(analysis.error_contexts[:3], 1):  # Show first 3
            console.print(f"\n[dim]Error {i}:[/dim]")
            console.print(f"  Type: {error.error_type}")
            console.print(f"  Message: {error.error_message[:100]}...")
            if error.file_path:
                location = f"{error.file_path}"
                if error.line_number:
                    location += f":{error.line_number}"
                console.print(f"  Location: {location}")


@cli.command()
def config():
    """Show current configuration"""
    console.print("\n[bold cyan]AEIA Configuration[/bold cyan]\n")
    
    github_token = os.getenv("GITHUB_TOKEN")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    
    config_table = Table(show_header=True)
    config_table.add_column("Variable", style="cyan")
    config_table.add_column("Status", style="green")
    
    config_table.add_row(
        "GITHUB_TOKEN",
        "✓ Set" if github_token else "[red]✗ Not set[/red]"
    )
    config_table.add_row(
        "ANTHROPIC_API_KEY",
        "✓ Set" if anthropic_key else "[red]✗ Not set[/red]"
    )
    
    console.print(config_table)
    console.print()


def main():
    cli()


if __name__ == "__main__":
    main()
