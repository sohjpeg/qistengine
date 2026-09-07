from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.config import BACKEND_ROOT, settings
from app.schemas import ParseBillResponse, ParseTransactionsResponse
from app.services.ocr import parse_bill
from app.services.transaction_parser import parse_transaction_files

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


MAX_TRANSACTION_FILES = 12


@router.post("/parse-transactions", response_model=ParseTransactionsResponse)
async def parse_transactions_route(
    files: list[UploadFile] = File(default=[]),
    file: UploadFile | None = File(default=None),
) -> ParseTransactionsResponse:
    """Parse one or more wallet statements into a single aggregated ledger.

    Several monthly exports are the normal shape of real wallet data, and
    cashflow volatility and income trend need more than one month to mean
    anything. `file` remains accepted so existing single-file callers keep
    working.
    """
    uploads = [f for f in files if f is not None]
    if file is not None:
        uploads.append(file)
    if not uploads:
        raise HTTPException(status_code=422, detail="Upload at least one transaction file")
    if len(uploads) > MAX_TRANSACTION_FILES:
        raise HTTPException(
            status_code=422,
            detail=f"At most {MAX_TRANSACTION_FILES} statement files at a time",
        )

    items: list[tuple[str, bytes]] = []
    total = 0
    for upload in uploads:
        data = await _read_capped(upload)
        total += len(data)
        if total > settings.max_upload_bytes * MAX_TRANSACTION_FILES:
            raise HTTPException(status_code=413, detail="Uploads exceed the combined size limit")
        items.append((upload.filename or "upload", data))

    try:
        result = parse_transaction_files(items)
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
