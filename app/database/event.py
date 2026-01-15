import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID

from database.session import Base

"""
Event Database Model Module

This module defines the SQLAlchemy model for storing events in the database.
It provides two main storage components:
1. Raw event data (data column): Stores the original incoming event
2. Processing results (task_context column): Stores the workflow processing results

This model is used with Alembic to generate the initial database migration.
"""


class Event(Base):
    """SQLAlchemy model for storing events and their processing results.

    This model serves as the primary storage for both incoming events and
    their processing results. It uses JSON columns for flexible schema
    storage of both raw data and processing context.
    """

    __tablename__ = "events"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid1,
        doc="Unique identifier for the event",
    )
    workflow_type = Column(
        String(150),
        nullable=False,
        doc="Type of workflow associated with the event (e.g., 'support')",
    )
    data = Column(JSON, doc="Raw event data as received from the API endpoint")
    task_context = Column(JSON, doc="Processing results and metadata from the workflow")

    created_at = Column(
        DateTime, default=datetime.now, doc="Timestamp when the event was created"
    )
    updated_at = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        doc="Timestamp when the event was last updated",
    )
