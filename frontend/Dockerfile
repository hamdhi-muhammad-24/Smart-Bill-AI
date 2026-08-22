# Stage 1 — build the React app
FROM node:20-alpine AS builder

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --prefer-offline

COPY . .

# API base URL and Azure AD configuration baked into JS bundle at build time
ARG VITE_API_BASE_URL=http://localhost:8000
ARG VITE_AZURE_CLIENT_ID=0d42d2c9-48a3-4924-980e-68c613f6737b
ARG VITE_AZURE_TENANT_ID=534253fc-dfb6-462f-b5ca-cbe81939f5ee

ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_AZURE_CLIENT_ID=$VITE_AZURE_CLIENT_ID
ENV VITE_AZURE_TENANT_ID=$VITE_AZURE_TENANT_ID

RUN npm run build

# Stage 2 — serve with nginx
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
