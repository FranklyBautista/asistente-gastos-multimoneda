import asyncio
import sys
from collections.abc import Mapping

import pytest
from pytest_asyncio.plugin import LoopFactory


def pytest_asyncio_loop_factories(
    config: pytest.Config, item: pytest.Item
) -> Mapping[str, LoopFactory] | None:
    # psycopg async no funciona con el ProactorEventLoop por defecto de Windows.
    if sys.platform == "win32":
        return {"selector": asyncio.SelectorEventLoop}
    return None
