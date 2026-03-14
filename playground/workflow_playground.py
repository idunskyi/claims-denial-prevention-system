import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env file from the app directory
env_path = Path(__file__).parent.parent / "app" / ".env"
load_dotenv(env_path)

sys.path.append(str(Path(__file__).parent.parent / "app"))
sys.path.append(str(Path(__file__).parent.parent))

import nest_asyncio
from workflows.customer_care_workflow import CustomerCareWorkflow

from playground.utils.event_loader import EventLoader

logging.basicConfig(level=logging.INFO)
nest_asyncio.apply()

"""
This playground is used to test the WorkflowRegistry and the workflows themselves.
"""

event = EventLoader.load_event(event_key="spam")
workflow = CustomerCareWorkflow()
result = workflow.run(event)
print(result.model_dump_json(indent=2))
