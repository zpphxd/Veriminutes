import pytest
import tempfile
from pathlib import Path

from src.app.merkle import MerkleTree


class TestMerkleTree:
    def test_single_chunk_file(self):
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            f.write(b"Small file content")
            temp_path = f.name

        try:
            tree = MerkleTree()
            result = tree.build_from_file(temp_path)

            assert result["docPath"] == Path(temp_path).name
            assert result["chunkSize"] == 65536
            assert result["leafAlgo"] == "sha256"
            assert len(result["leaves"]) == 1
            assert result["merkleRoot"] != ""
        finally:
            Path(temp_path).unlink()

    def test_multi_chunk_file(self):
        chunk_size = 1024
        data = b"A" * (chunk_size * 3 + 500)

        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            f.write(data)
            temp_path = f.name

        try:
            tree = MerkleTree(chunk_size=chunk_size)
            result = tree.build_from_file(temp_path)

            assert len(result["leaves"]) == 4
            assert result["merkleRoot"] != ""
            assert result["chunkSize"] == chunk_size
        finally:
            Path(temp_path).unlink()

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            temp_path = f.name

        try:
            tree = MerkleTree()
            result = tree.build_from_file(temp_path)

            assert len(result["leaves"]) == 1
            assert result["merkleRoot"] != ""
        finally:
            Path(temp_path).unlink()

    def test_inclusion_proof(self):
        data = b"Test data for inclusion proof"

        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            f.write(data)
            temp_path = f.name

        try:
            tree = MerkleTree()
            result = tree.build_from_file(temp_path)

            leaf = result["leaves"][0]
            proof = result["inclusion"]
            root = result["merkleRoot"]

            assert tree.verify_inclusion(leaf, proof, root)
        finally:
            Path(temp_path).unlink()

    def test_verify_proof(self):
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            f.write(b"Content for verification")
            temp_path = f.name

        try:
            tree = MerkleTree()
            proof = tree.build_from_file(temp_path)

            assert MerkleTree.verify_proof(temp_path, proof)

            proof["merkleRoot"] = "0" * 64
            assert not MerkleTree.verify_proof(temp_path, proof)
        finally:
            Path(temp_path).unlink()

    def test_deterministic_hashing(self):
        data = b"Deterministic test data"

        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            f.write(data)
            temp_path = f.name

        try:
            tree1 = MerkleTree()
            result1 = tree1.build_from_file(temp_path)

            tree2 = MerkleTree()
            result2 = tree2.build_from_file(temp_path)

            assert result1["merkleRoot"] == result2["merkleRoot"]
            assert result1["leaves"] == result2["leaves"]
        finally:
            Path(temp_path).unlink()