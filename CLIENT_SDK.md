# Friday AI Assistant - Client SDK Documentation

Friday is now fully hostable on Render and works seamlessly with websites and mobile apps. This document provides comprehensive integration examples for different platforms.

## Quick Start

### 1. Get Your API Key

Set the `FRIDAY_API_KEY` environment variable on Render with a secure key. Include this key in all API requests using the `X-API-Key` header.

### 2. Base URL

Replace `https://your-app.onrender.com` with your actual Render deployment URL.

---

## Web Integration (JavaScript/TypeScript)

### Installation

```bash
npm install axios # or use fetch API
```

### Create a Room and Join

```javascript
const API_KEY = 'your-api-key';
const BASE_URL = 'https://your-app.onrender.com';
const headers = {
  'X-API-Key': API_KEY,
  'Content-Type': 'application/json'
};

// Step 1: Create a room
async function createRoom() {
  const response = await fetch(`${BASE_URL}/create-room`, {
    method: 'POST',
    headers,
  });
  const data = await response.json();
  return data.room_name;
}

// Step 2: Get LiveKit token
async function getToken(roomName, userId) {
  const response = await fetch(
    `${BASE_URL}/token?roomName=${roomName}&identity=${userId}`,
    { headers }
  );
  const data = await response.json();
  return data.token;
}

// Step 3: Connect using LiveKit SDK
async function startSession() {
  const { LiveKitRoom, Participant, Track } = await import('@livekit/components-js');
  
  const roomName = await createRoom();
  const token = await getToken(roomName, 'user-' + Date.now());
  
  const room = new Room({
    audio: true,
    video: false,
    adaptiveStream: true
  });
  
  room.connect(LIVEKIT_URL, token);
  return room;
}
```

### Call Tools via REST API

```javascript
// Get weather
async function getWeather(city) {
  const response = await fetch(`${BASE_URL}/api/weather`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ city })
  });
  return response.json();
}

// Search web
async function searchWeb(query) {
  const response = await fetch(`${BASE_URL}/api/search`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ query })
  });
  return response.json();
}

// Send email
async function sendEmail(to, subject, message, cc = null) {
  const response = await fetch(`${BASE_URL}/api/send-email`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      to_email: to,
      subject,
      message,
      cc_email: cc
    })
  });
  return response.json();
}
```

### Real-Time Chat via WebSocket

