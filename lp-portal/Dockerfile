# ----------- Build Stage ------------
FROM node:20-alpine AS builder

# Install system deps (if any fonts / sharp are needed)
RUN apk add --no-cache libc6-compat

WORKDIR /app

# Install dependencies based on lockfile first for better caching
COPY package.json package-lock.json* pnpm-lock.yaml* yarn.lock* ./
RUN npm ci --prefer-offline --no-audit --progress=false

# Copy source and build
COPY . .
RUN npm run build

# ----------- Production Stage ------------
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production

# Copy built assets & minimal deps
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/package.json ./package.json
# Only production dependencies
RUN npm install --omit=dev --prefer-offline --no-audit --progress=false

EXPOSE 3000
CMD ["npm", "start"]
