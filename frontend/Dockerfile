# ---------- build stage ----------
FROM node:20-slim AS builder

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

RUN npm run build


# ---------- production stage ----------
FROM node:20-slim AS runner

WORKDIR /app

ENV NODE_ENV=production

COPY --from=builder /app ./

RUN npm install --omit=dev

EXPOSE 3000

CMD ["npm","start"]
