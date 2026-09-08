"""Data transfer objects: what the read side hands back to the interfaces layer.

Deliberately distinct from `domain/model/`. Entities carry business rules and
identity; these carry numbers that have already been aggregated by the database.
Returning a `Session` from a dashboard query would mean loading thousands of
entities to compute one average — the thing the read side exists to avoid.
"""
