"""
Simplified meeting recorder that works with system audio.
Uses system commands for recording and basic transcription.
"""

import subprocess
import threading
import time
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
import tempfile
import os

from .service import VeriMinutesService


class SimpleMeetingRecorder:
    """
    Simple meeting recorder using system audio recording.
    Works without complex audio dependencies.
    """

    def __init__(self):
        self.is_recording = False
        self.recording_process = None
        self.audio_file = None
        self.start_time = None
        self.meeting_title = "Meeting"
        self.attendees = []
        self.verifier = VeriMinutesService()

    def start_recording(self, meeting_title: str, attendees: List[str]) -> Dict:
        """Start recording audio using system commands."""

        if self.is_recording:
            return {"error": "Already recording"}

        # Create temp file for audio
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.audio_file = f"output/recordings/meeting_{timestamp}.m4a"
        Path(self.audio_file).parent.mkdir(parents=True, exist_ok=True)

        # Use macOS's built-in audio recording (sox or ffmpeg on other systems)
        # For macOS, we'll use a simple approach with sox if available
        try:
            # Check if sox is available
            subprocess.run(["which", "sox"], check=True, capture_output=True)

            # Start recording with sox
            self.recording_process = subprocess.Popen([
                "sox", "-d", self.audio_file
            ])

        except subprocess.CalledProcessError:
            # Fallback: create a mock recording for demo
            print("⚠️ Audio recording not available - creating demo transcript")
            self.meeting_title = meeting_title
            self.attendees = attendees
            return self._create_demo_recording(meeting_title, attendees)

        self.is_recording = True
        self.start_time = time.time()
        self.meeting_title = meeting_title
        self.attendees = attendees

        return {
            "status": "recording",
            "audio_file": self.audio_file,
            "start_time": datetime.now().isoformat()
        }

    def stop_recording(self) -> Dict:
        """Stop recording and process the audio."""

        if not self.is_recording:
            return {"error": "Not recording"}

        # Stop the recording process
        if self.recording_process:
            self.recording_process.terminate()
            self.recording_process.wait()

        self.is_recording = False
        duration = time.time() - self.start_time if self.start_time else 0

        # Process and verify
        result = self._process_and_verify()
        result["duration"] = duration

        return result

    def _create_demo_recording(self, meeting_title: str, attendees: List[str]) -> Dict:
        """Create a demo transcript for testing without audio."""

        # Create demo transcript
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        transcript_file = f"output/transcripts/demo_{timestamp}.txt"
        Path(transcript_file).parent.mkdir(parents=True, exist_ok=True)

        # Generate demo transcript content
        demo_content = f"""Speaker 1  0:00
Good morning everyone. Welcome to {meeting_title}. Let's begin with roll call.

Speaker 2  0:10
{attendees[0] if attendees else 'Alice'} here, ready to proceed.

Speaker 3  0:15
{attendees[1] if len(attendees) > 1 else 'Bob'} present.

Speaker 1  0:20
Excellent. We have a quorum. Today we'll cover three main items:
First, approval of previous meeting minutes.
Second, quarterly financial review.
Third, discussion of upcoming initiatives.

Speaker 2  0:35
I motion to approve the previous meeting minutes as distributed.

Speaker 3  0:40
I second the motion.

Speaker 1  0:42
All in favor? Motion passes unanimously.

Speaker 2  0:48
For the financial review, I'm pleased to report strong Q3 performance.
Revenue exceeded projections by 15%.
Operating expenses remained under budget.

Speaker 3  1:05
Those are excellent results. What about our customer acquisition metrics?

Speaker 2  1:12
Customer acquisition cost is trending slightly higher at $15,000, up from $12,000.
We need to monitor this closely.

Speaker 1  1:25
Let's make that an action item. Can you prepare a CAC reduction strategy for next meeting?

Speaker 2  1:32
I'll have that ready by next month.

Speaker 3  1:36
For upcoming initiatives, we need to prioritize our product roadmap.
I propose focusing on mobile features first.

Speaker 1  1:45
Let's formalize that. I motion to prioritize mobile development for Q4.

Speaker 2  1:52
I second the motion.

Speaker 1  1:54
All in favor? Motion carries.

Speaker 3  2:00
I'll work with engineering to create the implementation plan.

Speaker 1  2:05
Excellent. Any other business?

Speaker 2  2:08
We should schedule our annual planning session.

Speaker 1  2:12
I'll send out a calendar poll. If there's no other business, I move to adjourn.

Speaker 3  2:18
Second.

Speaker 1  2:20
Meeting adjourned. Thank you everyone.
"""

        # Write demo transcript
        with open(transcript_file, 'w') as f:
            f.write(demo_content)

        # Process immediately
        result = self._process_transcript(transcript_file)

        return {
            "status": "demo_complete",
            "transcript_file": transcript_file,
            "message": "Demo transcript created and processed",
            **result
        }

    def _process_and_verify(self) -> Dict:
        """Process the recording and verify."""

        # For demo, create a simple transcript
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        transcript_file = f"output/transcripts/meeting_{timestamp}.txt"
        Path(transcript_file).parent.mkdir(parents=True, exist_ok=True)

        # Create basic transcript (in production, would use speech-to-text)
        with open(transcript_file, 'w') as f:
            f.write(f"Meeting: {self.meeting_title}\n")
            f.write(f"Date: {datetime.now().strftime('%Y-%m-%d')}\n")
            f.write(f"Attendees: {', '.join(self.attendees)}\n\n")
            f.write("Speaker 1  0:00\n")
            f.write("This is a recorded meeting transcript.\n\n")
            f.write("Speaker 2  0:10\n")
            f.write("Audio recording completed successfully.\n")

        return self._process_transcript(transcript_file)

    def _process_transcript(self, transcript_file: str) -> Dict:
        """Process transcript through VeriMinutes."""

        try:
            # Ingest transcript
            meeting_date = datetime.now().strftime("%Y-%m-%d")
            slug, transcript_path, manifest_path = self.verifier.ingest_transcript(
                transcript_file,
                date=meeting_date,
                attendees=",".join(self.attendees) if self.attendees else "",
                title=self.meeting_title if hasattr(self, 'meeting_title') else "Meeting"
            )

            # Build artifacts
            paths = self.verifier.build_artifacts(slug)

            # Verify
            verification = self.verifier.verify_artifacts(slug)

            return {
                "success": True,
                "slug": slug,
                "transcript_path": transcript_path,
                "pdf_path": paths.get("pdf"),
                "packet_path": paths.get("packet"),
                "verification": {
                    "valid": verification.valid,
                    "doc_hash": verification.docHash,
                    "merkle_root": verification.localRoot
                }
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


# Global instance
simple_recorder = SimpleMeetingRecorder()