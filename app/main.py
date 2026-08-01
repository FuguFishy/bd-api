from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.ui.main import app as ui_app

app = FastAPI(title="BD API")


@app.get("/")
def root():
    return RedirectResponse(url="/ui/")


@app.get("/health")
def health():
    return {"status": "ok"}


app.mount("/ui", ui_app)