from dataclasses import dataclass
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from functools import lru_cache
from dotenv import load_dotenv
from replicate import Client
import requests
import asyncio
import logging
import os

# Configure logging
logger = logging.getLogger(__name__)
load_dotenv()

# Settings management
class Settings(BaseModel):
    """Application settings with API configurations"""
    PIKAPI_BASE_URL: str = "https://api.pikapikapika.io/web"
    PIKAPI_BEARER_TOKEN: str = Field(default_factory=lambda: os.getenv("PIKAPI_BEARER_TOKEN"))
    REPLICATE_API_TOKEN: str = Field(default_factory=lambda: os.getenv("REPLICATE_API_TOKEN"))
    REPLICATE_MODEL_ID: str = "pharmapsychotic/clip-interrogator:8151e1c9f47e696fa316146a2e35812ccf79cfc9eba05b11c7f450155102af70"
    MAX_CHECK_TIME: int = 420  # 7 minutes
    INITIAL_WAIT_TIME: int = 300  # 5 minutes
    
    class Config:
        validate_default = True

    @property
    def is_valid(self) -> bool:
        return bool(self.PIKAPI_BEARER_TOKEN and self.REPLICATE_API_TOKEN)

@lru_cache()
def get_settings() -> Settings:
    """Get settings with validation and caching"""
    settings = Settings()
    if not settings.is_valid:
        raise ValueError("Missing required API tokens. Check your .env file.")
    return settings

# Request/Response Models
class VideoRequest(BaseModel):
    """Request model for video generation"""
    image_id: str = Field(..., description="URL of the image to animate")

class VideoResponse(BaseModel):
    """Response model for video generation"""
    media_id: str = Field(..., description="URL of the generated video")

class ErrorResponse(BaseModel):
    """Standard error response model"""
    detail: str

# External service clients
@dataclass
class ReplicateClient:
    """Client for Replicate API interactions"""
    _api_token: str
    _model_id: str

    async def generate_prompt(self, image: str) -> Optional[str]:
        """Generate a prompt from an image using CLIP interrogator"""
        try:
            client = Client(api_token=self._api_token)
            prompt = client.run(
                self._model_id,
                input={
                    "image": image,
                    "clip_model_name": "ViT-L-14/openai",
                    "mode": "fast"
                }
            )
            return prompt or ""
        except Exception as e:
            logger.error(f"Prompt generation failed: {str(e)}")
            return None

@dataclass
class PikapiClient:
    """Client for Pikapi API interactions"""
    _base_url: str
    _bearer_token: str
    _max_check_time: int
    _initial_wait_time: int

    async def initiate_generation(self, params: Dict[str, Any]) -> Optional[str]:
        """Initiate video generation"""
        try:
            response = requests.post(
                f"{self._base_url}/generate",
                json=params,
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()['job']['id']
        except Exception as e:
            logger.error(f"Video generation initiation failed: {str(e)}")
            return None

    async def check_status(self, job_id: str) -> Optional[str]:
        """Check job status and return video URL when complete"""
        try:
            # Initial wait before checking
            await asyncio.sleep(self._initial_wait_time)
            
            start_time = asyncio.get_event_loop().time()
            while True:
                if asyncio.get_event_loop().time() - start_time > self._max_check_time:
                    raise RuntimeError("Video generation timed out")

                response = requests.get(
                    f"{self._base_url}/jobs/{job_id}",
                    headers=self._get_headers()
                )
                response.raise_for_status()
                
                job_data = response.json()
                status = job_data['videos'][0]['status']
                logger.info(f"Job {job_id} status: {status}")

                if status == "finished":
                    return job_data['videos'][0]['resultUrl']
                elif status in ["queued", "pending"]:
                    await asyncio.sleep(10)
                else:
                    raise RuntimeError(f"Job failed: {status}")

        except Exception as e:
            logger.error(f"Status check failed for job {job_id}: {str(e)}")
            return None

    def _get_headers(self) -> Dict[str, str]:
        """Get common headers for API requests"""
        return {
            "Authorization": f"Bearer {self._bearer_token}",
            "Content-Type": "application/json"
        }

# Business Logic
@dataclass
class VideoGenerator:
    """Core business logic for video generation"""
    _replicate_client: ReplicateClient
    _pikapi_client: PikapiClient

    async def generate(self, image: str) -> Optional[str]:
        """Generate video from image URL"""
        try:
            # Generate prompt from image
            prompt = await self._replicate_client.generate_prompt(image)
            if not prompt:
                raise RuntimeError("Failed to generate prompt")

            # Prepare generation parameters
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

            # Start generation job
            job_id = await self._pikapi_client.initiate_generation(params)
            if not job_id:
                raise RuntimeError("Failed to initiate video generation")
            
            logger.info(f"Generation job started: {job_id}")

            # Wait for completion and get result
            video_url = await self._pikapi_client.check_status(job_id)
            if not video_url:
                raise RuntimeError("Failed to get video URL")

            return video_url

        except Exception as e:
            logger.error(f"Video generation failed: {str(e)}")
            return None

# FastAPI Application Setup
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize application dependencies"""
    settings = get_settings()

    # Initialize clients
    replicate_client = ReplicateClient(
        _api_token=settings.REPLICATE_API_TOKEN,
        _model_id=settings.REPLICATE_MODEL_ID
    )

    pikapi_client = PikapiClient(
        _base_url=settings.PIKAPI_BASE_URL,
        _bearer_token=settings.PIKAPI_BEARER_TOKEN,
        _max_check_time=settings.MAX_CHECK_TIME,
        _initial_wait_time=settings.INITIAL_WAIT_TIME
    )

    # Initialize video generator
    app.state.video_generator = VideoGenerator(
        _replicate_client=replicate_client,
        _pikapi_client=pikapi_client
    )

    yield

app = FastAPI(
    title="I-2-V API",
    description="A wrapper API for Replicate & Pika",
    version="1.0.0",
    lifespan=lifespan,
)

# Endpoints
@app.post(
    "/api/v1/i2v",
    response_model=VideoResponse,
    responses={
        200: {"model": VideoResponse},
        500: {"model": ErrorResponse},
    },
)
async def generate_video(
    request: VideoRequest,
    generator: VideoGenerator = Depends(lambda: app.state.video_generator),
) -> VideoResponse:
    """Generate a video from an image URL"""
    video_url = await generator.generate(request.image_id)
    
    if not video_url:
        raise HTTPException(status_code=500, detail="Video generation failed")

    return VideoResponse(media_id=video_url)

@app.get("/")
async def read_root():
    """API root endpoint with documentation"""
    return {
        "message": "i2v",
        "description": "a wrapper api for replicate & pika ai",
        "endpoints": {
            "/api/v1/i2v": "post — video gen with image url",
            "/docs": "interactive docs"
        },
        "version": "1.0.0"
    }