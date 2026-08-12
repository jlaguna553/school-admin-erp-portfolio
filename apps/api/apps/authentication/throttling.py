"""
Throttles for the credential endpoints.

Login and refresh are unauthenticated and accept guessable input, which makes
them the natural target for credential stuffing. Everything else in the API sits
behind a bearer token, so rate limiting is applied here rather than globally.

Scoping used to include the schema, back when the hostname named one before the
request was read. On a single domain there is no school at this point -- the
whole purpose of login is to find out which one -- so the address is all there
is to key on, and the per-account throttle below carries correspondingly more of
the weight.

That the address limit is now shared across institutions is a real consequence:
a busy school can eat into the budget of another behind the same NAT. It is why
the address limit is generous and the per-account one is not.
"""

from rest_framework.throttling import SimpleRateThrottle


class AddressScopedAnonThrottle(SimpleRateThrottle):
    """Base class keying on the client address alone."""

    def get_cache_key(self, request, view):  # noqa: ANN001, ANN201
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class LoginRateThrottle(AddressScopedAnonThrottle):
    """Caps login volume from a single address.

    Has to stay **generous**: a school's staff usually share one NAT egress
    address, so a whole staffroom signing in at the start of the day arrives as
    one client -- and on one domain, several schools may sit behind the same
    address. Set this near a human ceiling and it locks them all out at once.
    Per-account brute force is handled separately by
    :class:`LoginEmailRateThrottle`, which is where the tight limit belongs.
    """

    scope = "login"


class LoginEmailRateThrottle(SimpleRateThrottle):
    """Caps attempts against a single account.

    Keyed on the email rather than the client address, because that is the
    dimension brute force actually walks: one address may legitimately carry a
    whole school's logins, but nobody needs many attempts against one mailbox.
    Being IP-independent, it also holds when an attacker rotates addresses. The
    email is now unique platform-wide, so this key identifies exactly one
    account.
    """

    scope = "login_email"

    def get_cache_key(self, request, view):  # noqa: ANN001, ANN201
        email = (request.data or {}).get("email") if hasattr(request, "data") else None
        if not email:
            # No email to key on; the request will fail validation anyway.
            return None

        return self.cache_format % {
            "scope": self.scope,
            "ident": str(email).strip().lower(),
        }


class RefreshRateThrottle(AddressScopedAnonThrottle):
    """Caps refresh exchanges.

    Higher than login: a legitimate client refreshes on every access-token
    expiry, and several tabs may do so at once.
    """

    scope = "refresh"
