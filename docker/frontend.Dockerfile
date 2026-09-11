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

# No API key at build time: Vite inlines every VITE_* variable into the bundle
# any visitor can read. nginx adds `X-API-Key` at runtime instead (#149).
RUN npm run build

# ---------------------------------------------------------------------------
FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime

# The image's entrypoint runs /docker-entrypoint.d/*.sh in order before nginx
# starts: this one refuses to start without the API_KEY that nginx adds to
# every `/api` call, before the template below is rendered.
COPY --chmod=0755 docker/nginx-require-api-key.sh /docker-entrypoint.d/05-require-api-key.sh

# Rendered to /etc/nginx/conf.d/default.conf when the container starts; the
# image's entrypoint substitutes only variables that exist in the environment.
COPY docker/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080
