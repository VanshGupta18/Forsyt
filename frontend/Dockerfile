# Local-dev reproducibility only — build/run with Finch (or Docker) instead
# of a manual `npm install && npm run dev`. Does not change how this is
# hosted in production.
FROM node:20-slim

WORKDIR /app

COPY package.json package-lock.json .npmrc* ./
RUN npm ci

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
