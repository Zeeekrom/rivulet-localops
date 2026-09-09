from typing import Protocol

from rivulet_localops.models import DiagnoseRequest, DiagnoseResponse


class TriageProvider(Protocol):
    """Stable boundary for baseline and future model-assisted providers."""

    def diagnose(self, request: DiagnoseRequest) -> DiagnoseResponse: ...
