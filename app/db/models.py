from sqlalchemy import Column, Integer, Text, Date, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Organisation(Base):
    __tablename__ = "organisations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(Text, nullable=False, unique=True)
    short_name = Column(Text)
    sector = Column(Text)
    tier = Column(Text)
    account_status = Column(Text)
    notes = Column(Text)
    last_contact_date = Column(Date)

    contacts = relationship("Contact", back_populates="organisation")
    projects = relationship("Project", back_populates="organisation")


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    organisation_id = Column(Integer, ForeignKey("organisations.id"), nullable=False)
    first_name = Column(Text)
    last_name = Column(Text)
    email = Column(Text)
    full_name = Column(Text, nullable=False)
    position_title = Column(Text)
    department = Column(Text)
    relationship_type = Column(Text)
    source_type = Column(Text)
    linkedin_profile_url = Column(Text)
    linkedin_connection_status = Column(Text)
    verification_status = Column(Text)
    notes = Column(Text)
    organisation_name = Column(Text)

    organisation = relationship("Organisation", back_populates="contacts")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    organisation_id = Column(Integer, ForeignKey("organisations.id"), nullable=False)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True)
    name = Column(Text, nullable=False)
    project_type = Column(Text)
    status = Column(Text)
    opportunity_signal = Column(Text)
    strategic_importance = Column(Text)
    start_date = Column(Date)
    end_date = Column(Date)
    notes = Column(Text)
    organisation_name = Column(Text)

    organisation = relationship("Organisation", back_populates="projects")

class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, index=True)

    # Foreign key IDs — existing columns
    contact_id = Column(Integer, nullable=True)
    organisation_id = Column(Integer, nullable=True)
    project_id = Column(Integer, nullable=True)

    # Core activity metadata
    activity_type = Column(Text, nullable=False)
    activity_date = Column(DateTime, nullable=False)
    outcome = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    logged_by = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False)
