import asyncio
from typing import Callable

import aiohttp

from solaredge2mqtt.core.logging import logger


class HTTPClientAsync:
    def __init__(self, service: str) -> None:
        self.service = service
        self.session: aiohttp.ClientSession | None = None

    def init(self) -> None:
        if not self.session:
            cookie_jar = aiohttp.CookieJar(unsafe=True)
            self.session = aiohttp.ClientSession(cookie_jar=cookie_jar)

    async def _handle_response(
        self, response: aiohttp.ClientResponse, expect_json: bool = True
    ) -> dict | str | None:
        try:
            response.raise_for_status()
            return await response.json() if expect_json else await response.text()
        except aiohttp.ClientResponseError as error:
            logger.warning(f"HTTP error from {self.service}: {error}")
            raise error

    async def _get(
        self,
        url: str,
        params: dict[str, str | int | float] | None = None,
        headers: dict[str, str] | None = None,
        verify: bool = True,
        login: Callable | None = None,
    ) -> dict | None:
        try:
            self.init()

            async with self.session.get(
                url, params=params, headers=headers, ssl=verify
            ) as response:
                if response.status in (401, 403) and login:
                    await login()
                    return await self._get(url, params, headers, verify, None)
                return await self._handle_response(response)
        except (aiohttp.ClientConnectionError, asyncio.TimeoutError) as error:
            logger.warning(f"Connection issue with {self.service}: {error}")
            return None

    async def _post(
        self,
        url: str,
        json: dict[str, str] | None = None,
        data: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        verify: bool = True,
        expect_json: bool = True,
        login: Callable | None = None,
    ) -> dict | str | None:
        try:
            self.init()

            async with self.session.post(
                url, json=json, data=data, headers=headers, ssl=verify
            ) as response:
                if response.status in (401, 403) and login:
                    await login()
                    return await self._post(
                        url, json, data, headers, verify, expect_json, None
                    )

                return await self._handle_response(response, expect_json)
        except (aiohttp.ClientConnectionError, asyncio.TimeoutError) as error:
            logger.warning(f"Connection issue with {self.service}: {error}")
            return None

    async def close(self) -> None:
        if self.session:
            await self.session.close()
            self.session = None

    def cookie_exists(self, cookie_name: str) -> bool:
        return self.get_cookie(cookie_name) is not None

    def get_cookie(self, cookie_name: str) -> str | None:
        value: str | None = None
        if self.session:
            for cookie in self.session.cookie_jar:
                if cookie.key == cookie_name:
                    value = cookie.value
                    break

        return value
