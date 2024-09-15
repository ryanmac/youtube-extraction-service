# YouTube Extraction Service

This service efficiently processes YouTube channel transcripts, stores them in Pinecone for later retrieval, and provides a foundation for LLM-powered question answering.

## Features

1. Parallel video processing using Celery for improved performance.
2. Redis for task queue management and caching to avoid redundant work.
3. Immediate processing of fetched videos with progress tracking.
4. Efficient transcript chunking and embedding using OpenAI's API.
5. Pinecone vector database for fast and scalable similarity search.
6. API endpoints for job submission, status checking, and retrieving relevant transcript chunks.
7. Comprehensive error handling and logging for improved reliability.
8. API endpoints for job submission, status checking, retrieving relevant transcript chunks, and channel information.
9. Channel metadata caching for improved performance.
10. Flexible handling of various YouTube channel URL formats.


## Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/youtube-extraction-service.git
   cd youtube-extraction-service
   ```

2. Create a `.env` file with the following variables:
   ```bash
   REDIS_HOST=localhost
   REDIS_PORT=6379
   REDIS_DB=0
   PINECONE_API_KEY=your_pinecone_api_key
   PINECONE_ENVIRONMENT=your_pinecone_environment
   PINECONE_INDEX_NAME=your_pinecone_index_name
   OPENAI_API_KEY=your_openai_api_key
   YOUTUBE_API_KEY=your_youtube_api_key
   MAX_VIDEOS_PER_CHANNEL=5
   CHUNK_SIZE=200
   ```

3. Install dependencies:
   ```bash
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. Start Redis server:
   ```bash
   redis-server
   ```

5. Start Celery worker:
   ```bash
   source .venv/bin/activate
   celery -A celery_worker.celery_app worker --loglevel=info
   ```

6. Run the FastAPI application:
   ```bash
   source .venv/bin/activate
   uvicorn app.main:app --reload
   ```

## API Endpoints

- POST `/process_channel`: Submit a channel for processing
- GET `/job_status/{job_id}`: Check the status of a processing job
- GET `/relevant_chunks`: Retrieve relevant transcript chunks for a given query
- GET `/channel_info`: Get channel information and metadata
- POST `/refresh_channel_metadata`: Refresh channel metadata

## Testing

```bash
source .venv/bin/activate
pytest tests/
pytest tests/e2e/test_channel_processing.py
```

## Usage Examples

Below are updated usage examples that align with the new API structure:

### 1. **Get Channel Information**

You can retrieve channel information by providing a `channel_id`, `channel_name`, or `channel_url` as query parameters.

**Using Channel URL:**

```bash
curl -X GET "http://localhost:8000/channel_info?channel_url=https://www.youtube.com/@drwaku"
```

**Using Channel ID:**

```bash
curl -X GET "http://localhost:8000/channel_info?channel_id=UCZf5IX90oe5gdPppMXGImwg"
```

**Using Channel Name:**

```bash
curl -X GET "http://localhost:8000/channel_info?channel_name=drwaku"
```

**Returns:**

```json
{
  "channel_id": "UCZf5IX90oe5gdPppMXGImwg",
  "unique_video_count": 51,
  "total_embeddings": 1734,
  "metadata": {
    "snippet": {
      "title": "Dr Waku",
      "description": "...",
      "customUrl": "@drwaku",
      "publishedAt": "2023-04-05T21:05:39.174844Z",
      "thumbnails": {
        "default": { "url": "https://yt3.ggpht.com/NvRARiOnIb...", "width": 88, "height": 88 },
        "medium": { "url": "https://yt3.ggpht.com/NvRARiOnIb...", "width": 240, "height": 240 },
        "high": { "url": "https://yt3.ggpht.com/NvRARiOnIb...", "width": 800, "height": 800 }
      },
      "country": "CA"
    },
    "statistics": {
      "viewCount": "743515",
      "subscriberCount": "15800",
      "hiddenSubscriberCount": false,
      "videoCount": "128"
    },
    "topicDetails": {
      "topicCategories": [
        "https://en.wikipedia.org/wiki/Technology",
        "https://en.wikipedia.org/wiki/Health",
        "https://en.wikipedia.org/wiki/Knowledge",
        "https://en.wikipedia.org/wiki/Lifestyle_(sociology)"
      ]
    },
    "status": {
      "privacyStatus": "public",
      "isLinked": true,
      "madeForKids": false
    },
    "brandingSettings": {
      "channel": {
        "title": "Dr Waku",
        "description": "...",
        "country": "CA"
      },
      "image": {
        "bannerExternalUrl": "https://yt3.googleusercontent.com/TfX10Zv3y9..."
      }
    }
  }
}
```

