import os
import requests
import asyncio
from replicate import Client
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.pikapikapika.io/web"
PIKAPI_BEARER_TOKEN = os.getenv("PIKAPI_BEARER_TOKEN")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

if not PIKAPI_BEARER_TOKEN or not REPLICATE_API_TOKEN:
    raise ValueError("Missing API tokens. Please check your .env file.")

# FastAPI App
app = FastAPI()

class VideoRequestBody(BaseModel):
    image: str

async def generate_prompt(image: str) -> str:
    """Generate a prompt using the Replicate API."""
    try:
        replicate = Client(api_token=REPLICATE_API_TOKEN)
        prompt = replicate.run(
            "pharmapsychotic/clip-interrogator:8151e1c9f47e696fa316146a2e35812ccf79cfc9eba05b11c7f450155102af70",
            input={"image": image, "clip_model_name": "ViT-L-14/openai"},
        )
        return prompt or ""
    except Exception as e:
        raise RuntimeError(f"Error generating prompt: {e}")


async def send_post_request(params: dict) -> str:
    """Send a POST request to initiate video generation."""
    url = f"{BASE_URL}/generate"
    headers = {
        "Authorization": f"Bearer {PIKAPI_BEARER_TOKEN}",
        "Content-Type": "application/json"
    }
    response = requests.post(url, json=params, headers=headers)
    if response.status_code == 200:
        return response.json()['job']['id']
    else:
        raise RuntimeError(f"POST request failed: {response.text}")

async def check_job_status(job_id: str) -> str:
    """Check the job status and return the video URL if finished."""
    url = f"{BASE_URL}/jobs/{job_id}"
    headers = {"Authorization": f"Bearer {PIKAPI_BEARER_TOKEN}"}
    
    start_time = asyncio.get_event_loop().time()
    max_check_time = 600
    
    while True:
        # Check if we've exceeded the maximum time
        current_time = asyncio.get_event_loop().time()
        if current_time - start_time > max_check_time:
            raise RuntimeError("Video generation timed out after 10 minutes")
            
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            job_data = response.json()
            status = job_data['videos'][0]['status']
            print(f"Current status: {status}")
            
            if status == "finished":
                return job_data['videos'][0]['resultUrl']
            elif status in ["queued", "pending"]:
                await asyncio.sleep(10)
            else:
                raise RuntimeError(f"Job failed with status: {status}")
        else:
            raise RuntimeError(f"GET request failed: {response.text}")

async def generate_video(image: str) -> str:
    """Main function to generate the video and return the video URL."""
    prompt = await generate_prompt(image)
    params = {
        "promptText": prompt,
        "model": "1.5",
        "image": image,
        "options": {
            "frameRate": 24,
            "parameters": {
                "motion": 2,
                "guidanceScale": 16
            },
        }
    }
    job_id = await send_post_request(params)
    print(f"Job ID: {job_id}")

    # Wait for 6 minutes (360 seconds)
    await asyncio.sleep(360)

    # Check job status after waiting
    video_url = await check_job_status(job_id)
    return video_url


@app.post("/i2v")
async def generate_video_endpoint(request: VideoRequestBody):
    """Endpoint to generate video from an image URL."""
    try:
        # Now you can directly access the image URL from the request
        image = request.image
        video_url = await generate_video(image)
        return {"video_url": video_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def read_root():
    return {
        "message": "i2v api",
        "description": "",
        "endpoints": {
            "/i2v": "POST - start video generation",
            "/docs": "Test out the API in SwaggerUI"
        },
        "version": "v0.1"
    }
