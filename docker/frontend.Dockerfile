# syntax=docker/dockerfile:1
#
# The web interface, compiled once and served as static files.
#
# `build` compiles the SPA with the same Node major as CI. `runtime` ships only
# the compiled assets behind an unprivileged nginx, which also proxies `/api`
# to the `api` service: the browser talks to a single origin, so no CORS
# configuration is involved.

FROM node:20-alpine AS build

WORKDIR /app

# Dependencies first, so a source change does not invalidate the install layer.
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci

COPY frontend/ ./

# Vite inlines VITE_* variables at build time, not at runtime: the key the
# client sends as `X-API-Key` has to be known here. docker-compose.yml passes
# the `API_KEY` of the root `.env`, so it cannot drift from the backend's.
# An empty key would build an interface that gets a 401 on every call — fail
# the build instead of shipping that.
ARG VITE_API_KEY
RUN test -n "$VITE_API_KEY" \
    || { echo "VITE_API_KEY is empty: set API_KEY in .env" >&2; exit 1; }
ENV VITE_API_KEY=$VITE_API_KEY

RUN npm run build

# ---------------------------------------------------------------------------
FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime

# Rendered to /etc/nginx/conf.d/default.conf when the container starts; the
# image's entrypoint substitutes only variables that exist in the environment.
COPY docker/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080
