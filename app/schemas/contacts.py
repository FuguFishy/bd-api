from pydantic import BaseModel, ConfigDict


class ContactCreate(BaseModel):
    first_name: str
    last_name: str
    email: str | None = None
    organisation_id: int | None = None
    organisation_name: str | None = None


class ContactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    email: str | None = None
    organisation_id: int | None = None

    @property
    def label(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()