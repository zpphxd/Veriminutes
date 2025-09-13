from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import tempfile
import shutil
from typing import Optional

from .service import VeriMinutesService
from .schema import (
    IngestRequest, IngestResponse,
    BuildRequest, BuildResponse,
    VerificationResult
)


app = FastAPI(
    title="VeriMinutes API",
    description="Local-first verifiable minutes system",
    version="0.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

service = VeriMinutesService()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/ingest", response_model=IngestResponse)
async def ingest_transcript(request: IngestRequest):
    """Ingest a TXT transcript and normalize to JSON."""

    file_path = Path(request.path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {request.path}")

    try:
        slug, transcript_path, manifest_path = service.ingest_transcript(
            str(file_path),
            date=request.date,
            attendees=request.attendees,
            title=request.title
        )

        return IngestResponse(
            slug=slug,
            transcriptPath=transcript_path,
            manifestPath=manifest_path
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/build", response_model=BuildResponse)
async def build_artifacts(request: BuildRequest):
    """Build credentials, proofs, and PDF for a session."""

    try:
        paths = service.build_artifacts(request.slug)

        return BuildResponse(
            minutesPath=paths.get("minutes", ""),
            credentialPath=paths.get("minutes_cred", ""),
            proofPath=paths.get("minutes_proof", ""),
            packetPath=paths.get("packet", ""),
            pdfPath=paths.get("pdf", ""),
            anchorReceiptPath=paths.get("anchor_receipt")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/verify", response_model=VerificationResult)
async def verify_artifacts(slug: str):
    """Verify artifacts for a session."""

    if not slug:
        raise HTTPException(status_code=400, detail="Slug parameter is required")

    try:
        result = service.verify_artifacts(slug)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sessions")
async def list_sessions():
    """List all available sessions."""

    sessions = service.storage.list_sessions()
    return {"sessions": sessions}


@app.post("/upload")
async def upload_transcript(
    file: UploadFile = File(...),
    title: str = Form(...),
    date: str = Form(...),
    attendees: Optional[str] = Form(None)
):
    """Upload and process a transcript file."""

    if not file.filename.endswith('.txt'):
        raise HTTPException(status_code=400, detail="Only .txt files are supported")

    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp:
            content = await file.read()
            tmp.write(content.decode('utf-8'))
            temp_path = tmp.name

        # Process the transcript
        slug, transcript_path, manifest_path = service.ingest_transcript(
            temp_path,
            date=date,
            attendees=attendees,
            title=title
        )

        # Clean up temp file
        Path(temp_path).unlink()

        return {
            "slug": slug,
            "transcriptPath": transcript_path,
            "manifestPath": manifest_path
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/download/{slug}/{artifact_type}")
async def download_artifact(slug: str, artifact_type: str):
    """Download a specific artifact."""

    session_dir = service.storage.get_session_dir(slug)

    file_mappings = {
        "pdf": "minutes.pdf",
        "packet": "minutes.packet.json",
        "proof": "minutes.proof.json",
        "transcript": "transcript.normalized.json",
        "minutes": "minutes.json",
        "credential": "minutes.cred.json"
    }

    if artifact_type not in file_mappings:
        raise HTTPException(status_code=404, detail="Invalid artifact type")

    file_path = session_dir / file_mappings[artifact_type]

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Artifact not found")

    media_type = "application/pdf" if artifact_type == "pdf" else "application/json"

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=file_path.name
    )


# Mount static files for the web interface
static_dir = Path(__file__).parent.parent.parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")