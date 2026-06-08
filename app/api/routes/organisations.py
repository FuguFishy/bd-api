from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.crud import create_organisation, list_organisations
from app.db.session import get_db
from app.schemas.organisations import OrganisationCreate, OrganisationRead
from app.schemas.common import DropdownItem

router = APIRouter(prefix="/organisations", tags=["organisations"])


@router.post("", response_model=OrganisationRead)
def create_org(payload: OrganisationCreate, db: Session = Depends(get_db)):
    return create_organisation(db, payload)


@router.get("", response_model=list[DropdownItem])
def read_orgs(db: Session = Depends(get_db)):
    rows = list_organisations(db)
    return [DropdownItem(id=o.id, label=o.name) for o in rows]