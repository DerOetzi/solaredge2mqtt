from json import loads as json_loads
from typing import Callable, Optional

from requests import session
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import Timeout, HTTPError

from solaredge2mqtt.logging import logger


class HTTPClient:
    def __init__(self, service: str) -> None:
        self.session = session()
        self.service = service

    def _get(
        self,
        url: str,
        headers: Optional[dict[str, str]] = None,
        timeout: Optional[int] = 5,
        verify: Optional[bool] = True,
        login: Optional[Callable] = None,
    ) -> dict | None:
        result = None
        try:
            response = self.session.get(
                url, headers=headers, timeout=timeout, verify=verify
            )

            if response.status_code in (401, 403) and login:
                # Retry with a new login
                login()
                result = self._get(url, headers, timeout, verify)
            else:
                response.raise_for_status()
                result = json_loads(response.content.decode("utf-8"))
        except RequestsConnectionError as error:
            logger.error(f"Cannot connect to {self.service}: {error}")
        except Timeout as error:
            logger.error(f"Connection to {self.service} timed out: {error}")

        return result

    def _post(
        self,
        url: str,
        json: Optional[dict[str, str]] = None,
        data: Optional[dict[str, str]] = None,
        headers: Optional[dict[str, str]] = None,
        timeout: Optional[int] = 5,
        verify: Optional[bool] = True,
        expect_json: Optional[bool] = True,
        login: Optional[Callable] = None,
    ) -> dict | None:
        result = None
        try:
            response = self.session.post(
                url,
                headers=headers,
                json=json,
                data=data,
                timeout=timeout,
                verify=verify,
            )

            if response.status_code in (401, 403) and login:
                # Retry with a new login
                login()
                result = self._post(
                    url, json, data, headers, timeout, verify, expect_json
                )
            else:
                response.raise_for_status()
                if expect_json:
                    result = json_loads(response.content.decode("utf-8"))
                else:
                    result = response.content.decode("utf-8")
        except RequestsConnectionError as error:
            logger.error(f"Cannot connect to {self.service}: {error}")
        except Timeout as error:
            logger.error(f"Connection to {self.service} timed out: {error}")
        except HTTPError as error:
            logger.error(f"HTTP error from {self.service}: {error}")
            raise error

        return result
