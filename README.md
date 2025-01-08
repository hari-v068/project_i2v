# I2V API

A FastAPI-based wrapper API that converts still images to videos using Replicate's CLIP interrogator and Pika's video generation capabilities. The API processes requests asynchronously and provides callbacks upon completion.

## Features

- Asynchronous video generation from images
- Automatic prompt generation using CLIP interrogator
- Callback system for completion notifications
- Environment-based configuration
- Comprehensive error handling and logging
- FastAPI-powered interactive documentation

## Prerequisites

- Python 3.7+
- FastAPI
- Replicate API access
- Pika API access
- G.A.M.E API access (for callbacks)

## Environment Setup

Create a `.env` file in the root directory with the following variables:

```dotenv
PIKAPI_BEARER_TOKEN=your_pika_token
REPLICATE_API_TOKEN=your_replicate_token
GAME_API_KEY=your_game_api_key
```

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd i2v-api
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Starting the Server

```bash
uvicorn app:app --reload
```

The API will be available at `http://localhost:8000`

### API Endpoints

#### Generate Video
```http
POST /api/v1/i2v
```

Request headers:
- `x-request-id`: Unique identifier for the request (required)

Request body:
```json
{
    "image_id": "https://example.com/image.jpg"
}
```

Response:
```json
{
    "message": "Video generation pipeline initialized | ETA: 5-7 minutes",
    "request_id": "your-request-id"
}
```

#### Root Endpoint
```http
GET /
```
Returns API information and available endpoints.

### Interactive Documentation

Access the interactive API documentation at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Configuration

The API can be configured through the following environment variables:

- `PIKAPI_BEARER_TOKEN`: Authentication token for Pika API
- `REPLICATE_API_TOKEN`: Authentication token for Replicate API
- `GAME_API_KEY`: API key for G.A.M.E callback API
- `PIKAPI_BASE_URL`: Base URL for Pika API (default: "https://api.pikapikapika.io/web")
- `REPLICATE_MODEL_ID`: ID for the CLIP interrogator model
- `CALLBACK_API_URL`: URL for callback notifications
- `MAX_CHECK_TIME`: Maximum time to check for video generation completion (default: 420 seconds)
- `INITIAL_WAIT_TIME`: Initial wait time before checking status (default: 300 seconds)

## Callback System

The API implements an asynchronous callback system that notifies the specified endpoint when video generation is complete. The callback includes:

- Success response:
```json
{
    "data": {
        "addToInventory": true,
        "status": "COMPLETED",
        "output": {
            "title": "Generated Video Title",
            "type": "MEDIA",
            "category": "MARKETING_VIDEO",
            "url": "video_url"
        }
    }
}
```

- Failure response:
```json
{
    "data": {
        "addToInventory": false,
        "status": "FAILED",
        "output": null
    }
}
```

## Error Handling

The API implements comprehensive error handling and logging:
- Failed prompt generation
- Video generation failures
- Timeout handling
- Callback delivery failures

## Development

The project follows a modular structure:
- Settings management using Pydantic
- Separate client classes for external services
- Asynchronous processing using FastAPI
- Comprehensive logging