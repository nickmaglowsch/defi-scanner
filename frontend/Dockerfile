# dev-only; for production replace with standalone output
FROM node:20-alpine
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
CMD ["npm", "run", "dev", "--", "-H", "0.0.0.0", "-p", "3000"]
