FROM node:24-bookworm-slim AS build
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@11.19.0 --activate
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
RUN pnpm build
ENV NODE_ENV=production HOST=0.0.0.0 PORT=4310
RUN mkdir -p /app/.data && chown node:node /app/.data
USER node
EXPOSE 4310
CMD ["node", "--import", "tsx", "server/index.ts"]
