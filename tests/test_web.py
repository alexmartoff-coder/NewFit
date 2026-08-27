import pytest
import httpx
from src.web.app import app

@pytest.mark.asyncio
async def test_health_endpoint():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "app": "NewFit Web"}

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/welcome-alt",
        "/catalog",
        "/specialist",
        "/specialist/123",
        "/booking",
        "/booking/456",
        "/pro/schedule",
        "/pro/clients",
        "/pro/profile/edit",
        "/pro/schedule/generate",
        "/pro/unlock",
        "/client/favorites",
        "/client/bookings",
        "/client/profile",
        "/client/profile/view",
        "/admin",
        "/admin/subscriptions",
        "/admin/moderation",
        "/admin/devtools",
        "/screen/mobile_newfit_6",
    ],
)
async def test_web_routes(path: str):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(path)
        assert response.status_code == 200
        assert "html" in response.headers.get("content-type", "").lower()
