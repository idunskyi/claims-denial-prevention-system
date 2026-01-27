"""
Workflow Orchestration Module

This module implements the core workflow functionality.
It provides a flexible framework for defining and executing workflows with multiple
nodes and routing logic.
"""

import asyncio
import logging
from abc import ABC
from contextlib import contextmanager, nullcontext
from typing import Dict, Optional, ClassVar, Type, Any, AsyncIterator

from dotenv import load_dotenv
from langfuse import get_client

from core.exceptions import LangfuseAuthenticationError
from core.nodes.agent_streaming_node import AgentStreamingNode
from core.nodes.base import Node
from core.nodes.router import BaseRouter
from core.schema import WorkflowSchema, NodeConfig
from core.task import TaskContext
from core.validate import WorkflowValidator

load_dotenv()


class NoOpSpan:
    """No-op span that ignores all update calls."""

    def update(self, **kwargs):
        """Accepts and ignores all keyword arguments for compatibility with real spans."""
        pass


class Workflow(ABC):
    """Abstract base class for defining processing workflows.

    The Workflow class provides a framework for creating processing workflows
    with multiple nodes and routing logic. Each workflow must define its structure
    using a WorkflowSchema.

    Attributes:
        workflow_schema: Class variable defining the workflow's structure and flow
        validator: Validates the workflow schema
        nodes: Dictionary mapping node classes to their instances

    Example:
        class SupportWorkflow(Workflow):
            workflow_schema = WorkflowSchema(
                start=AnalyzeNode,
                nodes=[
                    NodeConfig(node=AnalyzeNode, connections=[RouterNode]),
                    NodeConfig(node=RouterNode, connections=[ResponseNode]),
                ]
            )
    """

    workflow_schema: ClassVar[WorkflowSchema]

    def __init__(self, enable_tracing: bool = False):
        """Initializes the workflow by validating schema and creating nodes.

        Args:
            enable_tracing: Whether to enable Langfuse tracing. Defaults to False.
        """
        self.validator = WorkflowValidator(self.workflow_schema)
        self.validator.validate()
        self.nodes: Dict[Type[Node], NodeConfig] = self._initialize_nodes()
        self.enable_tracing = enable_tracing

        if enable_tracing:
            langfuse = get_client()
            if langfuse.auth_check():
                self.langfuse = langfuse
            else:
                raise LangfuseAuthenticationError(
                    "Failed to authenticate with Langfuse. Check your LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY."
                )
        else:
            self.langfuse = None

    def _observation_context(self, name: str):
        """Returns a tracing context manager or no-op based on enable_tracing.

        Args:
            name: The name for the tracing span.

        Returns:
            A context manager that yields a Langfuse span if tracing is enabled,
            or a NoOpSpan otherwise.
        """
        if self.enable_tracing and self.langfuse:
            return self.langfuse.start_as_current_observation(as_type="span", name=name)
        return nullcontext(NoOpSpan())

    @contextmanager
    def node_context(self, node_name: str):
        """Context manager for logging node execution and handling errors.

        Args:
            node_name: Name of the node being executed

        Yields:
            None

        Raises:
            Exception: Re-raises any exception that occurs during node execution
        """
        logging.info(f"Starting node: {node_name}")
        try:
            yield
        except Exception as e:
            logging.error(f"Error in node {node_name}: {str(e)}")
            raise
        finally:
            logging.info(f"Finished node: {node_name}")

    def _initialize_nodes(self) -> Dict[Type[Node], NodeConfig]:
        """Initializes all nodes defined in the workflow schema.

        Returns:
            Dictionary mapping node classes to their instances
        """
        nodes = {}
        for node_config in self.workflow_schema.nodes:
            nodes[node_config.node] = node_config
            for connected_node in node_config.connections:
                if connected_node not in nodes:
                    connected_node_config = NodeConfig(node=connected_node)
                    nodes[connected_node] = connected_node_config
        return nodes

    @staticmethod
    def _instantiate_node(node_class: Type[Node]) -> Node:
        """Creates an instance of a node class.

        Args:
            node_class: The class of the node to instantiate

        Returns:
            An instance of the specified node class
        """
        return node_class()

    def run(self, event: Any) -> TaskContext:
        """Executes the workflow for a given event synchronously.

        Use this when you want to run the workflow in a new event loop,
        for example in a Celery background task or a plain Python script.

        Args:
            event: The event data to process through the workflow.

        Returns:
            TaskContext containing the results of workflow execution.
        """
        return asyncio.run(self.__run(event))

    async def run_async(self, event: Any) -> TaskContext:
        """Executes the workflow for a given event asynchronously.

        Use this when you want to run the workflow in an active event loop,
        for example in a FastAPI endpoint or Jupyter Notebook.

        Args:
            event: The event data to process through the workflow.

        Returns:
            TaskContext containing the results of workflow execution.
        """
        return await self.__run(event)

    async def run_stream_async(self, event: Any) -> AsyncIterator[Dict[str, Any]]:
        """Executes the workflow with streaming support, yielding events as they occur.

        Args:
            event: The event data to process through the workflow.

        Yields:
            Dict containing streaming events with type and data fields.
            Error events have type "error" with an "error" field.

        Raises:
            Exception: Re-raises any exception that occurs during workflow execution.
        """
        task_context = TaskContext(event=event)

        with self._observation_context(self.__class__.__name__) as workflow_span:
            try:
                logging.info("Starting workflow streaming execution")

                # Parse the raw event to the Pydantic schema defined in the WorkflowSchema
                task_context.event = self.workflow_schema.event_schema(**event)
                workflow_span.update(input=event)
                logging.info(
                    f"Parsed event with schema: {self.workflow_schema.event_schema.__name__}"
                )

                task_context.metadata["nodes"] = self.nodes
                current_node_class = self.workflow_schema.start
                logging.info(f"Starting with node: {current_node_class.__name__}")

                while current_node_class:
                    if task_context.should_stop:
                        logging.info("Stopping workflow execution")
                        break

                    current_node = self.nodes[current_node_class].node
                    node_name = current_node_class.__name__

                    with self._observation_context(node_name) as node_span:
                        node_span.update(
                            input=task_context.model_dump(
                                exclude={"metadata": {"nodes"}}
                            )
                        )

                        with self.node_context(node_name):
                            if not issubclass(current_node, BaseRouter):
                                node_instance = current_node(task_context=task_context)
                                logging.info(f"Node instance created: {node_name}")

                                if isinstance(node_instance, AgentStreamingNode):
                                    async for stream_event in node_instance.process(
                                        task_context
                                    ):
                                        yield stream_event
                                else:
                                    task_context = await node_instance.process(
                                        task_context
                                    )

                            node_span.update(
                                output=task_context.model_dump(
                                    include={"nodes": {node_name}}
                                )
                            )

                    current_node_class = await self._get_next_node_class(
                        current_node_class, task_context
                    )

                workflow_span.update(
                    output=task_context.model_dump(exclude={"metadata": {"nodes"}})
                )
                task_context.metadata.pop("nodes", None)

            except Exception as e:
                logging.error(f"Error in workflow execution: {str(e)}", exc_info=True)
                workflow_span.update(level="ERROR", status_message=str(e))
                yield {"type": "error", "error": str(e)}
                raise

    async def __run(self, event: Any) -> TaskContext:
        """Executes the workflow for a given event.

        Args:
            event: The event to process through the workflow

        Returns:
            TaskContext containing the results of workflow execution

        Raises:
            Exception: Any exception that occurs during workflow execution
        """
        task_context = TaskContext(event=event)

        with self._observation_context(self.__class__.__name__) as workflow_span:
            try:
                # Parse the raw event to the Pydantic schema defined in the WorkflowSchema
                task_context.event = self.workflow_schema.event_schema(**event)
                workflow_span.update(input=event)

                task_context.metadata["nodes"] = self.nodes
                current_node_class = self.workflow_schema.start

                while current_node_class:
                    if task_context.should_stop:
                        logging.info("Stopping workflow execution")
                        break

                    current_node = self.nodes[current_node_class].node
                    node_name = current_node_class.__name__

                    with self._observation_context(node_name) as node_span:
                        node_span.update(
                            input=task_context.model_dump(
                                exclude={"metadata": {"nodes"}}
                            )
                        )

                        with self.node_context(node_name):
                            if not issubclass(current_node, BaseRouter):
                                task_context = await current_node(
                                    task_context=task_context
                                ).process(task_context)

                        node_span.update(
                            output=task_context.model_dump(
                                include={"nodes": {node_name}}
                            )
                        )

                    current_node_class = await self._get_next_node_class(
                        current_node_class, task_context
                    )

                workflow_span.update(
                    output=task_context.model_dump(exclude={"metadata": {"nodes"}})
                )
                task_context.metadata.pop("nodes")
                return task_context

            except Exception as e:
                logging.error(f"Error in workflow execution: {str(e)}", exc_info=True)
                workflow_span.update(level="ERROR", status_message=str(e))
                raise

    async def _get_next_node_class(
        self, current_node_class: Type[Node], task_context: TaskContext
    ) -> Optional[Type[Node]]:
        """Determines the next node to execute in the workflow.

        Args:
            current_node_class: The class of the current node
            task_context: The current task context

        Returns:
            The class of the next node to execute, or None if at the end
        """
        node_config = next(
            (nc for nc in self.workflow_schema.nodes if nc.node == current_node_class),
            None,
        )

        if not node_config or not node_config.connections:
            return None

        if node_config.is_router:
            router: BaseRouter = self.nodes[current_node_class].node()
            return await self._handle_router(router, task_context)

        return node_config.connections[0]

    async def _handle_router(
        self, router: BaseRouter, task_context: TaskContext
    ) -> Optional[Type[Node]]:
        """Handles routing logic for router nodes.

        Args:
            router: The router node instance
            task_context: The current task context

        Returns:
            The class of the next node to execute, or None if at the end
        """
        next_node = router.route(task_context)
        return next_node.__class__ if next_node else None
