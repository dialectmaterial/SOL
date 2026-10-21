"""Event-loop setup for UI behavior tests, without asyncio trace instrumentation."""
import asyncio
import os


class UIEventLoop:
    """Keep per-test loop isolation, but use the application's normal loop mode.

    IsolatedAsyncioTestCase enables asyncio debug tracing by default. UI frameworks
    create many short-lived tasks, so recording their creation stacks is costly
    in these tests. No UI assertion depends on debug tracing; task cancellation,
    async cleanup, exceptions and unittest's resource warnings remain enabled.
    Set PYTHONASYNCIODEBUG=1 to retain creation-stack diagnostics.
    This mixin deliberately does not replace IsolatedAsyncioTestCase.
    """

    async def asyncSetUp(self):
        await super().asyncSetUp()
        if not os.environ.get("PYTHONASYNCIODEBUG"):
            asyncio.get_running_loop().set_debug(False)
