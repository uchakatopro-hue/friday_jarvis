# Friday AI Assistant - Mobile App Integration Guide

This guide provides best practices for integrating Friday into iOS and Android applications.

## Architecture Overview

```
┌─────────────────┐
│   Mobile App    │
│  (iOS/Android)  │
└────────┬────────┘
         │
         │ WebSocket (Real-time)
         │ REST APIs (Tools)
         │ LiveKit WebRTC (Voice)
         │
    ┌────▼─────────────────┐
    │  Friday on Render    │
    │  ┌──────────────┐    │
    │  │ FastAPI App  │    │
    │  ├──────────────┤    │
    │  │ LiveKit Agent│    │
    │  ├──────────────┤    │
    │  │ Tools Layer  │    │
    │  └──────────────┘    │
    └─────────┬────────────┘
              │
    ┌─────────┴──────────┬──────────────┐
    ▼                    ▼              ▼
┌─────────┐      ┌─────────────┐   ┌────────┐
│LiveKit  │      │Google Gemini│   │ Gmail  │
│ Cloud   │      │ Realtime API│   │ SMTP   │
└─────────┘      └─────────────┘   └────────┘
```

## iOS Integration (Swift)

### 1. CocoaPods Setup

```ruby
# Podfile
platform :ios, '14.0'

target 'FridayApp' do
  pod 'LiveKit'
  pod 'Alamofire'
  pod 'Starscream'  # WebSocket
  pod 'SwiftyJSON'  # JSON parsing
  pod 'KeychainSwift'  # Secure storage
end
```

Run: `pod install`

### 2. Environment Configuration

```swift
import Foundation

struct FridayConfig {
    static let baseURL = URL(string: ProcessInfo.processInfo.environment["FRIDAY_BASE_URL"] ?? "https://friday-ai-assistant.onrender.com")!
    static let apiKey = "YOUR_API_KEY"  // Store securely in Keychain
    static let livekitURL = "wss://your-project.livekit.cloud"
    
    static var headers: [String: String] {
        return [
            "X-API-Key": apiKey,
            "Content-Type": "application/json"
        ]
    }
}
```

### 3. API Client

```swift
import Alamofire
import SwiftyJSON

protocol FridayAPIDelegate: AnyObject {
    func didReceiveWeather(_ weather: String)
    func didReceiveSearchResults(_ results: String)
    func didSendEmail(success: Bool, message: String)
    func didEncounterError(_ error: FridayError)
}

class FridayAPIClient {
    weak var delegate: FridayAPIDelegate?
    
    func createRoom(completion: @escaping (String?) -> Void) {
        AF.request(
            "\(FridayConfig.baseURL)/create-room",
            method: .post,
            headers: HTTPHeaders(FridayConfig.headers)
        )
        .validate()
        .responseDecodable(of: RoomResponse.self) { response in
            switch response.result {
            case .success(let data):
                completion(data.room_name)
            case .failure(let error):
                self.delegate?.didEncounterError(.networkError(error))
                completion(nil)
            }
        }
    }
    
    func getToken(roomName: String, identity: String, completion: @escaping (String?) -> Void) {
        let params = ["roomName": roomName, "identity": identity]
        
        AF.request(
            "\(FridayConfig.baseURL)/token",
            parameters: params,
            headers: HTTPHeaders(FridayConfig.headers)
        )
        .validate()
        .responseDecodable(of: TokenResponse.self) { response in
            switch response.result {
            case .success(let data):
                completion(data.token)
            case .failure(let error):
                self.delegate?.didEncounterError(.networkError(error))
                completion(nil)
            }
        }
    }
    
    func getWeather(city: String) {
        let params: [String: Any] = ["city": city]
        
        AF.request(
            "\(FridayConfig.baseURL)/api/weather",
            method: .post,
            parameters: params,
            encoding: JSONEncoding.default,
            headers: HTTPHeaders(FridayConfig.headers)
        )
        .validate()
        .responseDecodable(of: WeatherResponse.self) { response in
            switch response.result {
            case .success(let data):
                self.delegate?.didReceiveWeather(data.data)
            case .failure(let error):
                self.delegate?.didEncounterError(.networkError(error))
            }
        }
    }
    
    func searchWeb(query: String) {
        let params: [String: Any] = ["query": query]
        
        AF.request(
            "\(FridayConfig.baseURL)/api/search",
            method: .post,
            parameters: params,
            encoding: JSONEncoding.default,
            headers: HTTPHeaders(FridayConfig.headers)
        )
        .validate()
        .responseDecodable(of: SearchResponse.self) { response in
            switch response.result {
            case .success(let data):
                self.delegate?.didReceiveSearchResults(data.data)
            case .failure(let error):
                self.delegate?.didEncounterError(.networkError(error))
            }
        }
    }
    
    func sendEmail(to: String, subject: String, message: String, cc: String? = nil) {
        let params: [String: Any] = [
            "to_email": to,
            "subject": subject,
            "message": message,
            "cc_email": cc ?? NSNull()
        ]
        
        AF.request(
            "\(FridayConfig.baseURL)/api/send-email",
            method: .post,
            parameters: params,
            encoding: JSONEncoding.default,
            headers: HTTPHeaders(FridayConfig.headers)
        )
        .validate()
        .responseDecodable(of: EmailResponse.self) { response in
            switch response.result {
            case .success(let data):
                self.delegate?.didSendEmail(success: data.success, message: data.message)
            case .failure(let error):
                self.delegate?.didEncounterError(.networkError(error))
            }
        }
    }
}

// Response Models
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

struct SearchResponse: Decodable {
    let success: Bool
    let data: String
    let query: String
    let timestamp: String
}

struct EmailResponse: Decodable {
    let success: Bool
    let message: String
    let recipient: String
    let timestamp: String
}

enum FridayError: Error {
    case networkError(Error)
    case invalidResponse
    case decodingError(Error)
}
```

