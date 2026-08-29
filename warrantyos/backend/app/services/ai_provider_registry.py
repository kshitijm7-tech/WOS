"""
Provider Registry — Part 2.4
Lightweight selection of AI provider. Orchestrator depends on registry, not on Mock directly.
"""

from app.core.config import get_settings

# Import here to avoid circular
def get_provider():
    """
    Returns an AIProvider instance based on config.AI_PROVIDER.
    Only "mock" is active in Part 2.4. Future: "rocketrider", "local".
    """
    settings = get_settings()
    provider_name = getattr(settings, "AI_PROVIDER", "mock").lower()

    if provider_name == "mock":
        # Import here to avoid circular and to ensure path
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
        from rocketrider.adapter import MockRocketRideClient
        return MockRocketRideClient()
    elif provider_name == "rocketrider":
        # Real provider not implemented in Part 2.4 (offline)
        raise NotImplementedError("RocketRide provider not implemented in offline Part 2.4")
    else:
        raise ValueError(f"Unknown AI provider: {provider_name}")
