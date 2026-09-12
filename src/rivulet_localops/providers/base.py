from typing import Protocol

from rivulet_localops.models import DiagnoseRequest, DiagnoseResponse, ProviderReference


class TriageProvider(Protocol):
    """Stable boundary for baseline and future model-assisted providers."""

    @property
    def reference(self) -> ProviderReference: ...

    def diagnose(self, request: DiagnoseRequest) -> DiagnoseResponse: ...
