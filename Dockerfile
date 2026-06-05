# Default to amd64 because some runtime wheels (e.g. gmsh) and the native
# CGAL build target only ship x86_64 Linux artifacts. Override with
# `--build-arg BUILD_PLATFORM=...` if you really need another arch.
ARG BUILD_PLATFORM=linux/amd64
FROM --platform=${BUILD_PLATFORM} python:3.11.13-slim AS base
WORKDIR /app

# Runtime dependencies (keep minimal)
# libglu1-mesa / libgl1 / libxrender1 / libxcursor1 / libxft2 / libxinerama1:
# the gmsh Python wheel dynamically links against OpenGL/GLU + X11 libs even
# for headless meshing, so they must be present or `import gmsh` fails with
# "libGLU.so.1: cannot open shared object file".
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        postgresql-client \
        git \
        libglu1-mesa \
        libgl1 \
        libgomp1 \
        libxrender1 \
        libxcursor1 \
        libxft2 \
        libxinerama1 && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /var/cache/apt/*

# Upgrade pip and install build dependencies
RUN pip install --upgrade pip setuptools wheel

COPY requirements.txt /app
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY . /app

# Make entrypoint executable
RUN chmod +x ./entrypoint.sh

# Optional: Build native detector in a builder stage and copy the binary
ARG BUILD_PLATFORM=linux/amd64
FROM --platform=${BUILD_PLATFORM} python:3.11.13-slim AS builder
WORKDIR /build

# Install build tools and native deps for CGAL/Eigen
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        git \
        libcgal-dev \
        libeigen3-dev && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /var/cache/apt/*

# Copy repository and run the native build script
COPY . /src
WORKDIR /src/app/geometry/volume_detection
RUN chmod +x build.sh || true
RUN ./build.sh

FROM base AS final
WORKDIR /app

# Runtime shared libraries the native detector links against.
# CGAL's exact arithmetic uses GMP/MPFR, so these must be present at runtime
# even though CGAL itself is largely header-only (compiled into the binary).
RUN apt-get update && \
    apt-get install -y --no-install-recommends libgmp10 libmpfr6 && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /var/cache/apt/*

# Copy compiled native binary if present
COPY --from=builder /src/bin/volume_detector /app/bin/volume_detector

# Expose environment variable pointing to the detector binary path
ENV VOLUME_DETECTOR_BIN=/app/bin/volume_detector

EXPOSE 5001
CMD ["/app/entrypoint.sh"]