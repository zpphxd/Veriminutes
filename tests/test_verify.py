import pytest
import tempfile
import json
from pathlib import Path

from src.app.service import VeriMinutesService
from src.app.schema import Transcript_v1, TranscriptItem, TranscriptMetadata


class TestVerification:
    def setup_method(self):
        self.service = VeriMinutesService()

    def test_end_to_end_verification(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Alice: Welcome to the Q3 board meeting.\n")
            f.write("Bob: Thank you for having me.\n")
            f.write("Alice: Motion to approve the Q2 minutes.\n")
            f.write("Bob: I second the motion.\n")
            f.write("Alice: All in favor? Motion passed.\n")
            f.write("Alice: Action item: Bob will prepare Q4 forecast by October 1.\n")
            temp_path = f.name

        try:
            slug, _, _ = self.service.ingest_transcript(
                temp_path,
                date="2025-09-12",
                attendees="Alice,Bob",
                title="Q3 Board"
            )

            paths = self.service.build_artifacts(slug)
            assert paths["minutes"]
            assert paths["minutes_cred"]
            assert paths["minutes_proof"]
            assert paths["packet"]
            assert paths["pdf"]

            result = self.service.verify_artifacts(slug)
            assert result.valid
            assert result.localRoot != ""
            assert result.docHash != ""

        finally:
            Path(temp_path).unlink()

    def test_tampered_file_detection(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Alice: Original meeting content.\n")
            temp_path = f.name

        try:
            slug, _, _ = self.service.ingest_transcript(
                temp_path,
                date="2025-09-12",
                title="Test Meeting"
            )

            paths = self.service.build_artifacts(slug)

            minutes_path = Path(paths["minutes"])
            minutes_data = json.loads(minutes_path.read_text())
            minutes_data["title"] = "TAMPERED TITLE"
            minutes_path.write_text(json.dumps(minutes_data))

            result = self.service.verify_artifacts(slug)
            assert not result.valid

        finally:
            Path(temp_path).unlink()

    def test_credential_signature_verification(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test: Content for signature verification.\n")
            temp_path = f.name

        try:
            slug, _, _ = self.service.ingest_transcript(temp_path)
            paths = self.service.build_artifacts(slug)

            cred_path = Path(paths["minutes_cred"])
            cred_data = json.loads(cred_path.read_text())

            cred_data["signature"] = "InvalidSignature=="
            cred_path.write_text(json.dumps(cred_data))

            result = self.service.verify_artifacts(slug)
            assert not result.valid

        finally:
            Path(temp_path).unlink()

    def test_merkle_proof_verification(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Speaker: Content for Merkle proof testing.\n")
            temp_path = f.name

        try:
            slug, _, _ = self.service.ingest_transcript(temp_path)
            paths = self.service.build_artifacts(slug)

            proof_path = Path(paths["minutes_proof"])
            proof_data = json.loads(proof_path.read_text())

            original_root = proof_data["merkleRoot"]
            proof_data["merkleRoot"] = "0" * 64
            proof_path.write_text(json.dumps(proof_data))

            result = self.service.verify_artifacts(slug)
            assert result.localRoot != proof_data["merkleRoot"]

        finally:
            Path(temp_path).unlink()