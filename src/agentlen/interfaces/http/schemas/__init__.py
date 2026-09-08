"""Pydantic schemas for the HTTP layer.

Deliberately separate from the domain entities: the wire format is allowed to
change without touching business rules, and a Pydantic model must never appear
in `domain/`.
"""
