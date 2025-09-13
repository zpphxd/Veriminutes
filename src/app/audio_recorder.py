"""
Audio recording module with Voice Activity Detection (VAD).
Records meeting audio and detects when people are speaking.
"""

import pyaudio
import wave
import webrtcvad
import numpy as np
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, Tuple
import threading
import time


class AudioRecorder:
    """Records audio with voice activity detection."""

    def __init__(
        self,
        sample_rate: int = 16000,
        chunk_duration_ms: int = 30,
        padding_duration_ms: int = 1500,
        vad_aggressiveness: int = 3
    ):
        """
        Initialize audio recorder.

        Args:
            sample_rate: Audio sample rate (16000 for speech)
            chunk_duration_ms: Duration of audio chunks for VAD
            padding_duration_ms: Duration of padding around speech
            vad_aggressiveness: VAD aggressiveness (0-3, 3 is most aggressive)
        """
        self.sample_rate = sample_rate
        self.chunk_duration_ms = chunk_duration_ms
        self.padding_duration_ms = padding_duration_ms

        # Initialize VAD
        self.vad = webrtcvad.Vad(vad_aggressiveness)

        # Calculate chunk size
        self.chunk_size = int(sample_rate * chunk_duration_ms / 1000)
        self.chunk_bytes = self.chunk_size * 2  # 16-bit audio

        # Audio setup
        self.audio = pyaudio.PyAudio()
        self.stream = None

        # Recording state
        self.is_recording = False
        self.audio_buffer = []
        self.voiced_buffer = deque(maxlen=padding_duration_ms // chunk_duration_ms)

        # Callbacks
        self.on_speech_start: Optional[Callable] = None
        self.on_speech_end: Optional[Callable] = None
        self.on_audio_chunk: Optional[Callable] = None

        # Thread management
        self.recording_thread = None
        self.stop_event = threading.Event()

    def start_recording(self, output_path: Optional[str] = None) -> str:
        """
        Start recording audio.

        Args:
            output_path: Optional path to save the recording

        Returns:
            Path to the output file
        """
        if self.is_recording:
            raise RuntimeError("Already recording")

        # Generate output path if not provided
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"output/recordings/meeting_{timestamp}.wav"

        # Ensure output directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # Open audio stream
        self.stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size
        )

        # Start recording thread
        self.is_recording = True
        self.stop_event.clear()
        self.recording_thread = threading.Thread(
            target=self._recording_loop,
            args=(output_path,)
        )
        self.recording_thread.start()

        return output_path

    def stop_recording(self) -> Tuple[str, float]:
        """
        Stop recording.

        Returns:
            Tuple of (output_path, duration_seconds)
        """
        if not self.is_recording:
            raise RuntimeError("Not recording")

        # Signal stop
        self.is_recording = False
        self.stop_event.set()

        # Wait for thread to finish
        if self.recording_thread:
            self.recording_thread.join(timeout=5.0)

        # Close stream
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None

        # Calculate duration
        duration = len(self.audio_buffer) * self.chunk_duration_ms / 1000.0

        return self.current_output_path, duration

    def _recording_loop(self, output_path: str):
        """Main recording loop with VAD."""

        self.current_output_path = output_path
        self.audio_buffer = []

        # State for speech detection
        triggered = False
        voiced_frames = []

        print(f"Recording started: {output_path}")

        while not self.stop_event.is_set():
            try:
                # Read audio chunk
                chunk = self.stream.read(self.chunk_size, exception_on_overflow=False)

                # Check if speech is present
                is_speech = self.vad.is_speech(chunk, self.sample_rate)

                # Add to buffer
                self.audio_buffer.append(chunk)

                # Notify chunk callback
                if self.on_audio_chunk:
                    self.on_audio_chunk(chunk, is_speech)

                # Update voiced buffer
                self.voiced_buffer.append((chunk, is_speech))

                if not triggered:
                    # Check if we should start recording speech
                    num_voiced = len([f for f, speech in self.voiced_buffer if speech])
                    if num_voiced > 0.9 * self.voiced_buffer.maxlen:
                        triggered = True
                        print("Speech started")
                        if self.on_speech_start:
                            self.on_speech_start()

                        # Add buffered audio
                        for audio, _ in self.voiced_buffer:
                            voiced_frames.append(audio)
                else:
                    # We're recording speech
                    voiced_frames.append(chunk)

                    # Check if speech has ended
                    num_unvoiced = len([f for f, speech in self.voiced_buffer if not speech])
                    if num_unvoiced > 0.9 * self.voiced_buffer.maxlen:
                        triggered = False
                        print("Speech ended")
                        if self.on_speech_end:
                            self.on_speech_end(b''.join(voiced_frames))
                        voiced_frames = []

            except Exception as e:
                print(f"Recording error: {e}")
                break

        # Save complete recording
        self._save_recording(output_path, self.audio_buffer)
        print(f"Recording saved: {output_path}")

    def _save_recording(self, output_path: str, audio_buffer: list):
        """Save audio buffer to WAV file."""

        with wave.open(output_path, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(self.audio.get_sample_size(pyaudio.paInt16))
            wf.setframerate(self.sample_rate)
            wf.writeframes(b''.join(audio_buffer))

    def get_audio_level(self, chunk: bytes) -> float:
        """
        Get audio level (RMS) of a chunk.

        Args:
            chunk: Audio chunk bytes

        Returns:
            RMS level (0.0 to 1.0)
        """
        # Convert bytes to numpy array
        audio_data = np.frombuffer(chunk, dtype=np.int16)

        # Calculate RMS
        rms = np.sqrt(np.mean(audio_data.astype(np.float32) ** 2))

        # Normalize to 0-1 range
        max_value = 32768.0  # Max value for 16-bit audio
        normalized = rms / max_value

        return min(1.0, normalized)

    def close(self):
        """Clean up resources."""

        if self.is_recording:
            self.stop_recording()

        if self.audio:
            self.audio.terminate()