### 4. LiveKit Integration

```swift
import LiveKit
import AVFoundation

class LiveKitManager: NSObject, RoomDelegate {
    var room: Room?
    var api: FridayAPIClient
    var participants: [Participant] = []
    
    override init() {
        api = FridayAPIClient()
        super.init()
        requestMicrophonePermission()
    }
    
    private func requestMicrophonePermission() {
        AVAudioSession.sharedInstance().requestRecordPermission { granted in
            if !granted {
                print("Microphone permission denied")
            }
        }
    }
    
    func joinRoom(identity: String) {
        api.createRoom { [weak self] roomName in
            guard let self = self, let roomName = roomName else { return }
            
            self.api.getToken(roomName: roomName, identity: identity) { token in
                guard let token = token else { return }
                self.connectToRoom(roomName: roomName, token: token)
            }
        }
    }
    
    private func connectToRoom(roomName: String, token: String) {
        let room = Room()
        self.room = room
        room.delegate = self
        room.audioTrackPublishOptions = AudioTrackPublishOptions(
            audioCodec: .opus,
            bitrate: 32000,
            maxBitrate: 64000
        )
        
        do {
            try room.connect(FridayConfig.livekitURL, token: token)
        } catch {
            print("Failed to connect: \(error)")
        }
    }
    
    func leaveRoom() {
        room?.disconnect()
    }
    
    // MARK: - RoomDelegate
    func room(_ room: Room, didUpdate participants: [Participant]) {
        DispatchQueue.main.async {
            self.participants = participants
            // Update UI
        }
    }
    
    func room(_ room: Room, participantDidJoin participant: Participant) {
        print("Participant joined: \(participant.identity)")
    }
    
    func room(_ room: Room, participantDidLeave participant: Participant) {
        print("Participant left: \(participant.identity)")
    }
}
```

### 5. WebSocket Connection

```swift
import Starscream

class FridayWebSocket: WebSocketDelegate {
    var webSocket: WebSocket?
    var onMessageReceived: ((String) -> Void)?
    
    func connect(userId: String) {
        let wsURLString = FridayConfig.baseURL.absoluteString
            .replacingOccurrences(of: "https://", with: "wss://")
            .replacingOccurrences(of: "http://", with: "ws://")
        
        guard let url = URL(string: "\(wsURLString)/ws/\(userId)") else {
            print("Invalid WebSocket URL")
            return
        }
        
        webSocket = WebSocket(url: url)
        webSocket?.delegate = self
        webSocket?.connect()
    }
    
    func sendMessage(_ message: [String: Any]) {
        guard let jsonData = try? JSONSerialization.data(withJSONObject: message),
              let jsonString = String(data: jsonData, encoding: .utf8) else {
            return
        }
        webSocket?.send(string: jsonString)
    }
    
    func disconnect() {
        webSocket?.disconnect()
    }
    
    // MARK: - WebSocketDelegate
    func didReceive(event: WebSocketEvent, client: WebSocket) {
        switch event {
        case .connected(_):
            print("WebSocket connected")
        case .disconnected(_, _):
            print("WebSocket disconnected")
        case .text(let string):
            onMessageReceived?(string)
        case .binary(let data):
            if let string = String(data: data, encoding: .utf8) {
                onMessageReceived?(string)
            }
        case .error(let error):
            print("WebSocket error: \(error?.localizedDescription ?? "Unknown")")
        case .viabilityChanged(_):
            break
        case .reconnectSuggested(_):
            break
        case .cancelled:
            break
        case .pong(_):
            break
        case .ping(_):
            break
        }
    }
}
```

