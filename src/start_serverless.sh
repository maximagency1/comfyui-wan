#!/usr/bin/env bash

# Start script for RunPod Serverless
echo "🚀 Starting ComfyUI for RunPod Serverless..."

# Use libtcmalloc for better memory management
TCMALLOC="$(ldconfig -p | grep -Po "libtcmalloc.so.\d" | head -n 1)"
export LD_PRELOAD="${TCMALLOC}"

# Set the network volume path
NETWORK_VOLUME="/workspace"
URL="http://127.0.0.1:8188"

# Check if NETWORK_VOLUME exists; if not, use root directory instead
if [ ! -d "$NETWORK_VOLUME" ]; then
    echo "NETWORK_VOLUME directory '$NETWORK_VOLUME' does not exist. Setting NETWORK_VOLUME to '/' (root directory)."
    NETWORK_VOLUME="/"
fi

COMFYUI_DIR="$NETWORK_VOLUME/ComfyUI"

# Move ComfyUI to network volume if needed
if [ ! -d "$COMFYUI_DIR" ]; then
    mv /ComfyUI "$COMFYUI_DIR"
else
    echo "ComfyUI directory already exists at $COMFYUI_DIR"
fi

# Start ComfyUI in the background
echo "▶️  Starting ComfyUI..."
cd "$COMFYUI_DIR"
nohup python3 main.py --listen --use-sage-attention > /tmp/comfyui_serverless.log 2>&1 &
COMFYUI_PID=$!

# Wait for ComfyUI to be ready
echo "⏳ Waiting for ComfyUI to start..."
counter=0
max_wait=60

until curl --silent --fail "$URL" --output /dev/null; do
    if [ $counter -ge $max_wait ]; then
        echo "❌ ComfyUI failed to start within ${max_wait}s"
        echo "📋 Check logs at: /tmp/comfyui_serverless.log"
        cat /tmp/comfyui_serverless.log
        exit 1
    fi
    
    echo "🔄 ComfyUI starting... (${counter}s / ${max_wait}s)"
    sleep 2
    counter=$((counter + 2))
done

echo "✅ ComfyUI is running at $URL"

# Start RunPod handler
echo "🎯 Starting RunPod Serverless handler..."
python3 /rp_handler.py
