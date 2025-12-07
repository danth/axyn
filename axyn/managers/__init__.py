from __future__ import annotations
from abc import ABC
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from axyn.client import AxynClient


class Manager(ABC):
    def __init__(self, client: AxynClient):
        self._client = client

    async def setup_hook(self):
        """
        Do any asynchronous setup tasks.

        This is called once, before the client is logged in.
        """