```javascript
class FridayChat {
  constructor(userId, apiKey) {
    this.userId = userId;
    this.apiKey = apiKey;
    this.baseURL = BASE_URL;
  }

  connect() {
    const wsUrl = `ws://${this.baseURL.replace(/^https?:\/\//, '')}/ws/${this.userId}`;
    this.ws = new WebSocket(wsUrl);
    
    this.ws.onopen = () => {
      console.log('Connected to Friday');
      this.send({
        type: 'greeting',
        message: 'Hello Friday'
      });
    };
    
    this.ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      console.log('Received:', message);
      this.onMessage(message);
    };
    
    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
    
    this.ws.onclose = () => {
      console.log('Disconnected from Friday');
    };
  }

  send(message) {
    if (this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  sendMessage(content) {
    this.send({
      type: 'chat',
      content,
      timestamp: new Date().toISOString()
    });
  }

  onMessage(message) {
    // Handle incoming messages
    if (message.type === 'response') {
      console.log('AI Response:', message.content);
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
    }
  }
}

// Usage
const chat = new FridayChat('user123', API_KEY);
chat.connect();
chat.sendMessage('What is the weather in London?');
```

---

## iOS Integration (Swift)

### Installation with CocoaPods

```ruby
# Podfile
pod 'LiveKit'
pod 'Alamofire'
```

### Basic Setup

```swift
import LiveKit
import Alamofire

struct FridayClient {
    let apiKey: String
    let baseURL: String
    
    func createRoom() async throws -> String {
        let headers: HTTPHeaders = [
            "X-API-Key": apiKey,
            "Content-Type": "application/json"
        ]
        
        let response = await AF.request(
            "\(baseURL)/create-room",
            method: .post,
            headers: headers
        ).validate().serializingDecodable(RoomResponse.self).response
        
        guard let data = response.value else {
            throw response.error ?? FridayError.unknown
        }
        return data.room_name
    }
    
    func getToken(roomName: String, identity: String) async throws -> String {
        let headers: HTTPHeaders = ["X-API-Key": apiKey]
        let params = ["roomName": roomName, "identity": identity]
        
        let response = await AF.request(
            "\(baseURL)/token",
            parameters: params,
            headers: headers
        ).validate().serializingDecodable(TokenResponse.self).response
        
        guard let data = response.value else {
            throw response.error ?? FridayError.unknown
        }
        return data.token
    }
    
    func getWeather(city: String) async throws -> WeatherResponse {
        let headers: HTTPHeaders = [
            "X-API-Key": apiKey,
            "Content-Type": "application/json"
        ]
        
        let body: [String: Any] = ["city": city]
        
        let response = await AF.request(
            "\(baseURL)/api/weather",
            method: .post,
            parameters: body,
            encoding: JSONEncoding.default,
            headers: headers
        ).validate().serializingDecodable(WeatherResponse.self).response
        
        guard let data = response.value else {
            throw response.error ?? FridayError.unknown
        }
        return data
    }
}

struct RoomResponse: Decodable {
    let success: Bool
    let room_name: String
    let livekit_url: String
}

struct TokenResponse: Decodable {
    let token: String
}

struct WeatherResponse: Decodable {
    let success: Bool
    let data: String
    let query: String
    let timestamp: String
}

enum FridayError: Error {
    case unknown
}

// Usage
@main
struct FridayApp: App {
    @StateObject var viewModel = FridayViewModel()
    
    var body: some Scene {
        WindowGroup {
            ContentView(viewModel: viewModel)
        }
    }
}

class FridayViewModel: NSObject, ObservableObject {
    let client = FridayClient(
        apiKey: "your-api-key",
        baseURL: "https://your-app.onrender.com"
    )
    
    @Published var roomName: String = ""
    @Published var token: String = ""
    @Published var weather: String = ""
    
    func connectToAssistant() {
        Task {
            do {
                roomName = try await client.createRoom()
                let userId = UUID().uuidString
                token = try await client.getToken(roomName: roomName, identity: userId)
                print("Connected! Room: \(roomName)")
            } catch {
                print("Error: \(error)")
            }
        }
    }
    
    func fetchWeather(city: String) {
        Task {
            do {
                let result = try await client.getWeather(city: city)
                DispatchQueue.main.async {
                    self.weather = result.data
                }
            } catch {
                print("Weather error: \(error)")
            }
        }
    }
}
```

---

## Android Integration (Kotlin)

### Installation with Gradle

```gradle
dependencies {
    implementation 'io.livekit:livekit-android:0.x.x'
    implementation 'com.squareup.retrofit2:retrofit:2.9.0'
    implementation 'com.squareup.retrofit2:converter-gson:2.9.0'
    implementation 'androidx.lifecycle:lifecycle-runtime-ktx:2.6.0'
}
```

### Basic Setup

```kotlin
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.*
import kotlinx.coroutines.*
import io.livekit.android.room.Room

data class RoomResponse(
    val success: Boolean,
    val room_name: String,
    val livekit_url: String
)

data class TokenResponse(val token: String)

data class WeatherRequest(val city: String)

data class WeatherResponse(
    val success: Boolean,
    val data: String,
    val query: String,
    val timestamp: String
)

interface FridayApiService {
    @POST("/create-room")
    suspend fun createRoom(@Header("X-API-Key") apiKey: String): RoomResponse
    
    @GET("/token")
    suspend fun getToken(
        @Query("roomName") roomName: String,
        @Query("identity") identity: String,
        @Header("X-API-Key") apiKey: String
    ): TokenResponse
    
    @POST("/api/weather")
    suspend fun getWeather(
        @Body request: WeatherRequest,
        @Header("X-API-Key") apiKey: String
    ): WeatherResponse
}

class FridayClient(private val baseURL: String, private val apiKey: String) {
    private val retrofit = Retrofit.Builder()
        .baseUrl(baseURL)
        .addConverterFactory(GsonConverterFactory.create())
        .build()
    
    private val api = retrofit.create(FridayApiService::class.java)
    
    suspend fun createRoom(): String = withContext(Dispatchers.IO) {
        return@withContext api.createRoom(apiKey).room_name
    }
    
    suspend fun getToken(roomName: String, identity: String): String = 
        withContext(Dispatchers.IO) {
            return@withContext api.getToken(roomName, identity, apiKey).token
        }
    
    suspend fun getWeather(city: String): WeatherResponse = 
        withContext(Dispatchers.IO) {
            return@withContext api.getWeather(WeatherRequest(city), apiKey)
        }
}

// ViewModel
class FridayViewModel(private val client: FridayClient) : ViewModel() {
    private val _roomName = MutableLiveData<String>()
    val roomName: LiveData<String> = _roomName
    
    private val _token = MutableLiveData<String>()
    val token: LiveData<String> = _token
    
    fun connectToAssistant() {
        viewModelScope.launch {
            try {
                val room = client.createRoom()
                _roomName.value = room
                
                val userToken = client.getToken(room, "user-${System.currentTimeMillis()}")
                _token.value = userToken
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
    }
    
    fun fetchWeather(city: String) {
        viewModelScope.launch {
            try {
                val weather = client.getWeather(city)
                // Update UI with weather data
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
    }
}

// Activity
class MainActivity : AppCompatActivity() {
    private lateinit var viewModel: FridayViewModel
    
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        val client = FridayClient(
            baseURL = "https://your-app.onrender.com",
            apiKey = "your-api-key"
        )
        viewModel = FridayViewModel(client)
        
        viewModel.connectToAssistant()
        
        viewModel.roomName.observe(this) { room ->
            Log.d("Friday", "Connected to room: $room")
        }
    }
}
```

---

## Deployment on Render

1. **Push to GitHub**: Ensure your code is in a Git repository
2. **Connect Render**: Link your GitHub account to Render
3. **Create Service**: 
   - Click "New +"
   - Select "Web Service"
   - Connect your repository
4. **Configure**:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
5. **Set Environment Variables**:
   - `LIVEKIT_URL`
   - `LIVEKIT_API_KEY`
   - `LIVEKIT_API_SECRET`
   - `GOOGLE_API_KEY`
   - `FRIDAY_API_KEY`
   - All email credentials
6. **Deploy**: Click "Deploy"

---

## API Response Examples

### Create Room
```json
{
  "success": true,
  "room_name": "room-a1b2c3d4",
  "livekit_url": "wss://your-project.livekit.cloud"
}
```

### Get Token
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

### Weather API
```json
{
  "success": true,
  "data": "London: ☁️ +15°C, humidity 72%",
  "query": "London",
  "timestamp": "2024-02-09T10:30:00.000Z"
}
```

### Search API
```json
{
  "success": true,
  "data": "1. Result One...\n2. Result Two...",
  "query": "how to learn python",
  "timestamp": "2024-02-09T10:30:00.000Z"
}
```

---

## Error Handling

All endpoints return consistent error responses:

```json
{
  "detail": "Error message describing the problem"
}
```

HTTP Status Codes:
- `200`: Success
- `400`: Bad request
- `403`: Forbidden (invalid API key)
- `500`: Server error

---

## WebSocket Message Format

### Client → Server

```json
{
  "type": "chat",
  "content": "What's the weather?",
  "timestamp": "2024-02-09T10:30:00.000Z"
}
```

### Server → Client

```json
{
  "success": true,
  "client_id": "user-123",
  "received_message": { "type": "chat", "content": "..." },
  "timestamp": "2024-02-09T10:30:00.000Z",
  "status": "Message received and processed"
}
```

---

## Support & Documentation

- **OpenAPI Docs**: `GET /api/openapi`
- **Health Check**: `GET /health`
- **SDK Docs**: `GET /api/docs/sdk`
- **Config**: `GET /api/config`

For issues, check the server logs on Render dashboard.
