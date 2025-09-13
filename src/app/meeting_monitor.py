"""
Real-time meeting monitor with auto-verification.
Records, transcribes, identifies speakers, and auto-verifies when meeting ends.
"""

import asyncio
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Callable
import json
import numpy as np

from .audio_recorder import AudioRecorder
from .speaker_diarization import SpeakerDiarizer
from .transcriber import MeetingTranscriber
from .service import VeriMinutesService


class MeetingMonitor:
    """
    Complete meeting monitoring system.
    Records audio, identifies speakers, transcribes, and auto-verifies.
    """

    def __init__(
        self,
        meeting_title: str = "Meeting",
        attendees: List[str] = None,
        auto_verify: bool = True,
        model_size: str = "base"
    ):
        """
        Initialize meeting monitor.

        Args:
            meeting_title: Title of the meeting
            attendees: List of expected attendees
            auto_verify: Automatically verify when meeting ends
            model_size: Whisper model size for transcription
        """
        self.meeting_title = meeting_title
        self.attendees = attendees or []
        self.auto_verify = auto_verify
        self.meeting_date = datetime.now().strftime("%Y-%m-%d")

        # Initialize components
        self.recorder = AudioRecorder()
        self.diarizer = SpeakerDiarizer()
        self.transcriber = MeetingTranscriber(model_size=model_size)
        self.verifier = VeriMinutesService()

        # Meeting state
        self.is_monitoring = False
        self.start_time = None
        self.audio_path = None
        self.transcript_segments = []
        self.speaker_timeline = []

        # Real-time buffers
        self.audio_buffer = []
        self.speech_buffer = []

        # Callbacks
        self.on_speech_detected: Optional[Callable] = None
        self.on_transcription: Optional[Callable] = None
        self.on_speaker_identified: Optional[Callable] = None
        self.on_meeting_end: Optional[Callable] = None

        # Setup recorder callbacks
        self._setup_callbacks()

    def _setup_callbacks(self):
        """Setup audio recorder callbacks."""

        def on_speech_start():
            if self.on_speech_detected:
                self.on_speech_detected(True)

        def on_speech_end(audio_data: bytes):
            if self.on_speech_detected:
                self.on_speech_detected(False)

            # Process speech segment
            self._process_speech_segment(audio_data)

        self.recorder.on_speech_start = on_speech_start
        self.recorder.on_speech_end = on_speech_end

    def _process_speech_segment(self, audio_data: bytes):
        """Process a speech segment for speaker ID and transcription."""

        # Convert to numpy array
        audio_array = np.frombuffer(audio_data, dtype=np.int16)

        # Identify speaker
        speaker, confidence = self.diarizer.identify_speaker(audio_array)
        current_time = time.time() - self.start_time if self.start_time else 0

        if self.on_speaker_identified:
            self.on_speaker_identified(speaker, confidence)

        # Transcribe segment
        text = self.transcriber.transcribe_realtime(audio_array)

        if text:
            # Store segment
            segment = {
                "time": current_time,
                "speaker": speaker,
                "text": text,
                "confidence": confidence
            }
            self.transcript_segments.append(segment)

            if self.on_transcription:
                self.on_transcription(speaker, text)

            print(f"[{speaker}]: {text}")

    def start_meeting(self) -> str:
        """
        Start monitoring a meeting.

        Returns:
            Meeting ID/slug
        """
        if self.is_monitoring:
            raise RuntimeError("Already monitoring a meeting")

        print(f"\n{'='*60}")
        print(f"  MEETING STARTED: {self.meeting_title}")
        print(f"  Date: {self.meeting_date}")
        print(f"  Attendees: {', '.join(self.attendees)}")
        print(f"  Auto-verify: {self.auto_verify}")
        print(f"{'='*60}\n")

        # Reset state
        self.transcript_segments = []
        self.speaker_timeline = []
        self.start_time = time.time()
        self.is_monitoring = True

        # Start recording
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.audio_path = f"output/recordings/meeting_{timestamp}.wav"
        self.recorder.start_recording(self.audio_path)

        # Generate meeting slug
        self.meeting_slug = f"{self.meeting_date}-{self.meeting_title.lower().replace(' ', '-')}"

        return self.meeting_slug

    def end_meeting(self) -> Dict:
        """
        End the meeting and trigger verification.

        Returns:
            Dictionary with meeting results
        """
        if not self.is_monitoring:
            raise RuntimeError("No meeting in progress")

        print("\n🛑 Ending meeting...")

        # Stop recording
        audio_path, duration = self.recorder.stop_recording()
        self.is_monitoring = False

        print(f"✓ Recording saved: {audio_path} ({duration:.1f}s)")

        # Process full recording
        print("📝 Processing full transcript...")
        results = self._process_recording(audio_path)

        # Auto-verify if enabled
        if self.auto_verify:
            print("🔒 Auto-verifying meeting minutes...")
            verification = self._verify_meeting(results["transcript_path"])
            results["verification"] = verification

        # Callback
        if self.on_meeting_end:
            self.on_meeting_end(results)

        print(f"\n{'='*60}")
        print(f"  MEETING COMPLETE")
        print(f"  Duration: {duration:.1f}s")
        print(f"  Speakers: {len(results['speakers'])}")
        if self.auto_verify:
            print(f"  Verification: {'✅ PASSED' if results['verification']['valid'] else '❌ FAILED'}")
        print(f"{'='*60}\n")

        return results

    def _process_recording(self, audio_path: str) -> Dict:
        """Process the full recording with speaker diarization and transcription."""

        # Full transcription with better accuracy
        print("  - Transcribing audio...")
        segments = self.transcriber.transcribe_audio(audio_path)

        # Get speaker statistics
        speaker_stats = self.diarizer.get_speaker_statistics()

        # Export transcript in Otter format
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        transcript_path = f"output/transcripts/meeting_{timestamp}.txt"
        self.transcriber.export_transcript(transcript_path, format="txt")

        print(f"  - Transcript saved: {transcript_path}")

        return {
            "audio_path": audio_path,
            "transcript_path": transcript_path,
            "segments": [seg.to_dict() for seg in segments],
            "speakers": speaker_stats,
            "meeting_slug": self.meeting_slug
        }

    def _verify_meeting(self, transcript_path: str) -> Dict:
        """Run VeriMinutes verification on the transcript."""

        try:
            # Ingest transcript
            slug, _, _ = self.verifier.ingest_transcript(
                transcript_path,
                date=self.meeting_date,
                attendees=",".join(self.attendees),
                title=self.meeting_title
            )

            # Build artifacts
            paths = self.verifier.build_artifacts(slug)

            # Verify
            result = self.verifier.verify_artifacts(slug)

            return {
                "valid": result.valid,
                "slug": slug,
                "pdf_path": paths.get("pdf"),
                "packet_path": paths.get("packet"),
                "doc_hash": result.docHash,
                "merkle_root": result.localRoot
            }

        except Exception as e:
            print(f"  ❌ Verification error: {e}")
            return {"valid": False, "error": str(e)}

    def enroll_speaker(self, name: str, audio_samples: List[np.ndarray]):
        """
        Enroll a speaker for voice identification.

        Args:
            name: Speaker's name
            audio_samples: List of audio samples for training
        """
        profile = self.diarizer.enroll_speaker(name, audio_samples)
        print(f"✓ Enrolled speaker: {name} (ID: {profile.id})")
        return profile

    def get_meeting_status(self) -> Dict:
        """Get current meeting status."""

        if not self.is_monitoring:
            return {"status": "idle"}

        elapsed = time.time() - self.start_time if self.start_time else 0

        return {
            "status": "recording",
            "title": self.meeting_title,
            "elapsed_time": elapsed,
            "segments_count": len(self.transcript_segments),
            "speakers": list(set(s["speaker"] for s in self.transcript_segments))
        }

    def pause_meeting(self):
        """Pause the meeting recording."""
        if self.is_monitoring:
            # Implementation for pause
            pass

    def resume_meeting(self):
        """Resume the meeting recording."""
        if self.is_monitoring:
            # Implementation for resume
            pass


