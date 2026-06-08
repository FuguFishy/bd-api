# BD Automation Process Flow

A small FastAPI-based business development tracker for logging activities, managing contacts, organisations, and projects, and showing a weekly activity summary.

## Project overview

This project started as a structured backend + UI MVP for tracking business development activity in one place.  
It includes:

- A FastAPI API layer.
- A simple HTML UI mounted into the same app.
- Database-backed contacts, organisations, projects, and activities.
- A weekly report endpoint for summary tracking.

The goal was to build a lightweight internal workflow tool with clear routes, predictable response models, and a simple browser UI.

## What it does

- Lists contacts, organisations, and projects for dropdown selection.
- Lets users log activities against those records.
- Supports quick-add forms for contacts and projects.
- Shows weekly summary information.
- Uses a single FastAPI app to serve both the API and the UI.

## Project structure

- `app/main.py` — Main FastAPI app and API router registration.
- `app/ui/main.py` — Serves the HTML UI.
- `app/api/routes/` — API route modules.
- `app/db/` — Database CRUD, session, and model code.
- `app/schemas/` — Pydantic schemas for request and response models.
- `app/ui/bd-ui-mvp.html` — Browser UI for the MVP.

## Current status

This project is functionally complete as an MVP and has been updated in GitHub.  
The API and UI are wired together, dropdowns load correctly, and the response models have been standardized for easier maintenance.

This repository is now at a stable stopping point and can be treated as a completed project or archived reference.

## Running locally

Typical development flow:

```bash
python -m uvicorn app.main:app --reload
```

Then open the app in the browser and use the UI to test contacts, organisations, projects, activities, and the weekly report.

## Notes

- The repository includes a modular FastAPI structure.
- The UI uses same-origin fetch calls to talk to the API.
- The response schemas are designed to keep the frontend contract stable.
- If the project is reopened later, any new work should continue from the current schema-first structure.

## Status

Project 5 is complete.
