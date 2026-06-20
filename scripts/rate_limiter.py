#!/usr/bin/env python3
"""B2H4 Rate Limiter — rate limiting simples por IP."""
import time
import threading
from collections import defaultdict
from functools import wraps
from flask import request, jsonify


class RateLimiter:
    """Rate limiter simples em memória por IP."""

    def __init__(self, max_requests=60, window_seconds=60):
        self.max_requests = max_requests
        self.window = window_seconds
        self._requests = defaultdict(list)
        self._lock = threading.Lock()

    def is_allowed(self, ip):
        now = time.time()
        with self._lock:
            # Limpa requests antigos
            self._requests[ip] = [
                t for t in self._requests[ip] if now - t < self.window
            ]
            if len(self._requests[ip]) >= self.max_requests:
                return False
            self._requests[ip].append(now)
            return True

    def get_remaining(self, ip):
        now = time.time()
        with self._lock:
            recent = [t for t in self._requests[ip] if now - t < self.window]
            return max(0, self.max_requests - len(recent))


# Instância global: 60 requests por minuto por IP
limiter = RateLimiter(max_requests=60, window_seconds=60)

# Limite mais restritivo para endpoints sensíveis
strict_limiter = RateLimiter(max_requests=10, window_seconds=60)


def rate_limit(strict=False):
    """Decorator para rate limiting."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            ip = request.remote_addr or 'unknown'
            target = strict_limiter if strict else limiter
            if not target.is_allowed(ip):
                remaining = target.get_remaining(ip)
                return jsonify({
                    'error': 'Rate limit exceeded',
                    'retry_after': 60,
                    'remaining': remaining,
                }), 429
            return f(*args, **kwargs)
        return wrapper
    return decorator
