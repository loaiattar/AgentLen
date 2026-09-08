"""HTTP interface: FastAPI routers, Pydantic schemas, dependency wiring.

This is the only layer allowed to import `infrastructure` — `import-linter`
enforces it. Everything below here talks to ports, never to adapters.
"""
