import time

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from misc.auth import login_required
from config import get_version


def init_app_routes(app: FastAPI):
    from routes.user import router as user_router
    from routes.news import router as news_router
    from routes.event import router as event_router
    from routes.edit import router as edit_router
    from routes.delete import router as delete_router
    from routes.create import router as create_router

    app.include_router(news_router, prefix="/api/news", tags=["news"])
    app.include_router(event_router, prefix="/api/event", tags=["event"])
    app.include_router(user_router, prefix="/api/user", tags=["user"])

    app.include_router(
        edit_router,
        prefix="/api/edit",
        tags=["edit"],
        dependencies=[Depends(login_required)],
    )
    app.include_router(
        delete_router,
        prefix="/api/delete",
        tags=["delete"],
        dependencies=[Depends(login_required)],
    )
    app.include_router(
        create_router,
        prefix="/api/create",
        tags=["create"],
        dependencies=[Depends(login_required)],
    )
    @app.middleware("http")
    async def add_header(request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(round(process_time * 1000, 4))
        response.headers["X-CsaWeb-Version"] = get_version()
        return response

    @app.middleware("http")
    async def add_cache_control(request: Request, call_next):
        response = await call_next(request)
        if "Cache-Control" not in response.headers:
            for tp in ["image", "font", "css", "javascript"]:
                if tp in response.headers.get("Content-Type", ""):
                    response.headers["Cache-Control"] = "public, max-age=2592000"
                    break
            else:
                response.headers["Cache-Control"] = "no-store"
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins="*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