### 2. **Refresh Channel Metadata**

Refresh the metadata for a specific channel by providing a `channel_id`, `channel_name`, or `channel_url` as query parameters.

**Using Channel URL:**

```bash
curl -X POST "http://localhost:8000/refresh_channel_metadata?channel_url=https://www.youtube.com/@drwaku"
```

**Using Channel ID:**

```bash
curl -X POST "http://localhost:8000/refresh_channel_metadata?channel_id=UCZf5IX90oe5gdPppMXGImwg"
```

**Returns:**

```json
{
  "message": "Channel metadata refreshed successfully",
  "metadata": {
    "snippet": {
      "title": "Dr Waku",
      "description": "...",
      "customUrl": "@drwaku",
      "publishedAt": "2023-04-05T21:05:39.174844Z",
      "thumbnails": {
        "default": { "url": "https://yt3.ggpht.com/NvRARiOnIb...", "width": 88, "height": 88 },
        "medium": { "url": "https://yt3.ggpht.com/NvRARiOnIb...", "width": 240, "height": 240 },
        "high": { "url": "https://yt3.ggpht.com/NvRARiOnIb...", "width": 800, "height": 800 }
      },
      "country": "CA"
    },
    "statistics": {
      "viewCount": "743515",
      "subscriberCount": "15800",
      "hiddenSubscriberCount": false,
      "videoCount": "128"
    },
    "status": {
      "privacyStatus": "public",
      "isLinked": true,
      "madeForKids": false
    },
    "brandingSettings": {
      "channel": {
        "title": "Dr Waku",
        "description": "...",
        "country": "CA"
      },
      "image": {
        "bannerExternalUrl": "https://yt3.googleusercontent.com/TfX10Zv3y9..."
      }
    }
  }
}
```

### 3. **Process a Channel**

To process a channel, you need to provide the `channel_id` in the request body as JSON. Optionally, you can specify the `video_limit`.

**Example:**

```bash
curl -X POST "http://localhost:8000/process_channel" \
     -H "Content-Type: application/json" \
     -d '{"channel_id": "UCqhM8e549EVcpmV8eTFHKjg", "video_limit": 5}'
```

**Returns:**

```json
{ "job_id": "f02af531-3854-48af-ab86-72f664fd3656", "status": "STARTED" }
```

### 4. **Check Job Status**

Retrieve the status of a processing job using the `job_id` obtained from the `/process_channel` endpoint.

```bash
curl -X GET "http://localhost:8000/job_status/{job_id}"
```

**Replace `{job_id}` with your actual job ID.**

**Returns:**

```json
{
  "job_id": "f02af531-3854-48af-ab86-72f664fd3656",
  "status": "SUCCESS",
  "progress": 100.0,
  "error": null,
  "channel_id": "UCZf5IX90oe5gdPppMXGImwg"
}
```

### 5. **Get Relevant Chunks**

Fetch relevant transcript chunks based on a query and a specific `channel_id`.

```bash
curl -X GET "http://localhost:8000/relevant_chunks?query=AI%20ethics&channel_id=UCZf5IX90oe5gdPppMXGImwg&chunk_limit=5&context_window=1"
```

**Returns:**

```json
{
  "chunks": [
    {
      "main_chunk": "interests and also AI can enhance...",
      "context_before": ["Previous context..."],
      "context_after": ["Following context..."],
      "score": 0.330345035
    },
    {
      "main_chunk": "hi everyone in an era where AI...",
      "context_before": ["Previous context..."],
      "context_after": ["Following context..."],
      "score": 0.333593
    },
    // ... more chunks
  ]
}
```

