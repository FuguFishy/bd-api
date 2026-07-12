from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.health import router as health_router
from app.api.routes.organisations import router as organisations_router
from app.api.routes.contacts import router as contacts_router
from app.api.routes.projects import router as projects_router
from app.api.routes.activities import router as activities_router
from app.api.routes.reports import router as reports_router
from app.api.routes.n8n_webhooks import router as n8n_webhooks_router
from app.api.routes.review_queue import router as review_queue_router
from app.api.routes.scrape_runs import router as scrape_runs_router
from app.ui.main import app as ui_app
from app.api.routes.ops_dashboard import router as ops_dashboard_router

app = FastAPI(
    title="BD API",
    description="Internal BD platform API with UI routes, review queue, n8n webhooks, and ops monitoring",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(organisations_router)
app.include_router(contacts_router)
app.include_router(projects_router)
app.include_router(activities_router)
app.include_router(reports_router)
app.include_router(n8n_webhooks_router)
app.include_router(review_queue_router)
app.include_router(scrape_runs_router)
app.include_router(ops_dashboard_router)

app.mount("/ui", ui_app)