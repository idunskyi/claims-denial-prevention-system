import json
from typing import AsyncIterator


async def event_stream_generator(workflow_stream: AsyncIterator) -> AsyncIterator[str]:
    import logging

    try:
        async for event in workflow_stream:
            sse_data = f"data: {json.dumps(event)}\n\n"
            yield sse_data
        yield "data: [DONE]\n\n"
    except Exception as e:
        logging.error(f"Error in event_stream_generator: {e}", exc_info=True)
        error_event = {"type": "error", "error": str(e)}
        yield f"data: {json.dumps(error_event)}\n\n"
        raise