### 6. SwiftUI View

```swift
import SwiftUI

struct ContentView: View {
    @StateObject private var liveKitManager = LiveKitManager()
    @State private var isConnected = false
    @State private var currentQuery = ""
    @State private var weatherResult = ""
    
    var body: some View {
        VStack(spacing: 20) {
            Text("Friday AI Assistant")
                .font(.largeTitle)
                .fontWeight(.bold)
            
            if isConnected {
                VStack(spacing: 15) {
                    TextField("Ask something...", text: $currentQuery)
                        .textFieldStyle(.roundedBorder)
                        .padding()
                    
                    HStack {
                        Button("Weather") {
                            liveKitManager.api.getWeather(city: currentQuery)
                        }
                        .buttonStyle(.bordered)
                        
                        Button("Search") {
                            liveKitManager.api.searchWeb(query: currentQuery)
                        }
                        .buttonStyle(.bordered)
                    }
                    
                    if !weatherResult.isEmpty {
                        Text(weatherResult)
                            .padding()
                            .background(Color.gray.opacity(0.1))
                            .cornerRadius(8)
                    }
                }
                .padding()
                
                Button("Leave Call") {
                    liveKitManager.leaveRoom()
                    isConnected = false
                }
                .buttonStyle(.borderedProminent)
                .tint(.red)
            } else {
                Button("Start Voice Chat") {
                    let userId = UUID().uuidString
                    liveKitManager.joinRoom(identity: userId)
                    isConnected = true
                }
                .buttonStyle(.borderedProminent)
                .font(.headline)
            }
            
            Spacer()
        }
        .padding()
    }
}

#Preview {
    ContentView()
}
```

## Android Integration (Kotlin)

### 1. Gradle Dependencies

```gradle
dependencies {
    // LiveKit
    implementation 'io.livekit:livekit-android:0.x.x'
    
    // Networking
    implementation 'com.squareup.retrofit2:retrofit:2.9.0'
    implementation 'com.squareup.retrofit2:converter-gson:2.9.0'
    implementation 'com.squareup.okhttp3:logging-interceptor:4.10.0'
    
    // WebSocket
    implementation 'com.neovisionaries:nv-websocket-client:2.14'
    
    // JSON
    implementation 'com.google.code.gson:gson:2.10.1'
    
    // Security
    implementation 'androidx.security:security-crypto:1.1.0-alpha06'
    
    // Coroutines
    implementation 'org.jetbrains.kotlinx:kotlinx-coroutines-android:1.6.4'
}
```

### 2. API Client

```kotlin
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.*
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import com.google.gson.annotations.SerializedName

object FridayConfig {
    const val BASE_URL = "https://friday-ai-assistant.onrender.com"
    const val API_KEY = "YOUR_API_KEY"
    const val LIVEKIT_URL = "wss://your-project.livekit.cloud"
}

// Data models
data class RoomResponse(
    val success: Boolean,
    val room_name: String,
    val livekit_url: String
)

data class TokenResponse(val token: String)

data class WeatherRequest(@SerializedName("city") val city: String)

data class WeatherResponse(
    val success: Boolean,
    val data: String,
    val query: String,
    val timestamp: String
)

// API Interface
interface FridayApiService {
    @POST("/create-room")
    suspend fun createRoom(
        @Header("X-API-Key") apiKey: String
    ): RoomResponse
    
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

class FridayApiClient {
    private val retrofit = Retrofit.Builder()
        .baseUrl(FridayConfig.BASE_URL)
        .addConverterFactory(GsonConverterFactory.create())
        .client(createOkHttpClient())
        .build()
    
    private val apiService: FridayApiService = retrofit.create(FridayApiService::class.java)
    
    private fun createOkHttpClient(): OkHttpClient {
        val logging = HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BODY
        }
        
        return OkHttpClient.Builder()
            .addInterceptor(logging)
            .build()
    }
    
    suspend fun createRoom(): String {
        return apiService.createRoom(FridayConfig.API_KEY).room_name
    }
    
    suspend fun getToken(roomName: String, identity: String): String {
        return apiService.getToken(roomName, identity, FridayConfig.API_KEY).token
    }
    
    suspend fun getWeather(city: String): WeatherResponse {
        return apiService.getWeather(WeatherRequest(city), FridayConfig.API_KEY)
    }
}
```

### 3. LiveKit Manager

