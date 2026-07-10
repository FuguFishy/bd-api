from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.workflowruns import (
    WorkflowRunFinishRequest,
    WorkflowRunFinishResponse,
    WorkflowRunStartRequest,
    WorkflowRunStartResponse,
)

router = APIRouter(prefix="/workflow-runs", tags=["workflow-runs"])


@router.post("/start", response_model=WorkflowRunStartResponse)
def start_workflow_run(
    payload: WorkflowRunStartRequest,
    db: Session = Depends(get_db),
):
    row = db.execute(
        text(
            """
            insert into public.workflowruns
            (
                workflowname,
                runtype,
                startedat,
                status,
                recordsprocessed,
                recordsflagged,
                errorsummary
            )
            values
            (
                :workflowname,
                :runtype,
                :startedat,
                :status,
                :recordsprocessed,
                :recordsflagged,
                :errorsummary
            )
            returning id, status
            """
        ),
        {
            "workflowname": payload.workflowname,
            "runtype": payload.runtype,
            "startedat": datetime.now(UTC),
            "status": "running",
            "recordsprocessed": payload.recordsprocessed or 0,
            "recordsflagged": payload.recordsflagged or 0,
            "errorsummary": payload.errorsummary,
        },
    ).mappings().first()

    db.commit()

    return WorkflowRunStartResponse(
        ok=True,
        workflowrunid=row["id"],
        status=row["status"],
    )


@router.post("/{workflowrunid}/success", response_model=WorkflowRunFinishResponse)
def finish_workflow_run_success(
    workflowrunid: int,
    payload: WorkflowRunFinishRequest,
    db: Session = Depends(get_db),
):
    existing = db.execute(
        text(
            """
            select id
            from public.workflowruns
            where id = :workflowrunid
            limit 1
            """
        ),
        {"workflowrunid": workflowrunid},
    ).mappings().first()

    if not existing:
        raise HTTPException(status_code=404, detail="Workflow run not found")

    finishedat = datetime.now(UTC)

    row = db.execute(
        text(
            """
            update public.workflowruns
            set
                finishedat = :finishedat,
                status = :status,
                recordsprocessed = :recordsprocessed,
                recordsflagged = :recordsflagged,
                errorsummary = :errorsummary
            where id = :workflowrunid
            returning id, status, finishedat
            """
        ),
        {
            "workflowrunid": workflowrunid,
            "finishedat": finishedat,
            "status": "success",
            "recordsprocessed": payload.recordsprocessed or 0,
            "recordsflagged": payload.recordsflagged or 0,
            "errorsummary": payload.errorsummary,
        },
    ).mappings().first()

    db.commit()

    return WorkflowRunFinishResponse(
        ok=True,
        workflowrunid=row["id"],
        status=row["status"],
        finishedat=row["finishedat"],
    )


@router.post("/{workflowrunid}/fail", response_model=WorkflowRunFinishResponse)
def finish_workflow_run_fail(
    workflowrunid: int,
    payload: WorkflowRunFinishRequest,
    db: Session = Depends(get_db),
):
    existing = db.execute(
        text(
            """
            select id
            from public.workflowruns
            where id = :workflowrunid
            limit 1
            """
        ),
        {"workflowrunid": workflowrunid},
    ).mappings().first()

    if not existing:
        raise HTTPException(status_code=404, detail="Workflow run not found")

    finishedat = datetime.now(UTC)

    row = db.execute(
        text(
            """
            update public.workflowruns
            set
                finishedat = :finishedat,
                status = :status,
                recordsprocessed = :recordsprocessed,
                recordsflagged = :recordsflagged,
                errorsummary = :errorsummary
            where id = :workflowrunid
            returning id, status, finishedat
            """
        ),
        {
            "workflowrunid": workflowrunid,
            "finishedat": finishedat,
            "status": "failed",
            "recordsprocessed": payload.recordsprocessed or 0,
            "recordsflagged": payload.recordsflagged or 0,
            "errorsummary": payload.errorsummary,
        },
    ).mappings().first()

    db.commit()

    return WorkflowRunFinishResponse(
        ok=True,
        workflowrunid=row["id"],
        status=row["status"],
        finishedat=row["finishedat"],
    )