**Note:** The `context_before` and `context_after` fields provide surrounding context based on the `context_window` parameter.

---

**Important Changes:**

- **Removed Processing via Channel URL:** The `/process_channel` endpoint now requires a `channel_id` in the JSON body. Processing via `channel_url` is no longer supported.

- **Unified Query Parameters:** The `/channel_info` and `/refresh_channel_metadata` endpoints accept `channel_id`, `channel_name`, or `channel_url` as query parameters for flexibility.

- **Simplified Responses:** The responses remain consistent, providing essential information such as `channel_id`, `job_id`, and relevant data.

---

**Example Workflow:**

1. **Get Channel Information:**

   Retrieve information to obtain the `channel_id` if you don't already have it.

   ```bash
   curl -X GET "http://localhost:8000/channel_info?channel_name=drwaku"
   ```

2. **Process the Channel:**

   Start processing the channel using the `channel_id`.

   ```bash
   curl -X POST "http://localhost:8000/process_channel" \
        -H "Content-Type: application/json" \
        -d '{"channel_id": "UCZf5IX90oe5gdPppMXGImwg", "video_limit": 5}'
   ```

3. **Check Job Status:**

   Monitor the processing status using the `job_id` returned.

   ```bash
   curl -X GET "http://localhost:8000/job_status/f02af531-3854-48af-ab86-72f664fd3656"
   ```

4. **Retrieve Relevant Chunks:**

   Once processing is complete, fetch relevant transcript chunks.

   ```bash
   curl -X GET "http://localhost:8000/relevant_chunks?query=AI%20ethics&channel_id=UCZf5IX90oe5gdPppMXGImwg"
   ```

5. **Retrieve Recent Chunks:**
   
   Once processing is complete, fetch recent transcript chunks.

   ```bash
   curl -X GET "http://localhost:8000/recent_chunks?channel_id=UCZf5IX90oe5gdPppMXGImwg&chunk_limit=5"
   ```

---

**Additional Notes:**

- **API Key Requirement:** Ensure that you include the required API key in your requests if your API is secured.

- **Error Handling:** The API will return appropriate HTTP status codes and error messages if something goes wrong, such as missing parameters or processing errors.

- **Customization:** Adjust parameters like `video_limit`, `chunk_limit`, and `context_window` to fine-tune the data retrieved.

## Frontend Integration

To integrate this YouTube Extraction Service into a frontend application, follow these steps:

1. Set up a React frontend project:
   ```bash
   npx create-react-app youtube-qa-frontend
   cd youtube-qa-frontend
   ```

2. Install necessary dependencies:
   ```bash
   npm install axios @material-ui/core @material-ui/icons
   ```

3. Create a new file `src/api.js` to handle API calls:

```javascript
import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

export const processChannel = async (channelUrl) => {
  const response = await axios.post(`${API_BASE_URL}/process_channel`, { channel_url: channelUrl });
  return response.data;
};

export const getJobStatus = async (jobId) => {
  const response = await axios.get(`${API_BASE_URL}/job_status/${jobId}`);
  return response.data;
};

export const getRelevantChunks = async (query, channelUrl, chunkLimit = 5, contextWindow = 1) => {
  const response = await axios.get(`${API_BASE_URL}/relevant_chunks`, {
    params: { query, channel_url: channelUrl, chunk_limit: chunkLimit, context_window: contextWindow }
  });
  return response.data;
};

export const getChannelInfo = async (channelUrl) => {
  const response = await axios.get(`${API_BASE_URL}/channel_info`, {
    params: { channel_url: channelUrl }
  });
  return response.data;
};

export const refreshChannelMetadata = async (channelUrl) => {
  const response = await axios.post(`${API_BASE_URL}/refresh_channel_metadata`, null, {
    params: { channel_url: channelUrl }
  });
  return response.data;
};
```

4. Create a new component `src/YouTubeQA.js`:

