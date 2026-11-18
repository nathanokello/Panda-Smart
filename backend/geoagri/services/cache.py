"""Small cache helpers for environmental provider adapters.

Provider adapters should cache by provider + variable + rounded coordinates + period,
attach provenance to every observation, and never synthesize missing measurements.
"""
from django.core.cache import cache

DEFAULT_ENVIRONMENT_TTL = 6 * 60 * 60

def cached_provider_call(cache_key, fetch_callable, timeout=DEFAULT_ENVIRONMENT_TTL):
    cached = cache.get(cache_key)
    if cached is not None:
        return cached, True
    result = fetch_callable()
    if result is not None:
        cache.set(cache_key, result, timeout)
    return result, False
