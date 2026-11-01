from fastapi import APIRouter, Depends

from ..injector import get_admin_adapter
from ..adapters import AdminAdapter
from .validators import AdminLoginModel

admin_api_router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@admin_api_router.post(path="/login", tags=["admin"])
async def admin_login(credentials: AdminLoginModel, admin_adapter: AdminAdapter = Depends(get_admin_adapter)):
    return await admin_adapter.login(credentials.username, credentials.password)