```jsx
import React, { useState } from 'react';
import { TextField, Button, CircularProgress, Typography, Paper } from '@material-ui/core';
import { processChannel, getJobStatus, getRelevantChunks } from './api';

const YouTubeQA = () => {
  const [channelUrl, setChannelUrl] = useState('');
  const [query, setQuery] = useState('');
  const [processing, setProcessing] = useState(false);
  const [channelId, setChannelId] = useState(null);
  const [relevantChunks, setRelevantChunks] = useState([]);

  const handleProcessChannel = async () => {
    setProcessing(true);
    try {
      const { job_id } = await processChannel(channelUrl);
      await pollJobStatus(job_id);
    } catch (error) {
      console.error('Error processing channel:', error);
    }
    setProcessing(false);
  };

  const pollJobStatus = async (jobId) => {
    while (true) {
      const { status, progress, channel_id } = await getJobStatus(jobId);
      if (status === 'SUCCESS') {
        setChannelId(channel_id);
        break;
      } else if (status === 'FAILED') {
        console.error('Channel processing failed');
        break;
      }
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
  };

  const handleQuery = async () => {
    if (!channelId) return;
    try {
      const { chunks } = await getRelevantChunks(query, channelId);
      setRelevantChunks(chunks);
    } catch (error) {
      console.error('Error retrieving relevant chunks:', error);
    }
  };

  return (
    <Paper style={{ padding: '20px', maxWidth: '600px', margin: '20px auto' }}>
      <Typography variant="h5" gutterBottom>YouTube QA System</Typography>
      <TextField
        fullWidth
        label="YouTube Channel URL"
        value={channelUrl}
        onChange={(e) => setChannelUrl(e.target.value)}
        margin="normal"
      />
      <Button
        variant="contained"
        color="primary"
        onClick={handleProcessChannel}
        disabled={processing || !channelUrl}
      >
        {processing ? <CircularProgress size={24} /> : 'Process Channel'}
      </Button>
      {channelId && (
        <>
          <TextField
            fullWidth
            label="Ask a question"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            margin="normal"
          />
          <Button
            variant="contained"
            color="secondary"
            onClick={handleQuery}
            disabled={!query}
          >
            Ask
          </Button>
          {relevantChunks.map((chunk, index) => (
            <Paper key={index} style={{ padding: '10px', margin: '10px 0' }}>
              <Typography variant="body1">{chunk.main_chunk}</Typography>
              <Typography variant="caption">Score: {chunk.score}</Typography>
            </Paper>
          ))}
        </>
      )}
    </Paper>
  );
};

export default YouTubeQA;
```

5. Update `src/App.js` to use the new component:

```jsx
import React from 'react';
import YouTubeQA from './YouTubeQA';

function App() {
  return (
    <div className="App">
      <YouTubeQA />
    </div>
  );
}

export default App;
```

## Using with an LLM

To use the retrieved chunks with an LLM API (e.g., OpenAI's GPT), you can implement a function like this:

```javascript
import axios from 'axios';

const OPENAI_API_URL = 'https://api.openai.com/v1/chat/completions';
const OPENAI_API_KEY = 'your_openai_api_key';

export const generateAnswer = async (question, relevantChunks) => {
  const context = relevantChunks.map(chunk => chunk.main_chunk).join('\n\n');
  const messages = [
    { role: 'system', content: 'You are a helpful assistant that answers questions based on the given context.' },
    { role: 'user', content: `Context:\n${context}\n\nQuestion: ${question}` }
  ];

  try {
    const response = await axios.post(OPENAI_API_URL, {
      model: 'gpt-3.5-turbo',
      messages: messages,
      max_tokens: 150
    }, {
      headers: {
        'Authorization': `Bearer ${OPENAI_API_KEY}`,
        'Content-Type': 'application/json'
      }
    });

    return response.data.choices[0].message.content;
  } catch (error) {
    console.error('Error generating answer:', error);
    throw error;
  }
};
```

You can then use this function in your React component to generate answers based on the retrieved chunks.

## Error Handling and Monitoring

The YouTube Extraction Service includes comprehensive error handling and logging. To monitor the application:

1. Check the console output of the FastAPI application and Celery worker for detailed logs.
2. Implement a centralized logging system (e.g., ELK stack or Prometheus) for production environments.
3. Set up alerts for critical errors or performance issues.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License.
