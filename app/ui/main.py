from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pathlib import Path

app = FastAPI()
UI_PATH = Path(__file__).with_name("bd-ui-mvp.html")

@app.get("/", response_class=HTMLResponse)
def home():
    return UI_PATH.read_text(encoding="utf-8")