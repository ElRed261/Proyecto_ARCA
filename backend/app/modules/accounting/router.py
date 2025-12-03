from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def read_accounting_root():
    return {"module": "accounting", "status": "active"}
