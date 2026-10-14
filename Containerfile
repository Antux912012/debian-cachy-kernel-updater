FROM docker.io/library/debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential \
    bc \
    bison \
    flex \
    libssl-dev \
    libelf-dev \
    libncurses-dev \
    libdw-dev \
    libudev-dev \
    libpci-dev \
    libiberty-dev \
    autoconf \
    dwarves \
    pahole \
    zstd \
    xz-utils \
    lz4 \
    cpio \
    rsync \
    kmod \
    fakeroot \
    dpkg-dev \
    debhelper \
    devscripts \
    git \
    curl \
    wget \
    ca-certificates \
    python3 \
    python3-gi \
    python3-requests \
    clang \
    llvm \
    lld \
    sbsigntool \
    mokutil \
    openssl \
    && rm -rf /var/lib/apt/lists/*

ENV DEBFULLNAME="CachyOS Debian Builder"
ENV DEBEMAIL="builder@localhost"

WORKDIR /workspace
