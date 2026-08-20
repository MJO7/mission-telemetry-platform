# syntax=docker/dockerfile:1
#
# VITE_API_BASE_URL is baked into the JS bundle at BUILD time (Vite
# inlines import.meta.env.* at build, not runtime) -- there is no
# "restart the pod with a new env var" for a static SPA. That means the
# image is environment-specific: a build for the k3d demo cluster is a
# different image than one for anywhere else the API lives. Real
# tradeoff of the static-SPA-behind-nginx pattern, not an oversight --
# the alternative (fetch config.json at runtime before rendering) is a
# legitimate fix this project doesn't need yet at one deployment target.
FROM node:22-alpine AS builder
WORKDIR /app
COPY package*.json ./
# --legacy-peer-deps: openapi-typescript peer-depends on TypeScript ^5.x
# while this project pins ~6.0.2 (see docs/adr/0005) -- same fix as
# local dev, just needed again here since npm ci enforces the lockfile
# strictly.
RUN npm ci --legacy-peer-deps
COPY . .
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

# nginx-unprivileged: listens on 8080 and runs as a non-root UID out of
# the box -- the plain nginx image binds :80, which needs root, which
# is exactly the kind of "works locally, fails a k8s PodSecurityPolicy/
# SecurityContext that forbids root" gap not worth having here.
FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 8080