```kotlin
import io.livekit.android.room.Room
import io.livekit.android.room.RoomListener
import io.livekit.android.room.participant.Participant
import java.util.concurrent.TimeUnit

class LiveKitManager(private val apiClient: FridayApiClient) : RoomListener {
    private var room: Room? = null
    var onParticipantsUpdated: ((List<Participant>) -> Unit)? = null
    var onError: ((Exception) -> Unit)? = null
    
    suspend fun joinRoom(identity: String) {
        try {
            val roomName = apiClient.createRoom()
            val token = apiClient.getToken(roomName, identity)
            connectToRoom(token)
        } catch (e: Exception) {
            onError?.invoke(e)
        }
    }
    
    private fun connectToRoom(token: String) {
        room = Room(context = null).apply {
            setListener(this@LiveKitManager)
            connect(FridayConfig.LIVEKIT_URL, token)
        }
    }
    
    fun leaveRoom() {
        room?.disconnect()
    }
    
    override fun onParticipantsChanged(participants: List<Participant>) {
        onParticipantsUpdated?.invoke(participants)
    }
}
```

### 4. ViewModel

```kotlin
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.launch

class FridayViewModel : ViewModel() {
    private val apiClient = FridayApiClient()
    private val liveKitManager = LiveKitManager(apiClient)
    
    private val _weather = MutableLiveData<String>()
    val weather: LiveData<String> = _weather
    
    fun connectToAssistant() {
        viewModelScope.launch {
            try {
                val userId = UUID.randomUUID().toString()
                liveKitManager.joinRoom(userId)
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
    }
    
    fun fetchWeather(city: String) {
        viewModelScope.launch {
            try {
                val result = apiClient.getWeather(city)
                _weather.value = result.data
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
    }
    
    fun disconnectFromAssistant() {
        liveKitManager.leaveRoom()
    }
}
```

### 5. Compose UI

```kotlin
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel

@Composable
fun FridayScreen(viewModel: FridayViewModel = viewModel()) {
    var isConnected by remember { mutableStateOf(false) }
    var query by remember { mutableStateOf("") }
    val weather by viewModel.weather.observeAsState()
    
    Column(
        modifier = Modifier.fillMaxSize().padding(20.dp),
        verticalArrangement = Arrangement.Center
    ) {
        Text("Friday AI Assistant", style = MaterialTheme.typography.headlineLarge)
        
        Spacer(modifier = Modifier.height(20.dp))
        
        if (isConnected) {
            OutlinedTextField(
                value = query,
                onValueChange = { query = it },
                label = { Text("Ask something...") },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 10.dp)
            )
            
            Row(modifier = Modifier.fillMaxWidth()) {
                Button(onClick = { viewModel.fetchWeather(query) }) {
                    Text("Weather")
                }
                Button(onClick = { }) {
                    Text("Search")
                }
            }
            
            weather?.let {
                Text("Weather: $it", modifier = Modifier.padding(top = 10.dp))
            }
            
            Button(
                onClick = {
                    viewModel.disconnectFromAssistant()
                    isConnected = false
                },
                colors = ButtonDefaults.buttonColors(containerColor = Color.Red),
                modifier = Modifier.align(Alignment.CenterHorizontally)
            ) {
                Text("Leave Call")
            }
        } else {
            Button(
                onClick = {
                    viewModel.connectToAssistant()
                    isConnected = true
                },
                modifier = Modifier.align(Alignment.CenterHorizontally)
            ) {
                Text("Start Voice Chat", style = MaterialTheme.typography.headlineSmall)
            }
        }
    }
}
```

## Best Practices

### 1. Security
- Store API keys in secure storage (Keychain for iOS, EncryptedSharedPreferences for Android)
- Use HTTPS only
- Validate tokens server-side
- Rotate API keys regularly

### 2. Performance
- Implement connection pooling
- Cache responses appropriately
- Use lazy loading for lists
- Optimize image sizes

### 3. Error Handling
- Implement retry logic with exponential backoff
- Provide clear error messages to users
-  Log errors for debugging
- Handle network timeouts gracefully

### 4. User Experience
- Show loading indicators
- Provide feedback for actions
- Support offline fallbacks
- Implement proper permission handling

### 5. Testing
- Unit test API client
- Integration test with mock server
- End-to-end testing with staging environment
- Test on real devices

## Troubleshooting

### Connection Issues
```
Check network connectivity
Verify API key is correct
Ensure CORS is configured properly
Check LiveKit URL is accessible
```

### Audio Problems
```
Request microphone permission
Check audio routing
Verify sample rate compatibility
Test with different network conditions
```

### Performance Issues
```
Profile memory usage
Check for memory leaks
Optimize network requests
Implement proper caching
```

## Further Resources

- LiveKit SDKs: https://docs.livekit.io/
- SwiftUI Best Practices: https://developer.apple.com/tutorials/swiftui
- Jetpack Compose: https://developer.android.com/jetpack/compose
- Mobile Security: https://owasp.org/www-project-mobile-top-10/

