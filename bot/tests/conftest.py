import asyncio
import sys
from collections.abc import Mapping

import pytest
from pytest_asyncio.plugin import LoopFactory

if sys.platform == "win32":

    def pytest_asyncio_loop_factories(
        config: pytest.Config, item: pytest.Item
    ) -> Mapping[str, LoopFactory]:
        # psycopg async no funciona con el ProactorEventLoop por defecto de Windows.
        return {"selector": asyncio.SelectorEventLoop}
