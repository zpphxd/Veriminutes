import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from .parse_txt import TxtParser
from .structure import MinutesStructurer
from .hashing import HashingService
from .merkle import MerkleTree
from .storage import StorageService
from .pdfgen import PDFGenerator
from .anchor import AnchorService
from .schema import (
    Transcript_v1, BoardMinutes_v1, VerificationPacket,
    VerificationResult
)


class VeriMinutesService:
    """Main orchestration service for VeriMinutes pipeline."""

    def __init__(self):
        self.parser = TxtParser()
        self.structurer = MinutesStructurer()
        self.hasher = HashingService()
        self.storage = StorageService()
        self.pdf_gen = PDFGenerator()
        self.anchor = AnchorService()

    def ingest_transcript(
        self,
        file_path: str,
        date: Optional[str] = None,
        attendees: Optional[str] = None,
        title: Optional[str] = None
    ) -> Tuple[str, str, str]:
        """Ingest TXT transcript and normalize to JSON."""

        attendees_list = attendees.split(',') if attendees else []
        attendees_list = [a.strip() for a in attendees_list]

        transcript = self.parser.parse_file(
            file_path,
            date=date,
            title=title,
            attendees=attendees_list
        )

        slug = self.storage.create_slug(date, title)

        transcript_path = self.storage.store_artifact(
            slug,
            "transcript.normalized.json",
            transcript.model_dump()
        )

        manifest_path = self.storage.update_manifest(
            slug,
            "transcript",
            "transcript.normalized.json",
            {"schema": "Transcript_v1"}
        )

        return slug, transcript_path, manifest_path

    def build_artifacts(self, slug: str) -> Dict[str, str]:
        """Build all artifacts for a session."""

        paths = {}

        transcript_data = self.storage.read_artifact(slug, "transcript.normalized.json")
        transcript = Transcript_v1(**transcript_data)

        original_file = self.storage.get_manifest(slug)["artifacts"][0].get("path", "unknown.txt")

        minutes = self.structurer.structure_transcript(transcript, original_file)
        paths["minutes"] = self.storage.store_artifact(
            slug,
            "minutes.json",
            minutes.model_dump()
        )

        transcript_cred = self.hasher.create_credential(
            self.storage.get_session_dir(slug) / "transcript.normalized.json",
            "Transcript_v1"
        )
        paths["transcript_cred"] = self.storage.store_artifact(
            slug,
            "transcript.cred.json",
            transcript_cred
        )

        minutes_cred = self.hasher.create_credential(
            paths["minutes"],
            "BoardMinutes_v1"
        )
        paths["minutes_cred"] = self.storage.store_artifact(
            slug,
            "minutes.cred.json",
            minutes_cred
        )

        transcript_content = Path(self.storage.get_session_dir(slug) / "transcript.normalized.json").read_bytes()
        self.storage.store_in_cas(slug, "sha256", transcript_cred["sha256"], transcript_content)
        self.storage.store_in_cas(slug, "blake3", transcript_cred["blake3"], transcript_content)

        minutes_content = Path(paths["minutes"]).read_bytes()
        self.storage.store_in_cas(slug, "sha256", minutes_cred["sha256"], minutes_content)
        self.storage.store_in_cas(slug, "blake3", minutes_cred["blake3"], minutes_content)

        tree = MerkleTree()
        transcript_proof = tree.build_from_file(
            self.storage.get_session_dir(slug) / "transcript.normalized.json"
        )
        paths["transcript_proof"] = self.storage.store_artifact(
            slug,
            "transcript.proof.json",
            transcript_proof
        )

        tree = MerkleTree()
        minutes_proof = tree.build_from_file(paths["minutes"])
        paths["minutes_proof"] = self.storage.store_artifact(
            slug,
            "minutes.proof.json",
            minutes_proof
        )

        anchor_receipt = None
        if self.anchor.is_enabled():
            receipt = self.anchor.anchor_document(
                minutes_proof["merkleRoot"],
                minutes_cred["sha256"],
                "BoardMinutes_v1",
                f"veriminutes://{slug}/minutes.json"
            )
            if receipt:
                anchor_receipt = receipt
                paths["anchor_receipt"] = self.storage.store_artifact(
                    slug,
                    "anchor_receipt.json",
                    receipt
                )

        packet = VerificationPacket(
            minutes=minutes,
            transcriptRef="transcript.normalized.json",
            credential=minutes_cred,
            proof=minutes_proof,
            anchorReceipt=anchor_receipt
        )
        paths["packet"] = self.storage.store_artifact(
            slug,
            "minutes.packet.json",
            packet.model_dump()
        )

        pdf_path = self.storage.get_session_dir(slug) / "minutes.pdf"
        self.pdf_gen.generate_pdf(
            minutes,
            str(pdf_path),
            credential=minutes_cred,
            proof=minutes_proof,
            anchor_receipt=anchor_receipt
        )
        paths["pdf"] = str(pdf_path)

        for artifact_type, path in paths.items():
            if path:
                self.storage.update_manifest(
                    slug,
                    artifact_type,
                    Path(path).name
                )

        return paths

    def verify_artifacts(self, slug: str) -> VerificationResult:
        """Verify all artifacts for a session."""

        try:
            session_dir = self.storage.get_session_dir(slug)

            minutes_cred = self.storage.read_artifact(slug, "minutes.cred.json")
            minutes_proof = self.storage.read_artifact(slug, "minutes.proof.json")

            minutes_path = session_dir / "minutes.json"
            cred_valid = self.hasher.verify_credential(minutes_cred, str(minutes_path))

            tree = MerkleTree()
            proof_valid = tree.verify_proof(str(minutes_path), minutes_proof)

            on_chain_root = None
            tx_hash = None

            if self.anchor.is_enabled():
                try:
                    receipt = self.storage.read_artifact(slug, "anchor_receipt.json")
                    tx_hash = receipt.get("txHash")
                    on_chain_root = self.anchor.verify_anchor(
                        minutes_proof["merkleRoot"],
                        tx_hash
                    )
                except:
                    pass

            return VerificationResult(
                valid=cred_valid and proof_valid,
                localRoot=minutes_proof["merkleRoot"],
                onChainRoot=on_chain_root,
                docHash=minutes_cred["sha256"],
                txHash=tx_hash
            )
        except Exception as e:
            return VerificationResult(
                valid=False,
                localRoot="",
                onChainRoot=None,
                docHash="",
                txHash=None
            )