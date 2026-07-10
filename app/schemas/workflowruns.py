from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class WorkflowRunStartRequest(BaseModel):
    workflowname: str
    runtype: str
    recordsprocessed: Optional[int] = 0
    recordsflagged: Optional[int] = 0
    errorsummary: Optional[str] = None


class WorkflowRunStartResponse(BaseModel):
    ok: bool
    workflowrunid: int
    status: str


class WorkflowRunFinishRequest(BaseModel):
    recordsprocessed: Optional[int] = 0
    recordsflagged: Optional[int] = 0
    errorsummary: Optional[str] = None


class WorkflowRunFinishResponse(BaseModel):
    ok: bool
    workflowrunid: int
    status: str
    finishedat: datetime