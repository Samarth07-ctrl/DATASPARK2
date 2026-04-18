# ==============================================================================
# Frontend Dockerfile — Multi-stage build (Node build → Nginx serve)
# ==============================================================================
# WHY Nginx? CRA's `npm start` is a development server. In production we build
# static assets and serve them via Nginx for 10x better performance and security.
# ==============================================================================

# --- Build Stage ---
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --silent

COPY . .

# Build arg to inject the API URL at build time
ARG REACT_APP_API_URL=http://localhost:8000
ENV REACT_APP_API_URL=$REACT_APP_API_URL

RUN npm run build

# --- Production Stage ---
FROM nginx:alpine

# Copy the build output to Nginx's serve directory
COPY --from=builder /app/build /usr/share/nginx/html

# Custom Nginx config for SPA routing (React Router)
RUN echo 'server { \
    listen 80; \
    location / { \
        root /usr/share/nginx/html; \
        index index.html; \
        try_files $uri $uri/ /index.html; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
