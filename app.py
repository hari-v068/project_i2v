from dataclasses import dataclass
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Header
from pydantic import BaseModel, Field, field_validator
from functools import lru_cache
from dotenv import load_dotenv
from replicate import Client
from html import unescape
import re
from urllib.parse import unquote
import requests
import asyncio
import logging
import os
import json

logger = logging.getLogger(__name__)
load_dotenv()


class Settings(BaseModel):
    """Application settings with API configurations"""

    PIKAPI_BASE_URL: str = "https://api.pikapikapika.io/web"
    PIKAPI_BEARER_TOKEN: str = Field(
        default_factory=lambda: os.getenv("PIKAPI_BEARER_TOKEN")
    )
    REPLICATE_API_TOKEN: str = Field(
        default_factory=lambda: os.getenv("REPLICATE_API_TOKEN")
    )
    REPLICATE_MODEL_ID: str = (
        "pharmapsychotic/clip-interrogator:8151e1c9f47e696fa316146a2e35812ccf79cfc9eba05b11c7f450155102af70"
    )
    CALLBACK_API_URL: str = "https://game-api.virtuals.io/requests"
    GAME_API_KEY: str = Field(default_factory=lambda: os.getenv("GAME_API_KEY"))
    MAX_CHECK_TIME: int = 420
    INITIAL_WAIT_TIME: int = 300

    class Config:
        validate_default = True

    @property
    def is_valid(self) -> bool:
        return bool(
            self.PIKAPI_BEARER_TOKEN and self.REPLICATE_API_TOKEN and self.GAME_API_KEY
        )


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

    @field_validator("image_id")
    @classmethod
    def decode_url(cls, v):
        """Decode HTML-encoded URL"""

        decoded = unescape(v)

        decoded = decoded.replace("&#x2F;", "/")
        decoded = decoded.replace("&#x3D;", "=")
        decoded = decoded.replace("&amp;", "&")

        return decoded


class VideoResponse(BaseModel):
    """Response model for video generation initiation"""

    message: str = Field(
        default="Video generation pipeline initialized | ETA: 5-7 minutes"
    )
    request_id: str


class CallbackData(BaseModel):
    """Model for callback data"""

    data: Dict[str, Any]

    @classmethod
    def create_success(cls, url: str, title: str):
        return cls(
            data={
                "addToInventory": True,
                "status": "COMPLETED",
                "output": {
                    "title": title,
                    "type": "MEDIA",
                    "category": "MARKETING_VIDEO",
                    "url": url,
                },
            }
        )

    @classmethod
    def create_failure(cls):
        return cls(data={"addToInventory": False, "status": "FAILED", "output": None})


# Utility Functions
def extract_title_from_url(url: str) -> str:
    """Extract and clean up the title from the video URL"""
    try:
        match = re.search(r"[a-f0-9-]+/(.+?)(?:_seed\d+)?\.mp4$", url)
        if match:
            title = unquote(match.group(1))
            title = title.replace("_", " ").split(",")[0]
            title = re.sub(r"^[a-f0-9-]+/", "", title)
            return title.capitalize()
    except Exception as e:
        logger.error(f"Error extracting title: {str(e)}")
    return "Generated Video"


async def send_callback(
    settings: Settings, request_id: str, callback_data: CallbackData
):
    """Send callback to the G.A.M.E"""
    try:
        url = f"{settings.CALLBACK_API_URL}/{request_id}/callback"
        headers = {"x-api-key": settings.GAME_API_KEY}
        body = callback_data.model_dump()

        curl_command = f"curl -X POST {url} " \
                       f"-H 'x-api-key: {headers['x-api-key']}' " \
                       f"-H 'Content-Type: application/json' " \
                       f"-d '{json.dumps(body)}'"
        logger.warning(f"Generated curl command: {curl_command}")

        response = requests.post(url, json=callback_data.model_dump(), headers=headers)
        response.raise_for_status()
        logger.warning(f"Callback sent successfully for request {request_id}")
    except Exception as e:
        logger.error(f"Failed to send callback for request {request_id}: {str(e)}")


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
                    "mode": "best",
                },
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
                f"{self._base_url}/generate", json=params, headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()["job"]["id"]
        except Exception as e:
            logger.error(f"Video generation initiation failed: {str(e)}")
            return None

    async def check_status(self, job_id: str) -> Optional[str]:
        """Check job status and return video URL when complete"""
        try:
            await asyncio.sleep(self._initial_wait_time)

            start_time = asyncio.get_event_loop().time()
            while True:
                if asyncio.get_event_loop().time() - start_time > self._max_check_time:
                    raise RuntimeError("Video generation timed out")

                response = requests.get(
                    f"{self._base_url}/jobs/{job_id}", headers=self._get_headers()
                )
                response.raise_for_status()

                job_data = response.json()
                status = job_data["videos"][0]["status"]
                logger.info(f"Job {job_id} status: {status}")

                if status == "finished":
                    return job_data["videos"][0]["resultUrl"]
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
            "Content-Type": "application/json",
        }


# Business Logic
@dataclass
class VideoGenerator:
    """Core business logic for video generation"""

    _replicate_client: ReplicateClient
    _pikapi_client: PikapiClient
    _settings: Settings

    async def generate_and_callback(self, image: str, request_id: str):
        """Generate video and send callback when complete"""
        try:
            video_url = await self.generate(image)

            if video_url:
                title = extract_title_from_url(video_url)
                callback_data = CallbackData.create_success(video_url, title)
            else:
                callback_data = CallbackData.create_failure()

            await send_callback(self._settings, request_id, callback_data)

        except Exception as e:
            logger.error(f"Error in generate_and_callback: {str(e)}")
            await send_callback(
                self._settings, request_id, CallbackData.create_failure()
            )

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
                    "parameters": {"motion": 2, "guidanceScale": 16},
                },
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
        _api_token=settings.REPLICATE_API_TOKEN, _model_id=settings.REPLICATE_MODEL_ID
    )

    pikapi_client = PikapiClient(
        _base_url=settings.PIKAPI_BASE_URL,
        _bearer_token=settings.PIKAPI_BEARER_TOKEN,
        _max_check_time=settings.MAX_CHECK_TIME,
        _initial_wait_time=settings.INITIAL_WAIT_TIME,
    )

    # Initialize video generator
    app.state.video_generator = VideoGenerator(
        _replicate_client=replicate_client,
        _pikapi_client=pikapi_client,
        _settings=settings,
    )

    yield


app = FastAPI(
    title="I-2-V API",
    description="A wrapper API for Replicate & Pika with async processing",
    version="1.0.1",
    lifespan=lifespan,
)


# Endpoints
@app.post(
    "/api/v1/i2v",
    response_model=VideoResponse,
)
async def generate_video(
    request: VideoRequest,
    x_request_id: str = Header(...),
    generator: VideoGenerator = Depends(lambda: app.state.video_generator),
) -> VideoResponse:
    """Initiate video generation and return immediately"""
    asyncio.create_task(generator.generate_and_callback(request.image_id, x_request_id))

    return VideoResponse(request_id=x_request_id)


@app.get("/")
async def read_root():
    """API root endpoint with documentation"""
    return {
        "message": "i2v",
        "description": "a wrapper api for replicate & pika ai with async processing",
        "endpoints": {
            "/api/v1/i2v": "post — video gen with image url (async)",
            "/docs": "interactive docs",
        },
        "version": "1.0.9",
    }
