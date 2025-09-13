"""
Speech-to-text transcription module using Whisper.
Converts audio to text with timestamps and speaker labels.
"""

import whisper
import numpy as np
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import json
import wave
import time
from datetime import datetime, timedelta


class TranscriptionSegment:
    """Represents a transcribed segment with speaker info."""

    def __init__(
        self,
        text: str,
        start_time: float,
        end_time: float,
        speaker: str = "Unknown",
        confidence: float = 0.0
    ):
        self.text = text
        self.start_time = start_time
        self.end_time = end_time
        self.speaker = speaker
        self.confidence = confidence

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "text": self.text,
            "start": self.start_time,
            "end": self.end_time,
            "speaker": self.speaker,
            "confidence": self.confidence,
            "duration": self.end_time - self.start_time
        }


class MeetingTranscriber:
    """
    Transcribes meeting audio to text with speaker labels.
    Uses Whisper for transcription and integrates with speaker diarization.
    """

    def __init__(
        self,
        model_size: str = "base",
        language: str = "en",
        device: str = "cpu"
    ):
        """
        Initialize transcriber.

        Args:
            model_size: Whisper model size (tiny, base, small, medium, large)
            language: Language code for transcription
            device: Device to run model on (cpu, cuda)
        """
        self.model_size = model_size
        self.language = language
        self.device = device

        # Load Whisper model
        print(f"Loading Whisper model: {model_size}")
        self.model = whisper.load_model(model_size, device=device)

        # Transcription cache
        self.segments: List[TranscriptionSegment] = []

    def transcribe_audio(
        self,
        audio_path: str,
        speaker_segments: Optional[List[Tuple[float, float, str]]] = None
    ) -> List[TranscriptionSegment]:
        """
        Transcribe audio file with optional speaker diarization.

        Args:
            audio_path: Path to audio file
            speaker_segments: Optional list of (start, end, speaker) tuples

        Returns:
            List of transcription segments
        """
        start_time = time.time()
        print(f"Transcribing: {audio_path}")

        # Transcribe with Whisper
        result = self.model.transcribe(
            audio_path,
            language=self.language,
            word_timestamps=True,
            verbose=False
        )

        # Process segments
        self.segments = []

        for segment in result["segments"]:
            # Extract text and timing
            text = segment["text"].strip()
            start = segment["start"]
            end = segment["end"]

            # Find speaker for this segment
            speaker = self._find_speaker(start, end, speaker_segments)

            # Create transcription segment
            trans_segment = TranscriptionSegment(
                text=text,
                start_time=start,
                end_time=end,
                speaker=speaker,
                confidence=segment.get("avg_logprob", 0.0)
            )

            self.segments.append(trans_segment)

        elapsed = time.time() - start_time
        print(f"Transcription complete: {len(self.segments)} segments in {elapsed:.1f}s")

        return self.segments

    def transcribe_realtime(
        self,
        audio_chunk: np.ndarray,
        sample_rate: int = 16000
    ) -> Optional[str]:
        """
        Transcribe audio chunk in real-time.

        Args:
            audio_chunk: Audio chunk as numpy array
            sample_rate: Sample rate of audio

        Returns:
            Transcribed text or None if no speech
        """
        # Ensure audio is float32 and normalized
        if audio_chunk.dtype != np.float32:
            audio_chunk = audio_chunk.astype(np.float32) / 32768.0

        # Pad if too short (Whisper needs at least 0.1s)
        min_samples = int(0.1 * sample_rate)
        if len(audio_chunk) < min_samples:
            audio_chunk = np.pad(audio_chunk, (0, min_samples - len(audio_chunk)))

        # Transcribe
        result = self.model.transcribe(
            audio_chunk,
            language=self.language,
            verbose=False,
            fp16=False
        )

        text = result["text"].strip()
        return text if text else None

    def _find_speaker(
        self,
        start: float,
        end: float,
        speaker_segments: Optional[List[Tuple[float, float, str]]]
    ) -> str:
        """Find speaker for a given time range."""

        if not speaker_segments:
            return "Unknown"

        # Find overlapping speaker segment
        for seg_start, seg_end, speaker in speaker_segments:
            # Check for overlap
            if seg_start <= start <= seg_end or seg_start <= end <= seg_end:
                return speaker

            # Check if segment is contained
            if start <= seg_start and end >= seg_end:
                return speaker

        return "Unknown"

    def merge_short_segments(
        self,
        min_duration: float = 1.0
    ) -> List[TranscriptionSegment]:
        """
        Merge short segments from the same speaker.

        Args:
            min_duration: Minimum duration for a segment

        Returns:
            Merged segments
        """
        if not self.segments:
            return []

        merged = []
        current = self.segments[0]

        for segment in self.segments[1:]:
            # Check if should merge
            if (segment.speaker == current.speaker and
                segment.start_time - current.end_time < 1.0 and
                current.end_time - current.start_time < min_duration):

                # Merge segments
                current = TranscriptionSegment(
                    text=current.text + " " + segment.text,
                    start_time=current.start_time,
                    end_time=segment.end_time,
                    speaker=current.speaker,
                    confidence=(current.confidence + segment.confidence) / 2
                )
            else:
                # Save current and start new
                merged.append(current)
                current = segment

        # Add last segment
        merged.append(current)

        return merged

    def export_transcript(
        self,
        output_path: str,
        format: str = "txt",
        include_timestamps: bool = True
    ) -> str:
        """
        Export transcript to file.

        Args:
            output_path: Output file path
            format: Export format (txt, json, srt)
            include_timestamps: Include timestamps in output

        Returns:
            Path to exported file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if format == "txt":
            self._export_txt(output_path, include_timestamps)
        elif format == "json":
            self._export_json(output_path)
        elif format == "srt":
            self._export_srt(output_path)
        else:
            raise ValueError(f"Unknown format: {format}")

        return str(output_path)

    def _export_txt(self, output_path: Path, include_timestamps: bool):
        """Export as plain text."""

        with open(output_path, 'w', encoding='utf-8') as f:
            for segment in self.segments:
                if include_timestamps:
                    timestamp = self._format_timestamp(segment.start_time)
                    f.write(f"{segment.speaker}  {timestamp}\n")
                else:
                    f.write(f"{segment.speaker}: ")

                f.write(f"{segment.text}\n\n")

    def _export_json(self, output_path: Path):
        """Export as JSON."""

        data = {
            "meeting_date": datetime.now().isoformat(),
            "model": self.model_size,
            "language": self.language,
            "segments": [seg.to_dict() for seg in self.segments]
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def _export_srt(self, output_path: Path):
        """Export as SRT subtitle file."""

        with open(output_path, 'w', encoding='utf-8') as f:
            for i, segment in enumerate(self.segments, 1):
                # Write index
                f.write(f"{i}\n")

                # Write timestamp
                start = self._format_srt_time(segment.start_time)
                end = self._format_srt_time(segment.end_time)
                f.write(f"{start} --> {end}\n")

                # Write text with speaker
                f.write(f"[{segment.speaker}] {segment.text}\n\n")

    def _format_timestamp(self, seconds: float) -> str:
        """Format seconds as MM:SS."""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}:{secs:02d}"

    def _format_srt_time(self, seconds: float) -> str:
        """Format seconds as HH:MM:SS,mmm for SRT."""
        td = timedelta(seconds=seconds)
        hours = td.seconds // 3600
        minutes = (td.seconds % 3600) // 60
        secs = td.seconds % 60
        millis = td.microseconds // 1000
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def get_summary_statistics(self) -> Dict:
        """Get summary statistics about the transcription."""

        if not self.segments:
            return {}

        # Calculate statistics
        total_duration = self.segments[-1].end_time if self.segments else 0
        total_words = sum(len(seg.text.split()) for seg in self.segments)

        # Speaker statistics
        speaker_stats = {}
        for segment in self.segments:
            if segment.speaker not in speaker_stats:
                speaker_stats[segment.speaker] = {
                    "segments": 0,
                    "duration": 0,
                    "words": 0
                }

            speaker_stats[segment.speaker]["segments"] += 1
            speaker_stats[segment.speaker]["duration"] += segment.end_time - segment.start_time
            speaker_stats[segment.speaker]["words"] += len(segment.text.split())

        return {
            "total_duration": total_duration,
            "total_segments": len(self.segments),
            "total_words": total_words,
            "avg_confidence": np.mean([s.confidence for s in self.segments]),
            "speakers": speaker_stats
        }