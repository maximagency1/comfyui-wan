# RunPod Serverless Setup

This Docker image now supports both **regular pods** and **RunPod Serverless**.

## Usage Modes

### 1. Regular Pod (Default)
Uses `/start_script.sh` - starts ComfyUI on port 8188 for direct HTTP access.

### 2. Serverless Mode
Uses `/start_serverless.sh` - starts ComfyUI + RunPod handler for serverless execution.

## Deploy to RunPod Serverless

### Step 1: Build and Push Image

```bash
# Build the image
docker build -t maximagency1/comfyui-wan:latest .

# Push to Docker Hub
docker push maximagency1/comfyui-wan:latest
```

### Step 2: Create Serverless Endpoint

1. Go to [RunPod Serverless](https://www.runpod.io/console/serverless)
2. Click "New Endpoint"
3. Configure:
   - **Docker Image**: `maximagency1/comfyui-wan:latest`
   - **Docker Command**: `/start_serverless.sh` (IMPORTANT!)
   - **GPU**: RTX 4090 or A40
   - **Container Disk**: 20GB+
   - **Timeout**: 900s (15 min)
   - **Max Workers**: 10
   - **Idle Timeout**: 5s (scales to zero quickly)

### Step 3: Get Endpoint ID

After creation, copy your endpoint ID (e.g., `abc123xyz`)

## API Usage

### Input Format

```json
{
  "input": {
    "image_url": "https://example.com/image.jpg",
    "video_url": "https://example.com/video.mp4",
    "workflow": {
      "311": {
        "class_type": "LoadImage",
        "inputs": {"image": "placeholder"}
      },
      "417": {
        "class_type": "VHS_LoadVideo",
        "inputs": {"video": "placeholder"}
      }
      // ... rest of your ComfyUI workflow
    },
    "cloudinary": {
      "cloud_name": "your-cloud",
      "api_key": "your-key",
      "api_secret": "your-secret"
    }
  }
}
```

### Call from Node.js

```javascript
const axios = require('axios');

async function processVideo(imageUrl, videoUrl, workflow) {
  const response = await axios.post(
    'https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/runsync',
    {
      input: {
        image_url: imageUrl,
        video_url: videoUrl,
        workflow: workflow,
        cloudinary: {
          cloud_name: process.env.CLOUDINARY_CLOUD_NAME,
          api_key: process.env.CLOUDINARY_API_KEY,
          api_secret: process.env.CLOUDINARY_API_SECRET
        }
      }
    },
    {
      headers: {
        'Authorization': `Bearer ${process.env.RUNPOD_API_KEY}`,
        'Content-Type': 'application/json'
      },
      timeout: 900000 // 15 min
    }
  );

  return response.data.output;
}
```

### Response Format

```json
{
  "id": "job-id",
  "status": "COMPLETED",
  "output": {
    "output_url": "https://res.cloudinary.com/...",
    "filename": "AnimateDiff_00001.mp4",
    "duration": 123,
    "status": "success"
  }
}
```

## Testing Locally

### Test Regular Mode
```bash
docker run --gpus all -p 8188:8188 maximagency1/comfyui-wan:latest
# Access ComfyUI at http://localhost:8188
```

### Test Serverless Mode
```bash
docker run --gpus all -p 8188:8188 maximagency1/comfyui-wan:latest /start_serverless.sh
# Handler will start and wait for RunPod jobs
```

## Cost Comparison

### On-Demand Pods
- $0.50/hr × 24hr = **$12/day per GPU**
- Billed even when idle

### Serverless
- Only pay for actual processing time
- Example: 100 jobs × 5min = **$4.17/day**
- **Zero cost when idle**

## Workflow JSON

The handler automatically updates these nodes:
- `LoadImage` nodes - Sets uploaded image filename
- `VHS_LoadVideo` nodes - Sets uploaded video filename

Your workflow JSON should have these node types with correct `class_type` fields.

## Troubleshooting

### Handler not starting
- Check Docker command is set to `/start_serverless.sh`
- Verify image has RunPod SDK installed
- Check logs for ComfyUI startup errors

### Jobs timing out
- Increase timeout in endpoint settings
- Check GPU has enough VRAM
- Verify workflow is optimized

### Cold starts too slow
- Use GPU with faster startup (A40 < RTX 4090)
- Increase min workers to keep 1 warm
- Optimize Docker image size
