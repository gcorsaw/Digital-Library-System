# =========================================
# Stage 1: Build the Angular Application
# =========================================

# =========================================
# Use a lightweight DHI Node.js image for building (from the guide)
# This is also the base image for the Dockerfile (reviewing from the guide)
# The Docker Hardened Image (DHI) is going to provide minimal, secured, 
# and production-ready container images, so in this particular case,
# The node:24-alpine3.22-dev is going to be image and it's
# the AS of the command is going to give the build stage
# the name of builder. Later on, the --from=builder refers
# to the stage.
# =========================================
FROM dhi.io/node:24-alpine3.22-dev AS builder

# Set the working directory inside the container
WORKDIR /app

# Copy package-related files first to leverage Docker's caching mechanism
COPY package.json package-lock.json* ./

# Install project dependencies using npm ci (ensures a clean, reproducible install)
RUN --mount=type=cache,target=/root/.npm npm ci

# Copy the rest of the application source code into the container
COPY . .

# Build the Angular application
RUN npm run build

# =========================================
# Stage 2: Prepare Nginx to Serve Static Files
# =========================================

# This particular FROM is going to have another base image that is going to
# use the same DHI as before, however the nginx:1.28.0-alpine3.21-dev is going
# to be the image that we're going to be building. It's going then the AS is going to have
# the the build the the image under the name of `runner`. 
FROM dhi.io/nginx:1.28.0-alpine3.21-dev AS runner

# Copy custom Nginx config
COPY nginx.conf /etc/nginx/nginx.conf

# Copy the static build output from the build stage to Nginx's default HTML serving directory
COPY --chown=nginx:nginx --from=builder /app/dist/*/browser /usr/share/nginx/html

# Use a non-root user for security best practices
USER nginx

# Expose port 8080 to allow HTTP traffic
# Note: The default Nginx container now listens on port 8080 instead of 80
EXPOSE 8080

# Start Nginx directly with custom config
ENTRYPOINT ["nginx", "-c", "/etc/nginx/nginx.conf"]
CMD ["-g", "daemon off;"]