FROM node:22.23.2-alpine3.24
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev \
    && rm -rf /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/corepack /opt/yarn-* \
    && rm -f /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/corepack \
       /usr/local/bin/yarn /usr/local/bin/yarnpkg
COPY server.js token.js authorization.js ./
USER node
CMD ["node", "server.js"]
