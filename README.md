# **Image-to-Video Generator API**

This API acts as a wrapper for two third-party APIs: 
1. **Replicate API**: Generates a text prompt from an image.  
2. **Pikapikapika API**: Generates a video from the image and the generated text prompt.

It accepts an image URL, processes it, and returns a video URL.

---

## **Features**

- Accepts an image URL via a POST request.
- Automatically generates a descriptive prompt using the Replicate API.
- Uses the Pikapikapika API to generate a video based on the image and prompt.
- Returns a video URL for download or further processing.
- Built with **FastAPI**.

---

## **Requirements**

### **System Requirements**
- Python 3.9 or higher
- Pip for Python package management

### **Dependencies**
The required Python libraries are listed in `requirements.txt`. These include:
- **FastAPI**: For building the API.
- **Uvicorn**: For running the FastAPI app.
- **Replicate**: For accessing the Replicate API.
- **Requests**: For HTTP communication with APIs.
- **Python-dotenv**: For managing environment variables.

---

## **Getting Started**

### **1. Clone the Repository**
```bash
git clone https://github.com/hari-v068/project_i2v.git
cd project_i2v
```

### **2. Create a Virtual Environment**
```bash
python3 -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
```

### **3. Install Dependencies**
```bash
pip install -r requirements.txt
```

### **4. Set Up Environment Variables**
1. Create a `.env` file in the root directory.
2. Use the `.env.example` file as a reference:
   ```bash
   cp .env.example .env
   ```
3. Add your API tokens:
   - `REPLICATE_API_TOKEN`: API token for the Replicate service.
   - `PIKAPI_BEARER_TOKEN`: API token for the Pikapikapika service.

---

## **Running the Application**

### **1. Start the API Locally**
Run the application using Uvicorn:
```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```
- The API will be accessible at `http://127.0.0.1:8000`.

### **2. Test the API**
Access the interactive API documentation at:
- **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## **Endpoints**

### **1. Generate Video**
- **URL**: `/i2v`
- **Method**: `POST`
- **Request Body**:
   ```json
   {
      "image": "https://example.com/your-image.jpg"
   }
   ```
- **Response**:
   ```json
   {
      "video_url": "https://pikapikapika.io/videos/your-video.mp4"
   }
   ```

### **2. Root Endpoint**
- **URL**: `/`
- **Method**: `GET`
- **Response**:
   ```json
   {
        "message": "i2v api",
        "description": "",
        "endpoints": {
            "/i2v": "POST - start video generation",
            "/docs": "Test out the API in SwaggerUI"
        },
        "version": "v0.1"
   }
   ```

---

## **Development Notes**

### **How It Works**
1. **Prompt Generation**: 
   - The API calls the Replicate API with the provided image URL to generate a descriptive text prompt.
2. **Video Generation**:
   - The generated prompt and image URL are sent to the Pikapikapika API to create a video.
3. **Polling for Completion**:
   - The API checks the status of the video generation and waits until it's finished.
4. **Response**:
   - Once the video is ready, the URL is returned to the client.

---