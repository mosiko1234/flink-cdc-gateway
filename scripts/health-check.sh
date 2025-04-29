# scripts/health-check.sh
#!/bin/bash

# Health check script for CDC Gateway
if curl -s -f http://localhost:${CDC_GATEWAY_ADMIN_PORT}/health > /dev/null; then
  exit 0
else
  exit 1
fi