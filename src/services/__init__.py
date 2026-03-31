"""Service package exports.

Keep package imports lightweight so pure planning/test modules can be imported
without forcing optional runtime dependencies such as Redis.
"""

__all__ = ["EventBroadcaster", "get_broadcaster"]


def __getattr__(name):
    if name in __all__:
        from src.services.event_broadcaster import EventBroadcaster, get_broadcaster

        exports = {
            "EventBroadcaster": EventBroadcaster,
            "get_broadcaster": get_broadcaster,
        }
        return exports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
