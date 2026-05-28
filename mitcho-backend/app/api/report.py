import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, FileResponse

from app.api.auth import get_current_user
from app.reports.builder import build_report_data
from app.reports.pdf import generate_pdf
from db.models import User

router = APIRouter(prefix="/report", tags=["report"])

REPORTS_DIR = "reports"


@router.post("/generate")
async def generate_report(current_user: User = Depends(get_current_user)):
    """
    Generates the monthly report PDF on demand (authenticated users only).
    Runs the full pipeline: WFP prices + GDELT → RAG → PDF.
    Returns JSON with the download path.
    """
    try:
        data = await build_report_data()
        pdf_bytes = generate_pdf(data)

        os.makedirs(REPORTS_DIR, exist_ok=True)
        month_id = data["month_id"]
        filename = f"mitcho-rapport-{month_id}.pdf"
        path = os.path.join(REPORTS_DIR, filename)

        with open(path, "wb") as f:
            f.write(pdf_bytes)

        return {
            "status": "generated",
            "filename": filename,
            "month": data["month_label"],
            "generated_at": data["generated_at"],
            "download_url": f"/report/download/{filename}",
            "gdelt_articles": data.get("gdelt_articles_count", 0),
            "prices_count": len(data.get("prices", [])),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erreur de génération: {str(exc)}")


@router.get("/download/{filename}")
async def download_report(filename: str, current_user: User = Depends(get_current_user)):
    """Download a previously generated PDF report (authenticated users only)."""
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Nom de fichier invalide")

    path = os.path.join(REPORTS_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Rapport non trouvé. Générez-le d'abord.")

    return FileResponse(
        path=path,
        media_type="application/pdf",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/pdf/stream")
async def stream_report_pdf(current_user: User = Depends(get_current_user)):
    """
    Generates the PDF on the fly and streams it directly (no disk storage).
    Useful for immediate download without a prior /generate call.
    """
    try:
        data = await build_report_data()
        pdf_bytes = generate_pdf(data)
        month_id = data["month_id"]

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="mitcho-rapport-{month_id}.pdf"',
                "Content-Length": str(len(pdf_bytes)),
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erreur: {str(exc)}")
