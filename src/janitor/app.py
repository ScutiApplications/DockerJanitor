"""HTTP layer: the web page, the admin API and the scheduler loop."""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import unquote

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field

from janitor.security import SetupCode, hash_password, verify_password
from janitor.service import Busy, Janitor
from janitor.settings import Settings

log = logging.getLogger("janitor")

WEB_PAGE = Path(__file__).resolve().parents[2] / "web" / "index.html"
TICK_SECONDS = 60
WRONG_PASSWORD_DELAY = 1.0


class SetupIn(BaseModel):
    code: str = Field(max_length=64)
    password: str = Field(min_length=10, max_length=128)


class SettingsIn(Settings):
    smtp_password: str = Field("", max_length=256)  # empty keeps the stored one


class PostponeIn(BaseModel):
    days: int = Field(ge=1, le=27)


def create_app(janitor: Janitor, tick_seconds: float | None = TICK_SECONDS) -> FastAPI:
    """`tick_seconds=None` leaves the scheduler off (tests)."""
    store = janitor.store
    setup_code = None if store.get_sync("admin") else SetupCode()
    guess_lock = asyncio.Lock()
    setup_lock = asyncio.Lock()

    async def schedule() -> None:
        while True:
            try:
                if await store.get("admin"):  # nobody can skip a run before setup, so none happens
                    await janitor.tick()
            except Exception:  # noqa: BLE001 - the loop must survive any single failure
                log.exception("scheduler tick failed")
            await asyncio.sleep(tick_seconds)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if setup_code:
            print(f"DockerJanitor setup code: {setup_code.code}", flush=True)
        task = asyncio.create_task(schedule()) if tick_seconds else None
        yield
        if task:
            task.cancel()

    async def admin(x_admin_password: str = Header("")) -> None:
        stored = await store.get("admin")
        if not stored:
            raise HTTPException(403, "Setup is not done yet.")
        if not await asyncio.to_thread(verify_password, unquote(x_admin_password), stored):
            async with guess_lock:  # one wrong guess per second, however many connections
                await asyncio.sleep(WRONG_PASSWORD_DELAY)
            raise HTTPException(401, "Wrong password.")

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    private = APIRouter(prefix="/api", dependencies=[Depends(admin)])

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/")
    async def page():
        return FileResponse(WEB_PAGE, headers={"Cache-Control": "no-cache"})

    @app.get("/admin/")
    async def hub_path():
        return RedirectResponse("../")  # relative, so it also works behind ServiceHub's proxy

    @app.get("/api/status")
    async def status():
        return {"setup_done": bool(await store.get("admin"))}

    @app.post("/api/setup")
    async def setup(body: SetupIn):
        async with setup_lock:
            if await store.get("admin"):
                raise HTTPException(409, "Setup is already done.")
            if setup_code is None:
                raise HTTPException(409, "Restart the service to get a new setup code.")
            if not setup_code.accepts(body.code):
                locked = setup_code.tries_left <= 0
                raise HTTPException(403, "Locked. Restart the service." if locked else "Wrong setup code.")
            await store.set("admin", await asyncio.to_thread(hash_password, body.password))
        return {"setup_done": True}

    @private.get("/overview")
    async def overview():
        return {"settings": (await janitor.settings()).model_dump(),
                "smtp_password_set": bool(await store.get("smtp_password")),
                "state": await janitor.state(), "running": janitor.running,
                "disks": await janitor.disks.read(), "history": await store.history()}

    @private.put("/settings")
    async def save(body: SettingsIn):
        await janitor.save_settings(Settings(**body.model_dump(exclude={"smtp_password"})), body.smtp_password)
        return {"ok": True}

    @private.post("/preview")
    async def preview():
        settings = await janitor.settings()
        try:
            return await janitor.cleaner.preview(settings.prune_images, settings.prune_cache)
        except Exception as error:  # noqa: BLE001
            raise HTTPException(502, f"Docker preview failed: {str(error)[:300]}") from error

    @private.post("/run", status_code=202)
    async def run():
        try:
            janitor.start_run()
        except Busy as error:
            raise HTTPException(409, "A cleanup is already running.") from error
        return {"started": True}

    @private.post("/skip")
    async def skip():
        await janitor.skip()
        return {"ok": True}

    @private.post("/postpone")
    async def postpone(body: PostponeIn):
        await janitor.postpone(body.days)
        return {"ok": True}

    @private.post("/test-email")
    async def test_email():
        try:
            await janitor.send("Test email", ["Email from DockerJanitor works."])
        except Exception as error:  # noqa: BLE001
            raise HTTPException(502, f"Sending failed: {str(error)[:300]}") from error
        return {"ok": True}

    app.include_router(private)
    return app
