import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app

async def main():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        r = await client.post("/api/v1/auth/register", json={
            "email": "test-cookie@example.com",
            "password": "correct horse battery staple",
            "org_name": "Test Org",
            "org_type": "local",
            "country": "ET",
            "timezone": "Africa/Addis_Ababa",
        })
        print(f"Register status: {r.status_code}")
        print(f"Cookies in jar: {client.cookies}")
        
        # Now let's see what cookies are prepared for the next request
        req = client.build_request("GET", "/api/v1/auth/me")
        print(f"Headers for me: {req.headers}")
        
        me = await client.send(req)
        print(f"Me status: {me.status_code}")
        print(f"Me text: {me.text}")

asyncio.run(main())
