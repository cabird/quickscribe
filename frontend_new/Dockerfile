FROM node:18-alpine

WORKDIR /app

# Install dependencies first
COPY package*.json ./
RUN npm cache clean --force
RUN npm install --verbose

# Verify react-icons installation
RUN npm list react-icons || (echo "react-icons not found, installing manually" && npm install react-icons@^5.5.0)

# Copy source code
COPY . .

# Sync models if needed
RUN npm run sync-models || echo "sync-models failed, continuing..."

# Expose port
EXPOSE 3000

# Start development server
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]