class MeetingSimulator:
    """Simulate a meeting for testing."""

    @staticmethod
    def simulate_meeting():
        """Simulate a meeting with fake audio."""

        print("🎭 Starting meeting simulation...")

        monitor = MeetingMonitor(
            meeting_title="Demo Board Meeting",
            attendees=["Alice", "Bob", "Carol"],
            auto_verify=True,
            model_size="tiny"  # Use tiny model for speed
        )

        # Start meeting
        meeting_id = monitor.start_meeting()

        # Simulate some speech segments
        sample_segments = [
            ("Alice", "Welcome everyone to today's board meeting."),
            ("Bob", "Thank you for having me. I'm excited to discuss Q3 results."),
            ("Carol", "Let's start with the financial review."),
            ("Alice", "I motion to approve the Q2 minutes."),
            ("Bob", "I second the motion."),
            ("Alice", "All in favor? Motion passes."),
        ]

        print("\n📢 Simulating speech...")
        for speaker, text in sample_segments:
            print(f"  [{speaker}]: {text}")
            time.sleep(1)  # Simulate time passing

        # End meeting
        print("\n")
        results = monitor.end_meeting()

        return results


if __name__ == "__main__":
    # Run simulation
    results = MeetingSimulator.simulate_meeting()
    print(f"\nSimulation results: {json.dumps(results, indent=2)}")