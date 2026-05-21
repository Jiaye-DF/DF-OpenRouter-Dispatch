# ---- base ----
FROM node:22-alpine AS base
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY package.json package-lock.json ./
RUN npm ci

# ---- dev ----
FROM base AS dev
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]

# ---- builder ----
FROM base AS builder
COPY . .
RUN npm run build

# ---- prod ----
FROM node:22-alpine AS prod
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
EXPOSE 3000
CMD ["node", "server.js"]
