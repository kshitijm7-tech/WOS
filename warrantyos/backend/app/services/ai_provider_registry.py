"""
Provider Registry — Part 2.4/2.5
Lightweight selection of AI provider. Orchestrator depends on registry, not on Mock directly.
Part 2.5: Supports mock, rocketride, local with safe fallback.
"""

from app.core.config import get_settings

# Import here to avoid circular
def get_provider():
    """
    Returns an AIProvider instance based on config.AI_PROVIDER.
    Part 2.5: mock is the only active offline provider; rocketride/local fall back to mock if unavailable.
    """
    settings = get_settings()
    provider_name = getattr(settings, "AI_PROVIDER", "mock").lower()
    fallback = getattr(settings, "AI_FALLBACK_TO_MOCK", True)
    # Note: AI_FALLBACK_TO_MOCK may be bool or string; handle both
    if isinstance(fallback, str):
        fallback = fallback.lower() not in ("false", "0", "no")

    if provider_name == "mock":
        from app.services.providers.mock_provider import MockAIProvider
        return MockAIProvider()
    elif provider_name == "rocketride":
        try:
            from app.services.providers.rocketride_provider import RocketRideProvider
            provider = RocketRideProvider(api_key=getattr(settings, "ROCKETRIDE_API_KEY", "") or getattr(settings, "AI_API_KEY", ""))
            # Test availability without calling external; if not available, it will raise on run_pipeline, but we can check _available
            if not getattr(provider, "_available", True):
                if fallback:
                    from app.services.providers.mock_provider import MockAIProvider
                    return MockAIProvider()
            return provider
        except Exception as e:
            if fallback:
                from app.services.providers.mock_provider import MockAIProvider
                return MockAIProvider()
            raise
    elif provider_name == "local":
        try:
            from app.services.providers.local_provider import LocalLLMProvider
            return LocalLLMProvider(model=getattr(settings, "AI_MODEL", "mock-v1"))
        except Exception as e:
            if fallback:
                from app.services.providers.mock_provider import MockAIProvider
                return MockAIProvider()
            raise
    else:
        if fallback:
            from app.services.providers.mock_provider import MockAIProvider
            return MockAIProvider()
        raise ValueError(f"Unknown AI provider: {provider_name}")


def get_provider_info():
    """
    Returns safe provider info for logging/UI (no secrets).
    """
    settings = get_settings()
    return {
        "provider": getattr(settings, "AI_PROVIDER", "mock"),
        "model": getattr(settings, "AI_MODEL", "mock-v1"),
        "pipeline_version": getattr(settings, "AI_PIPELINE_VERSION", "2.4"),
        "fallback": getattr(settings, "AI_FALLBACK_TO_MOCK", True),
    }
