"""Async PostgREST client for database access."""

from typing import Optional
import httpx
from src.core.config import Settings, get_settings


class PostgRESTClient:
    """Async client for interacting with PostgREST API."""

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize with settings or use global settings."""
        self.settings = settings or get_settings()
        self.base_url = self.settings.postgrest_url.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

    def _get_headers(self) -> dict:
        """Get headers for PostgREST requests."""
        return {
            "apikey": self.settings.postgrest_api_key,
            "Content-Type": "application/json",
        }

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._get_headers(),
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def get(self, path: str) -> dict:
        """Perform GET request."""
        client = await self._get_client()
        response = await client.get(path)
        response.raise_for_status()
        return response.json()

    async def post(self, path: str, data: dict) -> dict:
        """Perform POST request."""
        client = await self._get_client()
        headers = {"Prefer": "return=representation"}
        response = await client.post(path, json=data, headers=headers)
        response.raise_for_status()

        # Handle empty response
        content = response.content
        if not content or len(content.strip()) == 0:
            return data  # Return the sent data if no response body

        result = response.json()
        # PostgREST returns a list with one item for POST
        if isinstance(result, list) and len(result) > 0:
            return result[0]
        return result

    async def patch(self, path: str, data: dict) -> dict:
        """Perform PATCH request."""
        client = await self._get_client()
        headers = {"Prefer": "return=representation"}
        response = await client.patch(path, json=data, headers=headers)
        response.raise_for_status()

        # Handle empty response
        content = response.content
        if not content or len(content.strip()) == 0:
            return data  # Return the sent data if no response body

        result = response.json()
        # PostgREST returns a list with one item for PATCH
        if isinstance(result, list) and len(result) > 0:
            return result[0]
        return result

    async def delete(self, path: str) -> dict:
        """Perform DELETE request."""
        client = await self._get_client()
        response = await client.delete(path)
        response.raise_for_status()
        return response.json()

    async def get_drones(self, filters: Optional[str] = None) -> dict:
        """Query all drones, optionally with filters."""
        path = "/drones"
        if filters:
            path += f"?{filters}"
        return await self.get(path)

    async def get_missions(self, filters: Optional[str] = None) -> dict:
        """Query all missions, optionally with filters."""
        path = "/missions"
        if filters:
            path += f"?{filters}"
        return await self.get(path)


async def get_postgrest_client() -> PostgRESTClient:
    """Dependency for FastAPI to get PostgREST client instance."""
    return PostgRESTClient()
