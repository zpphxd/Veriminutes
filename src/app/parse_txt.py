import re
from typing import List, Optional, Tuple
from pathlib import Path
from datetime import datetime

from .schema import Transcript_v1, TranscriptItem, TranscriptMetadata


class TxtParser:
    """Parse plain text transcripts into normalized JSON format."""

    SPEAKER_PATTERN = re.compile(r'^\s*([A-Za-z][\w .\-]{0,50}):\s+(.+)$')

    def __init__(self):
        self.items: List[TranscriptItem] = []
        self.current_speaker = "Unknown"

    def parse_file(
        self,
        file_path: str,
        date: Optional[str] = None,
        title: Optional[str] = None,
        attendees: Optional[List[str]] = None
    ) -> Transcript_v1:
        """Parse a text file into a normalized transcript."""

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        self.items = []
        idx = 0

        # Preserve the original content exactly as-is
        for line in lines:
            # Keep the original line, just remove trailing newline
            line = line.rstrip('\n')

            # Still try to detect speaker for metadata, but preserve original text
            speaker, _ = self._extract_speaker(line)
            if speaker:
                self.current_speaker = speaker

            # Add the complete original line as an item
            if line or line == "":  # Include blank lines too
                self.items.append(TranscriptItem(
                    idx=idx,
                    speaker=self.current_speaker if speaker else "Text",
                    text=line,  # Keep original line intact
                    ts=None
                ))
                idx += 1

        metadata = TranscriptMetadata(
            date=date or datetime.now().isoformat()[:10],
            title=title or path.stem,
            attendees=attendees or self._extract_attendees()
        )

        return Transcript_v1(
            provider="txt",
            items=self.items,
            metadata=metadata
        )

    def _extract_speaker(self, line: str) -> Tuple[Optional[str], str]:
        """Extract speaker label and text from a line."""

        match = self.SPEAKER_PATTERN.match(line)
        if match:
            speaker = match.group(1).strip()
            text = match.group(2).strip()
            return speaker, text

        return None, line

    def _extract_attendees(self) -> List[str]:
        """Extract unique speakers as attendees."""

        speakers = set()
        for item in self.items:
            if item.speaker and item.speaker != "Unknown":
                speakers.add(item.speaker)

        return sorted(list(speakers))