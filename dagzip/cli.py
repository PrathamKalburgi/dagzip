"""
DAGZip Command-Line Interface

Provides a beautiful, interactive terminal experience for building, 
extracting, and comparing DAGZip archives. Built with Click for routing 
and Rich for terminal styling and animations.
"""

import os
import sys
import time
import click
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.status import Status

# Import our backend logic
from .dag_builder import create_archive
from .extractor import extract_archive
from .diff import print_diff_report
from .utils import format_size, get_directory_stats

# Initialize the global Rich console
console = Console()

# --- ASCII Art & Theming ---
DAGZIP_LOGO = """
    ____  ___   __________(_)___ 
   / __ \\/   | / ____/_  / / __ \\
  / / / / /| |/ / __  / / / /_/ /
 / /_/ / ___ / /_/ / / /_/ ____/ 
/_____/_/  |_\\____/ /___/_/      
"""

def print_header() -> None:
    """Renders the stylized DAGZip logo and version info."""
    logo_text = Text(DAGZIP_LOGO, style="bold cyan")
    subtitle = Text("Content-Defined DAG Archiver v0.1.0", style="italic magenta")
    
    panel = Panel.fit(
        logo_text + Text("\n") + subtitle,
        border_style="blue",
        padding=(1, 5)
    )
    console.print(panel)


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """
    DAGZip: Next-generation deduplicating archiver.
    
    Commands:
      pack   - Compress a directory into a .dgz archive.
      unpack - Extract a .dgz archive.
      diff   - Compare two .dgz archives for changes.
    """
    if ctx.invoked_subcommand is None:
        print_header()
        click.echo(ctx.get_help())


@cli.command("pack")
@click.argument("source_dir", type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.argument("output_file", type=click.Path(writable=True))
@click.option("--encrypt", "-e", is_flag=True, help="Enable AES-256-GCM encryption.")
def pack(source_dir: str, output_file: str, encrypt: bool) -> None:
    """Compresses and deduplicates a directory into a .dgz archive."""
    print_header()
    
    console.print(f"[bold yellow]Analyzing directory:[/bold yellow] {source_dir}")
    total_size, file_count = get_directory_stats(source_dir)
    
    stats_msg = (
        f"Found [bold cyan]{file_count}[/bold cyan] files "
        f"totaling [bold green]{format_size(total_size)}[/bold green]."
    )
    console.print(stats_msg)
    
    password = ""
    if encrypt:
        console.print("[bold red]Encryption Enabled.[/bold red] Please set a password.")
        password = click.prompt("Password", hide_input=True, confirmation_prompt=True)
        
    start_time = time.time()
    
    try:
        with Status(
            "[bold cyan]Chunking, compressing, and building DAG manifest...[/bold cyan]",
            spinner="dots",
            console=console
        ) as status:
            create_archive(
                source=source_dir,
                destination=output_file,
                use_encryption=encrypt,
                password=password
            )
            
    except Exception as e:
        console.print(f"\n[bold red]✖ Error during packing:[/bold red] {e}")
        sys.exit(1)
        
    elapsed_time = time.time() - start_time
    final_size = os.path.getsize(output_file)
    ratio = (total_size / final_size) if final_size > 0 else 0
    
    summary = (
        f"✔ [bold green]Archive built successfully![/bold green]\n"
        f"Time taken:   {elapsed_time:.2f} seconds\n"
        f"Final size:   [bold cyan]{format_size(final_size)}[/bold cyan]\n"
        f"Space saved:  {ratio:.2f}x compression ratio"
    )
    console.print(Panel(summary, border_style="green", expand=False))


@cli.command("unpack")
@click.argument("archive_file", type=click.Path(exists=True, file_okay=True, dir_okay=False))
@click.argument("destination_dir", type=click.Path(writable=True))
@click.option("--password", "-p", default="", help="Password for encrypted archives.")
def unpack(archive_file: str, destination_dir: str, password: str) -> None:
    """Extracts a .dgz archive back into a standard directory."""
    print_header()
    console.print(f"[bold yellow]Preparing to extract:[/bold yellow] {archive_file}")
    
    start_time = time.time()
    
    try:
        with Status(
            "[bold magenta]Traversing DAG and reassembling files...[/bold magenta]",
            spinner="bouncingBar",
            console=console
        ) as status:
            extract_archive(
                archive_path=archive_file,
                destination=destination_dir,
                password=password
            )
            
    except ValueError as e:
        if "password is required" in str(e).lower() or "incorrect password" in str(e).lower():
            console.print("\n[bold red]✖ Locked Archive![/bold red]")
            pwd = click.prompt("Please enter the archive password", hide_input=True)
            try:
                with Status("[bold magenta]Decrypting...[/bold magenta]", console=console):
                    extract_archive(archive_file, destination_dir, pwd)
            except Exception as retry_e:
                console.print(f"[bold red]✖ Decryption failed:[/bold red] {retry_e}")
                sys.exit(1)
        else:
            console.print(f"\n[bold red]✖ Error during extraction:[/bold red] {e}")
            sys.exit(1)
            
    except Exception as e:
        console.print(f"\n[bold red]✖ Critical Error:[/bold red] {e}")
        sys.exit(1)

    elapsed_time = time.time() - start_time
    console.print(f"\n✔ [bold green]Extraction complete in {elapsed_time:.2f} seconds![/bold green]")
    console.print(f"Files extracted to: [bold cyan]{os.path.abspath(destination_dir)}[/bold cyan]")


@cli.command("diff")
@click.argument("old_archive", type=click.Path(exists=True, file_okay=True, dir_okay=False))
@click.argument("new_archive", type=click.Path(exists=True, file_okay=True, dir_okay=False))
@click.option("--old-pwd", default="", help="Password for the old archive.")
@click.option("--new-pwd", default="", help="Password for the new archive.")
def diff_cmd(old_archive: str, new_archive: str, old_pwd: str, new_pwd: str) -> None:
    """Compares two .dgz archives and lists file changes (Added/Removed/Modified)."""
    print_header()
    
    # We catch password errors here to prompt nicely, just like in unpack
    try:
        print_diff_report(old_archive, new_archive, old_pwd, new_pwd)
    except ValueError as e:
        if "password" in str(e).lower():
            console.print("\n[bold red]✖ One or both archives are locked![/bold red]")
            opwd = click.prompt("Password for OLD archive", hide_input=True)
            npwd = click.prompt("Password for NEW archive", hide_input=True)
            print_diff_report(old_archive, new_archive, opwd, npwd)
        else:
            console.print(f"\n[bold red]✖ Error calculating diff:[/bold red] {e}")

@cli.command("serve")
@click.argument("archive_file", type=click.Path(exists=True, file_okay=True, dir_okay=False))
@click.option("--password", "-p", default="", help="Password for the encrypted archive.")
@click.option("--port", default=8000, help="Port to run the HTTP server on.")
def serve_cmd(archive_file: str, password: str, port: int) -> None:
    """Hosts the archive over a FastAPI REST interface."""
    from .server import run_server
    print_header()
    
    # Check for password early so the server doesn't crash during boot
    try:
        # We do a quick dry-run of the extractor to validate the password
        from .extractor import ArchiveExtractor
        ArchiveExtractor(archive_file, password)
    except ValueError as e:
        if "password" in str(e).lower():
            console.print("\n[bold red]✖ Archive is locked![/bold red]")
            password = click.prompt("Please enter the archive password", hide_input=True)
            
    console.print(f"[bold green]Starting local server on port {port}...[/bold green]")
    run_server(archive_path=archive_file, password=password, port=port)
    
if __name__ == "__main__":
    cli()
