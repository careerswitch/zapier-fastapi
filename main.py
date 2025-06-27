from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from db import (
    init_db,
    insert_error_log,
    get_all_logs,
    update_log_status,
    clear_all_logs,
    get_logs_by_status,
)
from fastapi import Query
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from fastapi import Body
from typing import Any, Dict
import csv
import os
import io
import uvicorn


# Initialize FastAPI app
app = FastAPI(
    title="Zapier Error Dashboard API",
    description="API for managing and viewing Zapier error logs",
    version="1.0.0",
)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
init_db()

# Serve static files (for production)
app.mount("/static", StaticFiles(directory="static"), name="static")


# Models
class ErrorLogCreate(BaseModel):
    zap_name: str
    error_message: str
    explanation: Optional[str] = None


class LogStatusUpdate(BaseModel):
    status: str


# Error explanations
ERROR_EXPLANATIONS = {
    "not found": "Resource was renamed or deleted",
    "missing required field": "Check if field names changed",
    "auth expired": "Reauthorization needed",
    "rate limit": "API rate limit reached",
    "invalid data type": "Check field mappings",
}


def explain_error(error_msg: str) -> str:
    """Generate explanation based on error message patterns"""
    error_lower = error_msg.lower()
    for pattern, explanation in ERROR_EXPLANATIONS.items():
        if pattern in error_lower:
            return explanation
    return "No specific explanation available"


# API Endpoints
@app.post("/api/zapier_payload", status_code=201)
async def receive_zapier_payload(payload: Dict[str, Any] = Body(...)):
    """
    Zapier sends this payload from a webhook step.
    Expected fields:
    - zap_name
    - error_message
    - timestamp (optional)
    """
    try:
        zap_name = payload.get("zap_name")
        error_message = payload.get("error_message")
        timestamp = payload.get("timestamp")  # optional

        if not zap_name or not error_message:
            raise HTTPException(
                status_code=400, detail="Missing zap_name or error_message"
            )

        # Optionally override timestamp (if coming from Zapier)
        explanation = explain_error(error_message)
        log_id = insert_error_log(zap_name, error_message, explanation)

        if log_id == -1:
            return JSONResponse(
                status_code=409, content={"detail": "Duplicate log entry"}
            )

        return {"id": log_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/errors", status_code=201)
async def create_error_log(error: ErrorLogCreate):
    """Create a new error log entry"""
    explanation = error.explanation or explain_error(error.error_message)
    log_id = insert_error_log(
        zap_name=error.zap_name,
        error_message=error.error_message,
        explanation=explanation,
    )
    if log_id == -1:
        raise HTTPException(status_code=409, detail="Duplicate log entry")
    return {"id": log_id}


@app.get("/api/logs")
async def get_logs(status: Optional[str] = None):
    """Get all logs or filter by status"""
    try:
        if status:
            return get_logs_by_status(status)
        return get_all_logs()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/logs/{log_id}")
async def update_log(log_id: int, update: LogStatusUpdate):
    """Update log status"""
    try:
        success = update_log_status(log_id, update.status)
        if not success:
            raise HTTPException(status_code=404, detail="Log not found")
        return {"message": "Status updated"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/logs")
async def delete_all_logs():
    """Clear all logs"""
    count = clear_all_logs()
    return {"message": f"Deleted {count} logs"}


@app.get("/api/logs/export")
async def export_logs(status: Optional[str] = Query(None), format: str = "csv"):
    """
    Export logs in CSV format, optionally filtered by status
    """
    # Validate and get logs
    if status:
        logs = get_logs_by_status(status)
    else:
        logs = get_all_logs()

    if format == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=logs[0].keys() if logs else [])
        writer.writeheader()
        writer.writerows(logs)
        output.seek(0)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode()),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=zapier_logs_{timestamp}.csv"
            },
        )

    raise HTTPException(status_code=400, detail="Unsupported export format")


# Frontend serving (for production)
@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    try:
        with open("static/index.html", "r") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Frontend not found")


if __name__ == "__main__":
    import uvicorn
    import os

    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
