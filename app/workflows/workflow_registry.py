from enum import Enum

from workflows.customer_care_workflow import CustomerCareWorkflow
from workflows.claim_review_workflow import ClaimReviewWorkflow
from workflows.denial_learning_workflow import DenialLearningWorkflow


class WorkflowRegistry(Enum):
    """Registry of available workflows.

    Each workflow can be looked up by name and instantiated.
    Used by the event processing system to route events to workflows.
    """

    CUSTOMER_CARE = CustomerCareWorkflow
    CLAIM_REVIEW = ClaimReviewWorkflow
    DENIAL_LEARNING = DenialLearningWorkflow
