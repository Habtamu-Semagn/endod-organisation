"""The integration API for companies' own systems (docs/integrations.md).

* :mod:`.scopes`: what a connection may do, with plain-language labels;
* :mod:`.jose`: compact JWS (ES256, RS256) and JWKs, on ``cryptography``;
* :mod:`.signing`: the service's key that signs access tokens;
* :mod:`.clients`: connections (secrets, public keys, address limits);
* :mod:`.tokens`: the token endpoint and access-token checks;
* :mod:`.data`: employees (upsert, deactivate), claims and payout batches;
* :mod:`.webhooks`: signed events to the company's system, with SSRF guards;
* :mod:`.ratelimit`: per-process sliding windows.

The HTTP side is app.api.integrations (the API) and app.api.connections (the
portal's "Connect your system").
"""
