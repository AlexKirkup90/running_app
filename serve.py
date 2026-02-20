"""Serve the React build through the platform's preview channel.

Starts FastAPI (API backend) in a background thread, patches Streamlit's
Tornado server with an API proxy route, then launches Streamlit which
renders the React SPA via st.components.v1.html().

Run with:  python3 serve.py
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time

# ---------------------------------------------------------------------------
# 1. Start FastAPI in a background thread on port 8000
# ---------------------------------------------------------------------------

FASTAPI_PORT = 8000


def _start_api():
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres@localhost:5432/runseason",
    )
    import uvicorn

    from api.main import create_app

    app = create_app()
    uvicorn.run(app, host="127.0.0.1", port=FASTAPI_PORT, log_level="warning")


threading.Thread(target=_start_api, daemon=True).start()
time.sleep(2)

# ---------------------------------------------------------------------------
# 2. Monkey-patch Streamlit's server to proxy /api/* to FastAPI
# ---------------------------------------------------------------------------

import tornado.httpclient  # noqa: E402
import tornado.routing  # noqa: E402
import tornado.web  # noqa: E402

import streamlit.web.server.server as _st_server  # noqa: E402


class _ApiProxy(tornado.web.RequestHandler):
    """Forward /api/* requests to the FastAPI backend."""

    SUPPORTED_METHODS = ("GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS")

    def check_xsrf_cookie(self):
        pass  # API proxy does not need XSRF protection

    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods", "*")
        self.set_header("Access-Control-Allow-Headers", "*")

    async def options(self, *_a):
        self.set_status(204)

    async def get(self, *_a):
        await self._proxy()

    async def post(self, *_a):
        await self._proxy()

    async def put(self, *_a):
        await self._proxy()

    async def delete(self, *_a):
        await self._proxy()

    async def patch(self, *_a):
        await self._proxy()

    async def _proxy(self):
        url = f"http://127.0.0.1:{FASTAPI_PORT}{self.request.uri}"
        http = tornado.httpclient.AsyncHTTPClient()

        headers = {
            k: v
            for k, v in self.request.headers.items()
            if k.lower() not in ("host", "connection", "transfer-encoding")
        }

        body = self.request.body or None
        if self.request.method in ("GET", "HEAD", "DELETE"):
            body = None

        try:
            resp = await http.fetch(
                url,
                method=self.request.method,
                headers=headers,
                body=body,
                allow_nonstandard_methods=True,
                raise_error=False,
            )
            self.set_status(resp.code)
            skip = {"transfer-encoding", "content-length", "server",
                    "access-control-allow-origin"}
            for k, v in resp.headers.get_all():
                if k.lower() not in skip:
                    self.add_header(k, v)
            if resp.body:
                self.write(resp.body)
        except Exception as exc:
            self.set_status(502)
            self.write(json.dumps({"error": str(exc)}))


_original_create_app = _st_server.Server._create_app


def _patched_create_app(self):
    app = _original_create_app(self)
    # Insert API proxy rule at the top of the routing table so it
    # matches before Streamlit's catch-all static file handler.
    api_rule = tornado.routing.Rule(
        tornado.routing.PathMatches(r"/api/.*"), _ApiProxy
    )
    app.default_router.rules.insert(0, api_rule)
    return app


_st_server.Server._create_app = _patched_create_app

# ---------------------------------------------------------------------------
# 3. Launch Streamlit
# ---------------------------------------------------------------------------

from streamlit.web.cli import main as _st_main  # noqa: E402

sys.argv = [
    "streamlit", "run", "react_preview.py",
    "--server.headless=true",
    "--server.port=8501",
    "--browser.gatherUsageStats=false",
]
_st_main()
