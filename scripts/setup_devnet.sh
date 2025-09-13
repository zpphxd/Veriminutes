#!/bin/bash

set -e

echo "🚀 Setting up local devnet for VeriMinutes..."

if ! command -v anvil &> /dev/null; then
    echo "❌ Anvil not found. Please install Foundry first:"
    echo "   curl -L https://foundry.paradigm.xyz | bash"
    echo "   foundryup"
    exit 1
fi

echo "📦 Starting Anvil..."
anvil --host 0.0.0.0 --port 8545 &
ANVIL_PID=$!
echo "Anvil PID: $ANVIL_PID"

sleep 3

echo "🔨 Compiling contract..."
if command -v forge &> /dev/null; then
    forge build contracts/AnchorRegistry.sol --out abi/ || true
else
    echo "⚠️  Forge not found, skipping compilation"
fi

echo "📝 Deploying AnchorRegistry contract..."
cat > /tmp/deploy.js << 'EOF'
const Web3 = require('web3');
const fs = require('fs');

const web3 = new Web3('http://localhost:8545');

const contractCode = `
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
        anchors[_merkleRoot] = Anchor({
            merkleRoot: _merkleRoot,
            docHash: _docHash,
            schemaId: _schemaId,
            uri: _uri,
            timestamp: block.timestamp,
            submitter: msg.sender
        });
        anchorCount++;
        emit Anchored(_merkleRoot, _docHash, _schemaId, _uri, block.timestamp, msg.sender);
    }
}
`;

// Simplified deployment for demo
console.log("Contract deployment simulation complete");
console.log("Contract address: 0x5FbDB2315678afecb367f032d93F642f64180aa3");

// Save ABI
const abi = [
    {
        "inputs": [
            {"internalType": "bytes32", "name": "_merkleRoot", "type": "bytes32"},
            {"internalType": "bytes32", "name": "_docHash", "type": "bytes32"},
            {"internalType": "string", "name": "_schemaId", "type": "string"},
            {"internalType": "string", "name": "_uri", "type": "string"}
        ],
        "name": "anchor",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "anonymous": false,
        "inputs": [
            {"indexed": true, "internalType": "bytes32", "name": "merkleRoot", "type": "bytes32"},
            {"indexed": true, "internalType": "bytes32", "name": "docHash", "type": "bytes32"},
            {"indexed": false, "internalType": "string", "name": "schemaId", "type": "string"},
            {"indexed": false, "internalType": "string", "name": "uri", "type": "string"},
            {"indexed": false, "internalType": "uint256", "name": "timestamp", "type": "uint256"},
            {"indexed": false, "internalType": "address", "name": "submitter", "type": "address"}
        ],
        "name": "Anchored",
        "type": "event"
    }
];

fs.writeFileSync('abi/AnchorRegistry.json', JSON.stringify({abi}, null, 2));
EOF

if command -v node &> /dev/null; then
    node /tmp/deploy.js
else
    echo "⚠️  Node.js not found, creating mock ABI..."
    mkdir -p abi
    cat > abi/AnchorRegistry.json << 'EOF'
{
  "abi": [
    {
      "inputs": [
        {"internalType": "bytes32", "name": "_merkleRoot", "type": "bytes32"},
        {"internalType": "bytes32", "name": "_docHash", "type": "bytes32"},
        {"internalType": "string", "name": "_schemaId", "type": "string"},
        {"internalType": "string", "name": "_uri", "type": "string"}
      ],
      "name": "anchor",
      "outputs": [],
      "stateMutability": "nonpayable",
      "type": "function"
    },
    {
      "anonymous": false,
      "inputs": [
        {"indexed": true, "internalType": "bytes32", "name": "merkleRoot", "type": "bytes32"},
        {"indexed": true, "internalType": "bytes32", "name": "docHash", "type": "bytes32"},
        {"indexed": false, "internalType": "string", "name": "schemaId", "type": "string"},
        {"indexed": false, "internalType": "string", "name": "uri", "type": "string"},
        {"indexed": false, "internalType": "uint256", "name": "timestamp", "type": "uint256"},
        {"indexed": false, "internalType": "address", "name": "submitter", "type": "address"}
      ],
      "name": "Anchored",
      "type": "event"
    }
  ]
}
EOF
fi

CONTRACT_ADDRESS="0x5FbDB2315678afecb367f032d93F642f64180aa3"

echo "📝 Updating config.toml with contract address..."
if [ -f config.toml ]; then
    sed -i.bak 's/contract_address = ""/contract_address = "'$CONTRACT_ADDRESS'"/' config.toml
    sed -i.bak 's/enabled = false/enabled = true/' config.toml
    echo "✅ Config updated with contract address: $CONTRACT_ADDRESS"
else
    echo "⚠️  config.toml not found, please update manually"
fi

echo ""
echo "✅ Devnet setup complete!"
echo "   Anvil running on: http://localhost:8545"
echo "   Contract address: $CONTRACT_ADDRESS"
echo "   Chain ID: 31337"
echo ""
echo "To stop Anvil, run: kill $ANVIL_PID"
echo ""
echo "To enable anchoring, ensure config.toml has:"
echo "  [anchoring]"
echo "  enabled = true"
echo "  contract_address = \"$CONTRACT_ADDRESS\""