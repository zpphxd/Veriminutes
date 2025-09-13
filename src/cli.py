#!/usr/bin/env python3

import click
import json
from pathlib import Path
from typing import Optional

from .app.service import VeriMinutesService


@click.group()
def main():
    """VeriMinutes CLI - Local-first verifiable minutes system."""
    pass


@main.command()
@click.option('--path', required=True, help='Path to TXT transcript file')
@click.option('--date', help='Meeting date (YYYY-MM-DD)')
@click.option('--attendees', help='Comma-separated list of attendees')
@click.option('--title', help='Meeting title')
def ingest(path: str, date: Optional[str], attendees: Optional[str], title: Optional[str]):
    """Ingest a TXT transcript and normalize to JSON."""

    service = VeriMinutesService()

    file_path = Path(path)
    if not file_path.exists():
        click.echo(f"Error: File not found: {path}", err=True)
        return

    try:
        slug, transcript_path, manifest_path = service.ingest_transcript(
            str(file_path),
            date=date,
            attendees=attendees,
            title=title
        )

        click.echo(f"✓ Transcript ingested successfully")
        click.echo(f"  Slug: {slug}")
        click.echo(f"  Transcript: {transcript_path}")
        click.echo(f"  Manifest: {manifest_path}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@main.command()
@click.option('--slug', required=True, help='Session slug')
def build(slug: str):
    """Build credentials, proofs, and PDF for a session."""

    service = VeriMinutesService()

    try:
        paths = service.build_artifacts(slug)

        click.echo(f"✓ Artifacts built successfully")
        click.echo(f"  Minutes: {paths.get('minutes', 'N/A')}")
        click.echo(f"  Credential: {paths.get('minutes_cred', 'N/A')}")
        click.echo(f"  Proof: {paths.get('minutes_proof', 'N/A')}")
        click.echo(f"  Packet: {paths.get('packet', 'N/A')}")
        click.echo(f"  PDF: {paths.get('pdf', 'N/A')}")

        if paths.get('anchor_receipt'):
            click.echo(f"  Anchor: {paths['anchor_receipt']}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@main.command()
@click.option('--slug', required=True, help='Session slug')
def verify(slug: str):
    """Verify artifacts for a session."""

    service = VeriMinutesService()

    try:
        result = service.verify_artifacts(slug)

        if result.valid:
            click.echo("✓ Verification PASSED")
        else:
            click.echo("✗ Verification FAILED", err=True)

        click.echo(f"  Local Root: {result.localRoot[:16]}...")
        click.echo(f"  Doc Hash: {result.docHash[:16]}...")

        if result.onChainRoot:
            click.echo(f"  On-chain Root: {result.onChainRoot[:16]}...")
        if result.txHash:
            click.echo(f"  Tx Hash: {result.txHash[:16]}...")

        result_json = json.dumps(result.model_dump(), indent=2)
        click.echo(f"\nFull result:\n{result_json}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@main.command()
def list():
    """List all available sessions."""

    service = VeriMinutesService()
    sessions = service.storage.list_sessions()

    if sessions:
        click.echo("Available sessions:")
        for session in sessions:
            click.echo(f"  - {session}")
    else:
        click.echo("No sessions found")


if __name__ == "__main__":
    main()