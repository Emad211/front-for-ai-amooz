# --- build stage ---
FROM registry.hamravesh.com/library/node:20-slim AS builder

WORKDIR /app
COPY package*.json ./

RUN npm install
COPY . .
RUN npm run build

# --- production stage ---
FROM registry.hamravesh.com/library/node:20-slim AS runner

WORKDIR /app
COPY --from=builder /app ./

EXPOSE 3000
CMD ["npm", "start"]
