"""
Rate limiter instance (slowapi / limits).

Import `limiter` wherever you need @limiter.limit() on a route.
The limiter is attached to app.state in main.py.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

# Key function: rate limit per IP address.
# For authenticated routes, swap to a user-ID key function if per-user limits are needed.
limiter = Limiter(key_func=get_remote_address)
