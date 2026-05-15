try:
    from cachelib import SimpleCache as _SimpleCache

    class ReportCache:
        def __init__(self, default_timeout=1800):
            self._cache = _SimpleCache(default_timeout=default_timeout)

        def set(self, key, value):
            self._cache.set(key, value, timeout=self._cache.default_timeout)

        def get(self, key, default=None):
            result = self._cache.get(key)
            return result if result is not None else default

        def delete(self, key):
            self._cache.delete(key)

except ImportError:
    class ReportCache:
        def __init__(self, default_timeout=1800):
            self._store = {}
            self._default_timeout = default_timeout

        def set(self, key, value):
            self._store[key] = value

        def get(self, key, default=None):
            return self._store.get(key, default)

        def delete(self, key):
            self._store.pop(key, None)

report_cache = ReportCache()
