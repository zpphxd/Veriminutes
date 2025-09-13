import hashlib
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import math


class MerkleTree:
    """Merkle tree implementation with 64KB chunking and inclusion proofs."""

    def __init__(self, chunk_size: int = 65536):
        self.chunk_size = chunk_size
        self.leaves: List[str] = []
        self.tree: List[List[str]] = []
        self.root: Optional[str] = None

    def build_from_file(self, file_path: str) -> Dict[str, Any]:
        """Build Merkle tree from file using chunking."""

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        data = path.read_bytes()
        chunks = self._chunk_data(data)
        self.leaves = [self._hash_chunk(chunk) for chunk in chunks]

        self._build_tree()

        inclusion = self._generate_inclusion_proof(0) if self.leaves else {}

        return {
            "docPath": path.name,
            "chunkSize": self.chunk_size,
            "leafAlgo": "sha256",
            "leaves": self.leaves,
            "merkleRoot": self.root or "",
            "inclusion": inclusion
        }

    def _chunk_data(self, data: bytes) -> List[bytes]:
        """Split data into chunks of specified size."""

        chunks = []
        for i in range(0, len(data), self.chunk_size):
            chunk = data[i:i + self.chunk_size]
            chunks.append(chunk)

        if not chunks:
            chunks = [b'']

        return chunks

    def _hash_chunk(self, chunk: bytes) -> str:
        """Hash a chunk using SHA-256."""
        return hashlib.sha256(chunk).hexdigest()

    def _hash_pair(self, left: str, right: str) -> str:
        """Hash two nodes together."""

        combined = bytes.fromhex(left) + bytes.fromhex(right)
        return hashlib.sha256(combined).hexdigest()

    def _build_tree(self):
        """Build the Merkle tree from leaves."""

        if not self.leaves:
            self.root = ""
            return

        if len(self.leaves) == 1:
            self.root = self.leaves[0]
            self.tree = [self.leaves]
            return

        self.tree = [self.leaves[:]]

        current_level = self.leaves[:]

        while len(current_level) > 1:
            next_level = []

            for i in range(0, len(current_level), 2):
                if i + 1 < len(current_level):
                    left = current_level[i]
                    right = current_level[i + 1]
                else:
                    left = current_level[i]
                    right = current_level[i]

                parent = self._hash_pair(left, right)
                next_level.append(parent)

            self.tree.append(next_level)
            current_level = next_level

        self.root = current_level[0] if current_level else ""

    def _generate_inclusion_proof(
        self,
        leaf_index: int
    ) -> Dict[str, Any]:
        """Generate inclusion proof for a leaf."""

        if leaf_index >= len(self.leaves):
            return {}

        siblings = []
        offsets = []
        current_index = leaf_index

        for level in range(len(self.tree) - 1):
            level_size = len(self.tree[level])

            if current_index % 2 == 0:
                sibling_index = current_index + 1
                offsets.append("right")
            else:
                sibling_index = current_index - 1
                offsets.append("left")

            if sibling_index < level_size:
                siblings.append(self.tree[level][sibling_index])
            else:
                siblings.append(self.tree[level][current_index])

            current_index = current_index // 2

        return {
            "leafIndex": leaf_index,
            "offsets": offsets,
            "siblings": siblings
        }

    def verify_inclusion(
        self,
        leaf: str,
        proof: Dict[str, Any],
        root: str
    ) -> bool:
        """Verify that a leaf is included in the tree."""

        try:
            current = leaf
            siblings = proof.get("siblings", [])
            offsets = proof.get("offsets", [])

            for sibling, offset in zip(siblings, offsets):
                if offset == "right":
                    current = self._hash_pair(current, sibling)
                else:
                    current = self._hash_pair(sibling, current)

            return current == root
        except Exception:
            return False

    @staticmethod
    def verify_proof(
        file_path: str,
        proof: Dict[str, Any]
    ) -> bool:
        """Verify a Merkle proof against a file."""

        try:
            tree = MerkleTree(chunk_size=proof.get("chunkSize", 65536))
            result = tree.build_from_file(file_path)

            return result["merkleRoot"] == proof["merkleRoot"]
        except Exception:
            return False