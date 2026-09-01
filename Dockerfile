# This creates a Docker image from a python:3.12-slim base image.
# The python:3.12 is a Docker image that provides a minimal Linux environment
# (typically based on Debian Buster, Bullseye, or bookworm) pre-installed with
# Python 3.12. It's stripped of unnecessary compilation tools, development headers, 
# and extra packages to keep the footprint as light as possible.
FROM python:3.12-slim

# The ENV instruction sets the environment variable
# PYTHONDONTWRITEBYTECODE to 1, which prevents Python from writing .pyc files to disk.
# It also sets PYTHONUNBUFFERED to 1, which ensures that Python output is sent 
# straight to the terminal (stdout) without being buffered. This is useful for 
#logging and debugging purposes.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# The WORKDIR instruction sets the working directory to the /app
# directory inside of the container. If the directory doesn't exist
# it will be created. Then the subsequent commands will be run from the /app directory.
WORKDIR /app

# The COPY instruction copies the requirements.txt file from the host machine
# to the current working directory (which is /app) in the container.
# The RUN instruction uses a pip install commmand to install the 
# dependencies listed into the requirements.txt file. 
# The --no-cache-dir option is used to prevent pip from caching the packages,
# this can reduce the size of the Docker image. The --upgrade pip option is 
# used to ensure that pip is updated to the latest version before installing the 
# dependencies.
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# This COPY command will copy everything from the local build directory into the 
# /app directory in the container. This includes the application code,
# configuration files, and any other necessary files needed to run the application.
COPY . .

# The EXPOSE instruction informs the Docker that this container 
# will listen on the exposed port upon runtime. In this case,
# the application will listen on port 8000. This is a documentation feature
# and we can specify whether the port listens on TCP or UDP. By default, it's
# going to default to TCP. The EXPOSE instruction doesn't actually publish the port.
# It functions as a type of documentation between the person who builds the 
# image and the person who runs the container, about which ports are intended to 
# be published. To actually publish the port when running the container, you 
# would use the -p flag with docker run to map the container's port to a port on 
#the host machine.
EXPOSE 8000

# The CMD instruction specifies the command to run when the container starts.
# In this case, it runs the uvicorn server with the main:library_app application,
# and the --host specifying that the server should be available to all IP 
# addresses inside the container. The --port 8000 is going to set the network port
# to 8000 for incoming requests.
CMD ["uvicorn", "main:library_app", "--host", "0.0.0.0", "--port", "8000"]