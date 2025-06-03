FROM node:18-alpine

WORKDIR /app

# Install build dependencies for native modules
RUN apk add --no-cache python3 make g++

# Enable corepack for Yarn 4
RUN corepack enable

# Copy Yarn 4 files
COPY .yarn ./.yarn
COPY .yarnrc.yml ./

# Copy package files
COPY package.json yarn.lock ./

# Install dependencies with yarn
RUN yarn install --immutable

# Copy source code
COPY . .

# Expose port
EXPOSE 3000

# Start development server
CMD ["yarn", "dev", "--host", "0.0.0.0"]