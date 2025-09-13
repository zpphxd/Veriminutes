// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract AnchorRegistry {
    struct Anchor {
        bytes32 merkleRoot;
        bytes32 docHash;
        string schemaId;
        string uri;
        uint256 timestamp;
        address submitter;
    }

    mapping(bytes32 => Anchor) public anchors;
    uint256 public anchorCount;

    event Anchored(
        bytes32 indexed merkleRoot,
        bytes32 indexed docHash,
        string schemaId,
        string uri,
        uint256 timestamp,
        address submitter
    );

    function anchor(
        bytes32 _merkleRoot,
        bytes32 _docHash,
        string memory _schemaId,
        string memory _uri
    ) public {
        require(_merkleRoot != bytes32(0), "Invalid merkle root");
        require(_docHash != bytes32(0), "Invalid doc hash");

        anchors[_merkleRoot] = Anchor({
            merkleRoot: _merkleRoot,
            docHash: _docHash,
            schemaId: _schemaId,
            uri: _uri,
            timestamp: block.timestamp,
            submitter: msg.sender
        });

        anchorCount++;

        emit Anchored(
            _merkleRoot,
            _docHash,
            _schemaId,
            _uri,
            block.timestamp,
            msg.sender
        );
    }

    function getAnchor(bytes32 _merkleRoot) public view returns (
        bytes32 docHash,
        string memory schemaId,
        string memory uri,
        uint256 timestamp,
        address submitter
    ) {
        Anchor memory a = anchors[_merkleRoot];
        return (a.docHash, a.schemaId, a.uri, a.timestamp, a.submitter);
    }

    function verifyAnchor(bytes32 _merkleRoot, bytes32 _docHash) public view returns (bool) {
        return anchors[_merkleRoot].docHash == _docHash;
    }
}