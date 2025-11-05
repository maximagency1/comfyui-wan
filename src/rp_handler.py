"""
RunPod Serverless Handler for WanAnimate ComfyUI Workflow
Processes image + video inputs through ComfyUI and returns generated video
"""

import runpod
import requests
import json
import os
import time
import base64
from pathlib import Path
from typing import Dict, Any, Optional
import websocket

# ComfyUI API client
class ComfyUIClient:
    def __init__(self, server_address="127.0.0.1:8188"):
        self.server_address = server_address
        self.client_id = str(int(time.time()))
        
    def upload_file(self, file_path: str, file_type: str = "input") -> str:
        """Upload a file to ComfyUI and return the filename"""
        url = f"http://{self.server_address}/upload/image"
        
        # Determine mime type based on file extension
        filename = os.path.basename(file_path)
        if filename.lower().endswith(('.mp4', '.avi', '.mov', '.webm')):
            mime_type = 'video/mp4'
        else:
            mime_type = 'image/jpeg'
        
        with open(file_path, 'rb') as f:
            files = {'image': (filename, f, mime_type)}
            data = {'type': file_type, 'subfolder': ''}
            response = requests.post(url, files=files, data=data)
            
        if response.status_code != 200:
            raise Exception(f"Upload failed: {response.text}")
            
        return response.json()['name']
    
    def queue_prompt(self, workflow: Dict) -> str:
        """Queue a prompt and return the prompt ID"""
        url = f"http://{self.server_address}/prompt"
        payload = {"prompt": workflow, "client_id": self.client_id}
        
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            raise Exception(f"Queue failed: {response.text}")
            
        return response.json()['prompt_id']
    
    def get_history(self, prompt_id: str) -> Optional[Dict]:
        """Get the history for a prompt ID"""
        url = f"http://{self.server_address}/history/{prompt_id}"
        response = requests.get(url)
        
        if response.status_code != 200:
            return None
            
        history = response.json()
        return history.get(prompt_id)
    
    def wait_for_completion(self, prompt_id: str, timeout: int = 900) -> str:
        """Wait for prompt to complete and return output filename"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            history = self.get_history(prompt_id)
            
            if history and 'outputs' in history:
                # Find the output video
                for node_id, node_output in history['outputs'].items():
                    if 'gifs' in node_output:
                        return node_output['gifs'][0]['filename']
                    elif 'videos' in node_output:
                        return node_output['videos'][0]['filename']
                        
            time.sleep(2)
        
        raise TimeoutError(f"Prompt {prompt_id} did not complete within {timeout}s")
    
    def download_output(self, filename: str, output_path: str):
        """Download the output file from ComfyUI"""
        url = f"http://{self.server_address}/view?filename={filename}&subfolder=&type=output"
        response = requests.get(url)
        
        if response.status_code != 200:
            raise Exception(f"Download failed: {response.text}")
            
        with open(output_path, 'wb') as f:
            f.write(response.content)


def upload_to_cloudinary(file_path: str, cloudinary_config: Dict) -> str:
    """Upload file to Cloudinary and return URL"""
    import cloudinary
    import cloudinary.uploader
    
    cloudinary.config(
        cloud_name=cloudinary_config['cloud_name'],
        api_key=cloudinary_config['api_key'],
        api_secret=cloudinary_config['api_secret']
    )
    
    result = cloudinary.uploader.upload(
        file_path,
        resource_type='video',
        folder='comfyui-videos'
    )
    
    return result['secure_url']


def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main handler function for RunPod Serverless
    
    Expected input:
    {
        "image_url": "https://...",
        "video_url": "https://...",  # Optional
        "workflow": {...}  # ComfyUI workflow JSON
    }
    
    Returns:
    {
        "output_url": "https://...",  # Cloudinary URL (hardcoded credentials)
        "filename": "...",
        "duration": 123  # Processing time in seconds
    }
    """
    
    start_time = time.time()
    job_input = job['input']
    
    try:
        # Validate inputs
        if 'image_url' not in job_input:
            return {"error": "Missing required field: image_url"}
        if 'workflow' not in job_input:
            return {"error": "Missing required field: workflow"}
        
        print(f"📥 Processing job with image: {job_input['image_url']}")
        
        # Create temp directory
        temp_dir = Path("/tmp/comfyui_job")
        temp_dir.mkdir(exist_ok=True)
        
        # Download image
        print("📥 Downloading image...")
        image_path = temp_dir / "input_image.jpg"
        image_response = requests.get(job_input['image_url'])
        image_response.raise_for_status()
        image_path.write_bytes(image_response.content)
        print(f"✅ Downloaded image ({len(image_response.content)} bytes)")
        
        # Download video if provided
        video_path = None
        if 'video_url' in job_input and job_input['video_url']:
            print("📥 Downloading video...")
            video_path = temp_dir / "input_video.mp4"
            video_response = requests.get(job_input['video_url'])
            video_response.raise_for_status()
            video_path.write_bytes(video_response.content)
            print(f"✅ Downloaded video ({len(video_response.content)} bytes)")
        
        # Initialize ComfyUI client
        client = ComfyUIClient()
        
        # Upload files to ComfyUI
        print("📤 Uploading files to ComfyUI...")
        uploaded_image = client.upload_file(str(image_path), "input")
        print(f"✅ Uploaded image as: {uploaded_image}")
        
        uploaded_video = None
        if video_path:
            uploaded_video = client.upload_file(str(video_path), "input")
            print(f"✅ Uploaded video as: {uploaded_video}")
        
        # Update workflow with uploaded filenames
        workflow = job_input['workflow'].copy()
        
        # Find and update the image/video nodes (adjust node IDs as needed)
        # Common node IDs: "311" for LoadImage, "417" for VHS_LoadVideo
        for node_id, node_data in workflow.items():
            if node_data.get('class_type') == 'LoadImage':
                node_data['inputs']['image'] = uploaded_image
            elif node_data.get('class_type') == 'VHS_LoadVideo':
                if uploaded_video:
                    node_data['inputs']['video'] = uploaded_video
        
        # Queue the prompt
        print("🎬 Queuing prompt to ComfyUI...")
        prompt_id = client.queue_prompt(workflow)
        print(f"✅ Prompt queued: {prompt_id}")
        
        # Wait for completion
        print("⏳ Waiting for ComfyUI to process...")
        output_filename = client.wait_for_completion(prompt_id, timeout=900)
        print(f"✅ Processing complete: {output_filename}")
        
        # Download output
        print("📥 Downloading output...")
        output_path = temp_dir / output_filename
        client.download_output(output_filename, str(output_path))
        print(f"✅ Downloaded output ({output_path.stat().st_size} bytes)")
        
        # Upload to Cloudinary (using hardcoded credentials)
        print("☁️  Uploading to Cloudinary...")
        cloudinary_config = {
            'cloud_name': 'dwt1ebvwe',
            'api_key': '189877928833532',
            'api_secret': 'DYZR0Y-1MH9EO6DkjiojyQPaN8c'
        }
        output_url = upload_to_cloudinary(str(output_path), cloudinary_config)
        print(f"✅ Uploaded to Cloudinary: {output_url}")
        
        # Calculate duration
        duration = int(time.time() - start_time)
        
        # Cleanup
        print("🧹 Cleaning up temp files...")
        for file in temp_dir.glob("*"):
            file.unlink()
        
        return {
            "output_url": output_url,
            "filename": output_filename,
            "duration": duration,
            "status": "success"
        }
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            "error": str(e),
            "status": "failed",
            "duration": int(time.time() - start_time)
        }


# Start the RunPod serverless worker
if __name__ == "__main__":
    print("🚀 Starting RunPod Serverless Worker for WanAnimate...")
    runpod.serverless.start({"handler": handler})
