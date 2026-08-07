from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.api.routes import ops_dashboard, scrape_runs, n8n_webhooks, review_queue
from app.ui.main import app as ui_app

app = FastAPI(title="BD API")

app.include_router(scrape_runs.router)
app.include_router(ops_dashboard.router)
app.include_router(n8n_webhooks.router)
app.include_router(review_queue.router)

@app.get("/")
def root():
    return RedirectResponse(url="/ui/")


@app.get("/health")
def health():
    return {"status": "ok"}


app.mount("/ui", ui_app)
