from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="BD UI")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/", include_in_schema=False)
def ui_root():
    return RedirectResponse(url="/review-queue")


@app.get("/review-queue", include_in_schema=False)
def review_queue_page(request: Request):
    return templates.TemplateResponse(
        request,
        "review_queue.html",
        {
            "page_title": "Review Queue",
        },
    )