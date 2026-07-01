# ---------- builder ----------
FROM node:20-slim AS builder

WORKDIR /app

# 1) نصب وابستگی‌ها ابتدا — این لایه فقط به package*.json وابسته است، پس تا وقتی
#    وابستگی‌ها عوض نشوند کش می‌ماند. (Build Argها پایین‌تر تعریف می‌شوند تا
#    تغییرِ مقدارشان دیگر باعثِ نصبِ دوبارهٔ کاملِ npm نشود.)
COPY package*.json ./
RUN npm config set fetch-retries 10 \
 && npm config set fetch-retry-maxtimeout 180000 \
 && npm config set fetch-timeout 600000 \
 && npm install --no-audit --no-fund

# 2) Build Args (بعد از نصبِ وابستگی‌ها؛ فقط لایهٔ build را باطل می‌کنند نه npm را)
ARG NEXT_PUBLIC_API_URL
ARG BACKEND_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV BACKEND_URL=$BACKEND_URL

# 3) کپی سورس و build
COPY . .
RUN echo "NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL" \
 && echo "BACKEND_URL=$BACKEND_URL"
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
