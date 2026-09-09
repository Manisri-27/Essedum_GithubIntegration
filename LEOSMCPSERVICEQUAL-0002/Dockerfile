# Dockerfile for TMF 645 Service Qualification MCP Server
# mcp-servicequal.py

FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Copy requirements file
COPY mcp-servicequal-requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r mcp-servicequal-requirements.txt

# Copy the MCP server script
COPY mcp-servicequal.py .

# Expose MCP server port (5000)
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:5000/sse', timeout=5.0)" || exit 1

# Run the MCP server
CMD ["python", "mcp-servicequal.py"]
