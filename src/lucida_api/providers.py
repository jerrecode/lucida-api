"""Capability-described providers; no unverified Lucida website scraping."""
from __future__ import annotations
from typing import Protocol
from .models import ProviderCapabilities

class Provider(Protocol):
    @property
    def capabilities(self) -> ProviderCapabilities: ...
    def accepts(self, source: str) -> bool: ...

class SampleProvider:
    capabilities = ProviderCapabilities("sample", metadata=True, acquisition=True,
                                        formats=("wav",), notes="Offline synthesized 1-second test tone")
    def accepts(self, source: str) -> bool:
        return source == "sample://tone"

class DirectMediaProvider:
    capabilities = ProviderCapabilities("direct-http", acquisition=True,
                                        notes="Trusted user-authorized audio HTTP(S) URLs only; no redirects")
    def accepts(self, source: str) -> bool:
        return source.startswith(("https://", "http://"))

class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: list[Provider] = []

    def register(self, provider: Provider) -> None:
        if any(p.capabilities.name == provider.capabilities.name for p in self._providers):
            raise ValueError("Duplicate provider")
        self._providers.append(provider)

    def capabilities(self) -> list[ProviderCapabilities]:
        return [p.capabilities for p in self._providers]

    def resolve(self, source: str) -> Provider | None:
        return next((p for p in self._providers if p.accepts(source)), None)
