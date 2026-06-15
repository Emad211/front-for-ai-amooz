# ---------- builder ----------
FROM node:20-slim AS builder

WORKDIR /app

# 1) تعریف Build Args
ARG NEXT_PUBLIC_API_URL
ARG BACKEND_URL

# 2) تبدیل به ENV تا Next.js در زمان build بخونه
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV BACKEND_URL=$BACKEND_URL

# 3) نصب وابستگی‌ها (retry برای شبکه/پروکسی ناپایدار)
COPY package*.json ./
RUN npm config set fetch-retries 10 \
 && npm config set fetch-retry-maxtimeout 180000 \
 && npm config set fetch-timeout 600000 \
 && npm install --no-audit --no-fund

# 4) کپی سورس
COPY . .

# 5) (اختیاری برای اطمینان) چاپ env در لاگ build
RUN echo "NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL" \
 && echo "BACKEND_URL=$BACKEND_URL"

# 6) build
RUN npm run build


# ---------- runner ----------
FROM node:20-slim AS runner

WORKDIR /app

ENV NODE_ENV=production

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000

CMD ["node", "server.js"]
