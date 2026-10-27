from __future__ import annotations

from app.config import get_settings
from app.sources.base import SourceAdapter

ALL = {
    "autoscout24": ("app.sources.autoscout24", "AutoScout24Adapter"),
    "marktplaats": ("app.sources.marktplaats", "MarktplaatsAdapter"),
}


def get_adapter(name: str) -> SourceAdapter:
    import importlib

    module, cls = ALL[name]
    return getattr(importlib.import_module(module), cls)()


def enabled_adapters() -> list[SourceAdapter]:
    return [get_adapter(n) for n in get_settings().source_list if n in ALL]


def adapter_for_url(url: str) -> SourceAdapter | None:
    for name in ALL:
        adapter = get_adapter(name)
        if adapter.supports_url(url):
            return adapter
    return None


def adapters_info() -> list[dict]:
    enabled = set(get_settings().source_list)
    out = [{"name": "demo", "label": "Demo-data", "enabled": "demo" in enabled or get_settings().demo_mode, "verified": True}]
    for name, (module, cls) in ALL.items():
        import importlib

        klass = getattr(importlib.import_module(module), cls)
        out.append({"name": name, "label": klass.label, "enabled": name in enabled, "verified": klass.verified})
    return out
