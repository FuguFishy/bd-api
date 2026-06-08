from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.crud import create_contact, list_contacts
from app.db.session import get_db
from app.schemas.contacts import ContactCreate, ContactRead
from app.schemas.common import DropdownItem

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.post("", response_model=ContactRead)
def create_contact_route(payload: ContactCreate, db: Session = Depends(get_db)):
    return create_contact(db, payload)


@router.get("", response_model=list[DropdownItem])
def read_contacts(db: Session = Depends(get_db)):
    rows = list_contacts(db)
    return [
        DropdownItem(id=c.id, label=f"{c.first_name} {c.last_name}".strip())
        for c in rows
    ]