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

        for line in lines:
            line = line.strip()
            if not line:
                continue

            speaker, text = self._extract_speaker(line)
            if speaker:
                self.current_speaker = speaker

            if text:
                self.items.append(TranscriptItem(
                    idx=idx,
                    speaker=self.current_speaker,
                    text=text,
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