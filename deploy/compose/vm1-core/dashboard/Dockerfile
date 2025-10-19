FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package.json .

# Install dependencies
RUN npm install --production

# Copy application
COPY server.js .
COPY public/ ./public/

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000/health || exit 1

# Run
EXPOSE 3000
CMD ["node", "server.js"]
