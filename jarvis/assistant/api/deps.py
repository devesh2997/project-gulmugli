"""
Dependency injection for API routes.

Every route that needs the assistant dict uses `Depends(get_assistant)`.
The assistant dict is stored on the FastAPI app's state during startup
by `create_api()` in app.py — same dict built by `build_assistant()` in main.py.
"""

from fastapi import Request


def get_assistant(request: Request) -> dict:
    """
    FastAPI dependency — returns the assistant dict from app state.

    The assistant dict contains all initialized providers:
      assistant["brain"], assistant["music"], assistant["lights"],
      assistant["face_ui"], assistant["memory"], etc.

    This is the same dict used by handle_intent() and process_input().
    """
    return request.app.state.assistant
