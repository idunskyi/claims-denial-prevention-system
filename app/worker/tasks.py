from contextlib import contextmanager

from database.event import Event
from database.repository import GenericRepository
from database.session import db_session
from worker.config import celery_app
from workflows.workflow_registry import WorkflowRegistry

"""
Workflow Task Processing Module

This module handles asynchronous processing of workflow events using Celery.
It manages the lifecycle of event processing from database retrieval through
workflow execution and result storage.
"""


@celery_app.task(name="process_incoming_event")
def process_incoming_event(event_id: str):
    """Processes an incoming event through its designated workflow.

    This Celery task handles the asynchronous processing of events by:
    1. Retrieving the event from the database
    2. Determining the appropriate workflow
    3. Executing the workflow
    4. Storing the results

    Args:
        event_id: Unique identifier of the event to process
        workflow_type: Type of workflow to use for processing the event
    """
    with contextmanager(db_session)() as session:
        # Initialize repository for database operations
        repository = GenericRepository(session=session, model=Event)

        # Retrieve event from database
        db_event = repository.get(id=event_id)
        if db_event is None:
            raise ValueError(f"Event with id {event_id} not found")

        # Execute workflow and store results
        workflow = WorkflowRegistry[str(db_event.workflow_type)].value()
        task_context = workflow.run(db_event.data).model_dump(mode="json")

        db_event.task_context = task_context

        # Update event with processing results
        repository.update(obj=db_event)
