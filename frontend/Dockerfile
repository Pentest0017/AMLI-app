ARG NODE_IMAGE=node:22-slim
FROM ${NODE_IMAGE} AS builder
ARG NODE_BUILD_HEAP_MB=8192
ENV NODE_OPTIONS="--max-old-space-size=${NODE_BUILD_HEAP_MB}"
WORKDIR /app

ENV PUBLIC_BACKEND_API_URL=foo

COPY package*.json ./
COPY . .
RUN rm -rf .svelte-kit build node_modules
RUN npm install -g pnpm
RUN pnpm install --frozen-lockfile
RUN pnpm run build
RUN pnpm prune

ARG NODE_IMAGE=node:22-slim
FROM ${NODE_IMAGE}
ENV NODE_OPTIONS="--max-old-space-size=10240"
WORKDIR /app
COPY --from=builder /app/build build/
COPY --from=builder /app/server server/
COPY --from=builder /app/node_modules node_modules/
COPY package.json .
EXPOSE 3000
ENV NODE_ENV=production
ENV BODY_SIZE_LIMIT=25000000

RUN groupadd -g 1001 app && useradd -u 1001 -g 1001 -m -s /bin/bash app
# USER app  # not activated by default to keep compatibility

CMD [ "node", "server" ]
