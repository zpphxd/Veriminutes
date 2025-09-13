from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class TranscriptItem(BaseModel):
    idx: int
    speaker: str
    text: str
    ts: Optional[str] = None


class TranscriptMetadata(BaseModel):
    date: Optional[str] = None
    title: Optional[str] = None
    attendees: List[str] = Field(default_factory=list)


class Transcript_v1(BaseModel):
    provider: str = "txt"
    items: List[TranscriptItem]
    metadata: TranscriptMetadata


class AgendaItem(BaseModel):
    item: str


class Vote(BaseModel):
    for_count: int = Field(alias="for", default=0)
    against: int = 0
    abstain: int = 0
    result: str = "UNKNOWN"  # PASSED, FAILED, UNKNOWN


class Motion(BaseModel):
    text: str
    movedBy: Optional[str] = None
    secondedBy: Optional[str] = None
    vote: Vote


class Decision(BaseModel):
    text: str


class Action(BaseModel):
    owner: str
    due: Optional[str] = None
    text: str


class Source(BaseModel):
    provider: str = "txt"
    file: str


class BoardMinutes_v1(BaseModel):
    title: str
    date: str
    attendees: List[str]
    absent: List[str] = Field(default_factory=list)
    agenda: List[AgendaItem] = Field(default_factory=list)
    motions: List[Motion] = Field(default_factory=list)
    decisions: List[Decision] = Field(default_factory=list)
    actions: List[Action] = Field(default_factory=list)
    notes: Optional[str] = None
    source: Source


class Signer(BaseModel):
    type: str = "ed25519"
    publicKey: str


class Credential(BaseModel):
    target: str
    sha256: str
    blake3: str
    size: int
    createdAt: str
    schema: str
    signer: Signer
    signature: str


class MerkleProof(BaseModel):
    docPath: str
    chunkSize: int = 65536
    leafAlgo: str = "sha256"
    leaves: List[str]
    merkleRoot: str
    inclusion: Dict[str, Any]


class AnchorReceipt(BaseModel):
    txHash: str
    blockNumber: int
    contractAddress: str
    chainId: int


class VerificationPacket(BaseModel):
    minutes: BoardMinutes_v1
    transcriptRef: str
    credential: Credential
    proof: MerkleProof
    anchorReceipt: Optional[AnchorReceipt] = None


class VerificationResult(BaseModel):
    valid: bool
    localRoot: str
    onChainRoot: Optional[str] = None
    docHash: str
    txHash: Optional[str] = None


class IngestRequest(BaseModel):
    path: str
    date: Optional[str] = None
    attendees: Optional[str] = None
    title: Optional[str] = None


class BuildRequest(BaseModel):
    slug: str


class IngestResponse(BaseModel):
    slug: str
    transcriptPath: str
    manifestPath: str


class BuildResponse(BaseModel):
    minutesPath: str
    credentialPath: str
    proofPath: str
    packetPath: str
    pdfPath: str
    anchorReceiptPath: Optional[str] = None