"""Process-wide runtime state (startup progress) shared between the app and the API."""

STATE: dict = {"ready": False, "message": "Bezig met opstarten…"}
