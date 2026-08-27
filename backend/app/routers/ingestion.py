from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.config import BACKEND_ROOT, settings
from app.schemas import ParseBillResponse, ParseTransactionsResponse
from app.services.ocr import parse_bill
from app.services.transaction_parser import parse_transactions

router = APIRouter(prefix="/api/v1", tags=["ingestion"])

SAMPLES_DIR = BACKEND_ROOT / "data" / "samples"


async def _read_capped(file: UploadFile) -> bytes:
    data = await file.read()
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {settings.max_upload_mb} MB limit",
        )
    return data


@router.post("/parse-bill", response_model=ParseBillResponse)
async def parse_bill_route(file: UploadFile = File(...)) -> ParseBillResponse:
    data = await _read_capped(file)
    try:
        result = parse_bill(file.filename or "upload", data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ParseBillResponse(**result)


@router.post("/parse-transactions", response_model=ParseTransactionsResponse)
async def parse_transactions_route(file: UploadFile = File(...)) -> ParseTransactionsResponse:
    data = await _read_capped(file)
    try:
        result = parse_transactions(file.filename or "upload", data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ParseTransactionsResponse(**result)


@router.get("/samples")
def list_samples() -> dict:
    if not SAMPLES_DIR.exists():
        return {"files": []}
    return {
        "files": sorted(
            p.name for p in SAMPLES_DIR.iterdir() if p.is_file() and not p.name.startswith(".")
        )
    }


@router.get("/samples/{filename}")
def get_sample(filename: str) -> FileResponse:
    safe = (SAMPLES_DIR / filename).resolve()
    if SAMPLES_DIR.resolve() not in safe.parents or not safe.exists():
        raise HTTPException(status_code=404, detail="Sample file not found")
    return FileResponse(safe, filename=filename)
