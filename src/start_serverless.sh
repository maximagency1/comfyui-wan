#!/bin/bash

# Start script for RunPod Serverless
echo "🚀 Starting ComfyUI for RunPod Serverless..."

# Start ComfyUI in the background
cd /ComfyUI
python main.py --listen 0.0.0.0 --port 8188 &

# Wait for ComfyUI to be ready
echo "⏳ Waiting for ComfyUI to start..."
sleep 15

# Check if ComfyUI is running
if curl -s http://localhost:8188 > /dev/null; then
    echo "✅ ComfyUI is running"
else
    echo "❌ ComfyUI failed to start"
    exit 1
fi

# Start RunPod handler
echo "🎯 Starting RunPod Serverless handler..."
python /rp_handler.py
