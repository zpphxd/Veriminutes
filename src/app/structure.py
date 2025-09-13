import re
from typing import List, Optional, Dict, Set
from pathlib import Path

from .schema import (
    Transcript_v1, BoardMinutes_v1, AgendaItem, Motion, Vote,
    Decision, Action, Source
)


class MinutesStructurer:
    """Extract structured board minutes from normalized transcripts using heuristics."""

    MOTION_PATTERNS = [
        r'\b(motion|move to|moved that|propose|resolution)\b',
        r'\b(second|seconded|seconding)\b',
        r'\b(vote|voting|voted|approve|approved|pass|passed|fail|failed|carried|defeated)\b'
    ]

    DECISION_PATTERNS = [
        r'\b(decided|approved|resolved|concluded|agreed|ratified|adopted)\b',
        r'\b(decision|resolution|determination)\b'
    ]

    ACTION_PATTERNS = [
        r'\b(action item|todo|AI:|assign|assigned|owner|responsible|due|deadline)\b',
        r'\b(will|shall|must|need to|required to)\s+\w+',
    ]

    AGENDA_PATTERNS = [
        r'^(\d+\.?\s*)?agenda:?\s*(.+)$',
        r'^item\s+\d+:?\s*(.+)$',
        r'^topic:?\s*(.+)$'
    ]

    def __init__(self):
        self.motions: List[Motion] = []
        self.decisions: List[Decision] = []
        self.actions: List[Action] = []
        self.agenda: List[AgendaItem] = []

    def structure_transcript(
        self,
        transcript: Transcript_v1,
        original_file: str
    ) -> BoardMinutes_v1:
        """Convert a normalized transcript into structured board minutes."""

        self.motions = []
        self.decisions = []
        self.actions = []
        self.agenda = []

        for i, item in enumerate(transcript.items):
            text_lower = item.text.lower()

            if self._is_agenda_item(item.text):
                agenda_text = self._extract_agenda_text(item.text)
                if agenda_text:
                    self.agenda.append(AgendaItem(item=agenda_text))

            if self._is_motion(text_lower):
                motion = self._extract_motion(transcript.items, i)
                if motion:
                    self.motions.append(motion)

            if self._is_decision(text_lower):
                decision = self._extract_decision(item.text)
                if decision:
                    self.decisions.append(decision)

            if self._is_action(text_lower):
                action = self._extract_action(item.text, item.speaker)
                if action:
                    self.actions.append(action)

        return BoardMinutes_v1(
            title=transcript.metadata.title or "Board Meeting",
            date=transcript.metadata.date or "",
            attendees=transcript.metadata.attendees,
            absent=[],
            agenda=self.agenda,
            motions=self.motions,
            decisions=self.decisions,
            actions=self.actions,
            notes=self._generate_notes(transcript),
            source=Source(provider="txt", file=Path(original_file).name)
        )

    def _is_agenda_item(self, text: str) -> bool:
        """Check if text appears to be an agenda item."""
        for pattern in self.AGENDA_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _extract_agenda_text(self, text: str) -> Optional[str]:
        """Extract agenda item text."""
        for pattern in self.AGENDA_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1) if len(match.groups()) > 0 else text
        return text.strip()

    def _is_motion(self, text_lower: str) -> bool:
        """Check if text contains motion-related keywords."""
        for pattern in self.MOTION_PATTERNS:
            if re.search(pattern, text_lower):
                return True
        return False

    def _is_decision(self, text_lower: str) -> bool:
        """Check if text contains decision-related keywords."""
        for pattern in self.DECISION_PATTERNS:
            if re.search(pattern, text_lower):
                return True
        return False

    def _is_action(self, text_lower: str) -> bool:
        """Check if text contains action-related keywords."""
        for pattern in self.ACTION_PATTERNS:
            if re.search(pattern, text_lower):
                return True
        return False

    def _extract_motion(
        self,
        items: List,
        start_idx: int
    ) -> Optional[Motion]:
        """Extract motion details from transcript items."""

        motion_text = items[start_idx].text
        mover = items[start_idx].speaker
        seconder = None
        vote_result = "UNKNOWN"
        for_count = 0
        against_count = 0
        abstain_count = 0

        for i in range(start_idx + 1, min(start_idx + 10, len(items))):
            text_lower = items[i].text.lower()

            if 'second' in text_lower:
                seconder = items[i].speaker

            if re.search(r'approved|passed|carried', text_lower):
                vote_result = "PASSED"
            elif re.search(r'failed|defeated|rejected', text_lower):
                vote_result = "FAILED"

            vote_match = re.search(r'(\d+)\s*(for|in favor|yes)', text_lower)
            if vote_match:
                for_count = int(vote_match.group(1))

            against_match = re.search(r'(\d+)\s*(against|no|opposed)', text_lower)
            if against_match:
                against_count = int(against_match.group(1))

            abstain_match = re.search(r'(\d+)\s*(abstain|abstention)', text_lower)
            if abstain_match:
                abstain_count = int(abstain_match.group(1))

        return Motion(
            text=motion_text,
            movedBy=mover if mover != "Unknown" else None,
            secondedBy=seconder if seconder and seconder != "Unknown" else None,
            vote=Vote(
                **{"for": for_count},
                against=against_count,
                abstain=abstain_count,
                result=vote_result
            )
        )

    def _extract_decision(self, text: str) -> Optional[Decision]:
        """Extract decision from text."""
        return Decision(text=text.strip())

    def _extract_action(self, text: str, speaker: str) -> Optional[Action]:
        """Extract action item from text."""

        owner = speaker if speaker != "Unknown" else "TBD"

        owner_match = re.search(
            r'(assign|assigned to|owner:|responsible:)\s*([A-Za-z]+)',
            text,
            re.IGNORECASE
        )
        if owner_match:
            owner = owner_match.group(2)

        due = None
        due_match = re.search(
            r'(due|deadline|by|before)\s*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})',
            text,
            re.IGNORECASE
        )
        if due_match:
            due = due_match.group(2)

        action_text = re.sub(r'(action item:|todo:|AI:)', '', text, flags=re.IGNORECASE).strip()

        return Action(
            owner=owner,
            due=due,
            text=action_text
        )

    def _generate_notes(self, transcript: Transcript_v1) -> str:
        """Generate summary notes from transcript."""

        total_items = len(transcript.items)
        speakers = set(item.speaker for item in transcript.items if item.speaker != "Unknown")

        notes = f"Meeting transcript contained {total_items} speaking turns. "
        notes += f"Participants: {', '.join(sorted(speakers))}."

        return notes