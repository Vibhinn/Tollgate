FROM python:3.14-slim

# cmake/git: needed at `tollgate init` time to clone and compile llama.cpp
# natively on this exact machine (see cli/steps/build_server.py) - avoids the
# whole class of cross-machine shared-library packaging bugs a prebuilt
# binary distribution model kept hitting.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        git \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin tollgate

WORKDIR /app
COPY pyproject.toml main.py ./
COPY cli/ ./cli/
COPY build/ ./build/
COPY src/ ./src/

RUN pip install --no-cache-dir .

ENV TOLLGATE_DATA_DIR=/data/intelligence
RUN mkdir -p /data && chown -R tollgate:tollgate /data /app
WORKDIR /data
VOLUME ["/data"]

USER tollgate

EXPOSE 13000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fs http://localhost:13000/docs || exit 1

COPY --chown=tollgate:tollgate docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
