####################################
# Multi-stage Dockerfile for Flink CDC Gateway
# Optimized for CI/CD pipeline
####################################

# Stage 1: Build Python package
FROM python:3.9-slim AS builder

WORKDIR /app

# Copy project files
COPY . .

# Install build dependencies
RUN pip install --no-cache-dir build wheel

# Build the Python package
RUN python -m build

# Stage 2: Build final image
FROM flink:1.17.1-scala_2.12-java11

# Set maintainer information
LABEL maintainer="MosheEliya <mosiko1234@gmail.com>"
LABEL description="Apache Flink CDC Gateway for OpenShift environments"
LABEL version="0.7.0"

# Environment variables
ENV FLINK_VERSION=1.17.1 \
    FLINK_CDC_VERSION=3.0.0 \
    KAFKA_VERSION=3.3.2 \
    MSSQL_CONNECTOR_VERSION=11.2.1.jre11 \
    TZ=UTC

# Switch to root for installations
USER root

# Install necessary utilities
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        wget \
        unzip \
        netcat \
        jq \
        python3 \
        python3-pip \
        python3-venv && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create necessary directories
RUN mkdir -p /opt/flink/plugins/cdc/lib && \
    mkdir -p /opt/flink-cdc/scripts && \
    mkdir -p /opt/flink-cdc/config && \
    mkdir -p /opt/flink-cdc/pipelines

# Download and install Flink CDC connectors
RUN cd /tmp && \
    wget -q https://repo1.maven.org/maven2/org/apache/flink/flink-sql-connector-kafka/${FLINK_VERSION}/flink-sql-connector-kafka-${FLINK_VERSION}.jar -O /opt/flink/plugins/cdc/lib/flink-sql-connector-kafka-${FLINK_VERSION}.jar && \
    wget -q https://repo1.maven.org/maven2/com/microsoft/sqlserver/mssql-jdbc/${MSSQL_CONNECTOR_VERSION}/mssql-jdbc-${MSSQL_CONNECTOR_VERSION}.jar -O /opt/flink/plugins/cdc/lib/mssql-jdbc-${MSSQL_CONNECTOR_VERSION}.jar && \
    wget -q https://repo1.maven.org/maven2/org/apache/flink/flink-json/${FLINK_VERSION}/flink-json-${FLINK_VERSION}.jar -O /opt/flink/plugins/cdc/lib/flink-json-${FLINK_VERSION}.jar && \
    wget -q https://repo1.maven.org/maven2/com/ververica/flink-sql-connector-sqlserver-cdc/${FLINK_CDC_VERSION}/flink-sql-connector-sqlserver-cdc-${FLINK_CDC_VERSION}.jar -O /opt/flink/plugins/cdc/lib/flink-sql-connector-sqlserver-cdc-${FLINK_CDC_VERSION}.jar

# Create Python virtual environment
RUN python3 -m venv /opt/flink-cdc/venv

# Copy the built package from builder stage
COPY --from=builder /app/dist/*.whl /tmp/

# Install our Python package and dependencies
RUN /opt/flink-cdc/venv/bin/pip install --no-cache-dir /tmp/*.whl && \
    rm /tmp/*.whl

# Copy scripts and config files
COPY scripts/*.sh /opt/flink-cdc/scripts/
COPY config/* /opt/flink-cdc/config/

# Make scripts executable
RUN chmod +x /opt/flink-cdc/scripts/*.sh

# Create non-root user for OpenShift compatibility
RUN groupadd -r cdcuser -g 1000 && \
    useradd -r -g cdcuser -u 1000 -d /home/cdcuser cdcuser && \
    mkdir -p /home/cdcuser && \
    chown -R cdcuser:cdcuser /home/cdcuser && \
    chown -R cdcuser:cdcuser /opt/flink-cdc && \
    chown -R cdcuser:cdcuser /opt/flink/plugins/cdc

# Create log directory with correct permissions
RUN mkdir -p /opt/flink/log && \
    chown -R cdcuser:cdcuser /opt/flink/log

# Set working directory
WORKDIR /opt/flink-cdc

# Expose ports for CDC Gateway API and admin interface
EXPOSE 8084 8085

# Set environment variables for the application
ENV CDC_GATEWAY_PORT=8084 \
    CDC_GATEWAY_ADMIN_PORT=8085 \
    FLINK_JOBMANAGER_HOST=flink-jobmanager \
    FLINK_JOBMANAGER_PORT=6123 \
    PATH="/opt/flink-cdc/venv/bin:${PATH}"

# Switch to non-root user
USER cdcuser

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD /opt/flink-cdc/scripts/health-check.sh

# Entry point
ENTRYPOINT ["/opt/flink-cdc/scripts/start-cdc-gateway.sh"]