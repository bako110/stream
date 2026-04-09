from fastapi import APIRouter
router = APIRouter()

@router.get("/plans")
async def get_plans():
    return [
        {"plan": "basic",   "monthly": 5.99,  "annual": 59.99},
        {"plan": "premium", "monthly": 9.99,  "annual": 99.99},
        {"plan": "family",  "monthly": 14.99, "annual": 149.99},
    ]