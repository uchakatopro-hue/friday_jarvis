
import sys
import os

print(f"Python Executable: {sys.executable}")
print(f"Python Version: {sys.version}")

try:
    import livekit
    print(f"livekit package found: {livekit.__file__}")
except ImportError:
    print("livekit package NOT found")

try:
    from livekit.api import AccessToken, VideoGrants
    print("Successfully imported AccessToken, VideoGrants from livekit.api")
except ImportError as e:
    print(f"Failed to import from livekit.api: {e}")
    try:
        from livekit import AccessToken, VideoGrants
        print("Successfully imported AccessToken, VideoGrants from livekit")
    except ImportError as e2:
        print(f"Failed to import from livekit: {e2}")

try:
    import livekit.agents
    print(f"livekit.agents package found: {livekit.agents.__file__}")
except ImportError:
    print("livekit.agents package NOT found")
