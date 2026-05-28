from fastapi import APIRouter
from app.data.wfp_loader import fetch_latest_prices

router = APIRouter(prefix="/prices", tags=["prices"])


@router.get("")
async def get_prices():
    """
    Returns the latest WFP food prices for Benin.
    Fetches live from HDX; falls back to empty list on error.
    """
    data = await fetch_latest_prices()
    return {
        "updated_at": data.get("updated_at"),
        "prices": data.get("prices", []),
    }
