from pydantic import BaseModel, ConfigDict


class ProjectCreate(BaseModel):
    name: str
    status: str | None = None
    project_type: str | None = None
    organisation_id: int | None = None
    organisation_name: str | None = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str

    @property
    def label(self) -> str:
        return self.name