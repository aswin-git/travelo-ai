import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_health_check(client):
    """Basic health check to ensure the API is running."""
    # Assuming there is a root or health endpoint, or we just test 404 on a dummy route
    response = client.get("/non-existent-route")
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_chat_endpoint_missing_info():
    """Test the chat endpoint using httpx async client directly.
    We test a scenario that returns missing_info without hitting Gemini heavily.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/chat",
            json={"message": "I want to go somewhere"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "missing_info" in data

@pytest.mark.asyncio
async def test_chat_endpoint_simple_query():
    """Test the chat endpoint with a simple query to save API tokens."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/chat",
            json={
                "message": "What is the capital of India?",
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
