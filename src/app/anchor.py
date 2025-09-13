import json
import toml
from pathlib import Path
from typing import Dict, Any, Optional
from web3 import Web3
from web3.middleware import geth_poa_middleware


class AnchorService:
    """Local blockchain anchoring service."""

    def __init__(self, config_path: str = "./config.toml"):
        self.config = toml.load(config_path)
        self.enabled = self.config.get("anchoring", {}).get("enabled", False)

        if self.enabled:
            self._setup_web3()
        else:
            self.w3 = None
            self.contract = None

    def _setup_web3(self):
        """Setup Web3 connection and contract."""

        rpc_url = self.config["anchoring"]["rpc_url"]
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)

        abi_path = Path("abi/AnchorRegistry.json")
        if abi_path.exists():
            abi_data = json.loads(abi_path.read_text())
            contract_address = self.config["anchoring"].get("contract_address")

            if contract_address and self.w3.is_address(contract_address):
                self.contract = self.w3.eth.contract(
                    address=contract_address,
                    abi=abi_data["abi"]
                )
            else:
                self.contract = None
        else:
            self.contract = None

    def is_enabled(self) -> bool:
        """Check if anchoring is enabled."""
        return self.enabled

    def anchor_document(
        self,
        merkle_root: str,
        doc_hash: str,
        schema_id: str,
        uri: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Anchor document hashes to local blockchain."""

        if not self.enabled or not self.contract:
            return None

        try:
            account = self.w3.eth.accounts[0]

            merkle_bytes = bytes.fromhex(merkle_root)
            doc_bytes = bytes.fromhex(doc_hash)

            tx_hash = self.contract.functions.anchor(
                merkle_bytes,
                doc_bytes,
                schema_id,
                uri
            ).transact({'from': account})

            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

            return {
                "txHash": receipt.transactionHash.hex(),
                "blockNumber": receipt.blockNumber,
                "contractAddress": self.contract.address,
                "chainId": self.w3.eth.chain_id
            }
        except Exception as e:
            print(f"Anchoring failed: {e}")
            return None

    def verify_anchor(
        self,
        merkle_root: str,
        tx_hash: str
    ) -> Optional[str]:
        """Verify anchor on blockchain."""

        if not self.enabled or not self.contract:
            return None

        try:
            tx_receipt = self.w3.eth.get_transaction_receipt(tx_hash)

            logs = self.contract.events.Anchored().process_receipt(tx_receipt)

            for log in logs:
                on_chain_root = log['args']['merkleRoot'].hex()
                if on_chain_root == merkle_root:
                    return on_chain_root

            return None
        except Exception:
            return None