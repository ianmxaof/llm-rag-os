#!/bin/bash
# Intelligence OS Setup Script (Path A - Minimal)
# Creates minimal Docker setup for immediate intelligence feed

echo "========================================"
echo "  Intelligence OS - Minimal Setup"
echo "========================================"
echo ""

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INTEL_DIR="$PROJECT_ROOT/intelligence-data"

# Create directories
echo "[1/4] Creating directories..."
mkdir -p "$INTEL_DIR/n8n"
mkdir -p "$INTEL_DIR/out"
echo "  ✓ Directories created"
echo ""

# Check for .env.intelligence
echo "[2/4] Checking configuration..."
ENV_FILE="$PROJECT_ROOT/.env.intelligence"
if [ ! -f "$ENV_FILE" ]; then
    echo "  ⚠ .env.intelligence not found"
    echo "  → Creating from template..."
    cp "$PROJECT_ROOT/.env.intelligence.example" "$ENV_FILE"
    echo "  ✓ Template created at: $ENV_FILE"
    echo "  → Please edit .env.intelligence and add your API keys"
    echo ""
else
    echo "  ✓ Configuration file found"
    echo ""
fi

# Check Docker
echo "[3/4] Checking Docker..."
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version)
    echo "  ✓ Docker is available: $DOCKER_VERSION"
else
    echo "  ❌ Docker not found. Please install Docker"
    exit 1
fi
echo ""

# Instructions
echo "[4/4] Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit .env.intelligence and add your API keys"
echo "  2. Start services: docker compose -f docker/intelligence-minimal.yml up -d"
echo "  3. Open N8N: http://localhost:5678 (admin / changeme)"
echo "  4. Import the workflow JSON (provided separately)"
echo "  5. Link output folder:"
echo "     ln -s \"$INTEL_DIR/out\" \"knowledge/inbox/intelligence-feed\""
echo ""
echo "To pause: docker compose -f docker/intelligence-minimal.yml pause"
echo "To stop:  docker compose -f docker/intelligence-minimal.yml stop"
echo ""

