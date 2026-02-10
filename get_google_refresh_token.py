#!/usr/bin/env python3
"""
Helper script to generate a new Google OAuth2 refresh token.

This uses Google's OAuth2 server flow to get authorization.
Run this script and follow the prompts to authorize the app and get a new refresh token.
"""

import os
import webbrowser
import requests
from dotenv import load_dotenv
from urllib.parse import urlencode, parse_qs, urlparse
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

# Load existing env vars
load_dotenv()

CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
REDIRECT_URI = 'http://localhost:8080/callback'
SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.readonly',
]

auth_code = None
error_msg = None

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code, error_msg
        
        parsed = urlparse(self.path)
        if parsed.path == '/callback':
            query_params = parse_qs(parsed.query)
            
            if 'code' in query_params:
                auth_code = query_params['code'][0]
                response_html = """
                <html>
                <body style="font-family: Arial; text-align: center; padding: 50px;">
                    <h1>Authorization Successful!</h1>
                    <p>You can close this window and return to the terminal.</p>
                </body>
                </html>
                """
                self.send_response(200)
            elif 'error' in query_params:
                error_msg = query_params['error'][0]
                response_html = f"""
                <html>
                <body style="font-family: Arial; text-align: center; padding: 50px;">
                    <h1>Authorization Failed</h1>
                    <p>Error: {error_msg}</p>
                    <p>You can close this window and try again.</p>
                </body>
                </html>
                """
                self.send_response(400)
            else:
                response_html = "<html><body>Invalid callback</body></html>"
                self.send_response(400)
                
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(response_html.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Suppress server logs
        pass

def get_refresh_token():
    """Run the OAuth2 flow to get a refresh token."""
    global auth_code, error_msg
    
    if not CLIENT_ID or not CLIENT_SECRET:
        print("❌ Error: GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in .env")
        return None
    
    print("\n" + "="*60)
    print("Google OAuth2 Refresh Token Generator")
    print("="*60)
    print(f"\nClient ID: {CLIENT_ID[:20]}...")
    print(f"Scopes: Gmail Send & Read")
    print("\nStarting local callback server on http://localhost:8080/callback")
    
    # Start local server for OAuth callback
    server = HTTPServer(('localhost', 8080), OAuthCallbackHandler)
    server.timeout = 1
    
    # Build authorization URL
    auth_params = {
        'client_id': CLIENT_ID,
        'redirect_uri': REDIRECT_URI,
        'scope': ' '.join(SCOPES),
        'response_type': 'code',
        'access_type': 'offline',
        'prompt': 'consent',
    }
    auth_url = 'https://accounts.google.com/o/oauth2/v2/auth?' + urlencode(auth_params)
    
    print(f"\nOpening browser to authorize app...")
    print(f"If browser doesn't open, visit: {auth_url}\n")
    
    try:
        webbrowser.open(auth_url)
    except:
        print(f"Could not open browser. Please visit this URL:\n{auth_url}\n")
    
    print("Waiting for authorization (timeout: 5 minutes)...")
    
    # Wait for callback (max 5 minutes)
    import time
    start_time = time.time()
    
    while (time.time() - start_time) < 300:  # 5 minutes
        server.handle_request()
        if auth_code or error_msg:
            break
        time.sleep(0.1)
    
    server.server_close()
    
    if error_msg:
        print(f"\n❌ Authorization failed: {error_msg}")
        return None
    
    if not auth_code:
        print("\n❌ Timeout waiting for authorization. Please try again.")
        return None
    
    print(f"\n✓ Got authorization code")
    print("Exchanging code for refresh token...")
    
    # Exchange auth code for tokens
    token_url = 'https://oauth2.googleapis.com/token'
    token_data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'code': auth_code,
        'redirect_uri': REDIRECT_URI,
        'grant_type': 'authorization_code',
    }
    
    try:
        resp = requests.post(token_url, data=token_data, timeout=10)
        resp.raise_for_status()
        tokens = resp.json()
        
        if 'refresh_token' not in tokens:
            print("\n❌ No refresh token in response. Make sure you see the consent screen.")
            print("Response:", json.dumps(tokens, indent=2))
            return None
        
        refresh_token = tokens['refresh_token']
        access_token = tokens.get('access_token', 'N/A')
        
        print(f"\n✓ Got tokens!")
        print(f"Refresh Token (first 20 chars): {refresh_token[:20]}...")
        print(f"Access Token (first 20 chars): {access_token[:20]}...")
        
        return refresh_token
        
    except requests.RequestException as e:
        print(f"\n❌ Error exchanging code: {e}")
        return None

def main():
    refresh_token = get_refresh_token()
    
    if refresh_token:
        print("\n" + "="*60)
        print("SUCCESS! New Refresh Token Generated")
        print("="*60)
        print(f"\nRefresh Token:")
        print(refresh_token)
        print("\nUpdate your .env file with:")
        print(f"GOOGLE_REFRESH_TOKEN={refresh_token}")
        print("\n" + "="*60)
    else:
        print("\n❌ Failed to generate refresh token. Please try again.")

if __name__ == '__main__':
    main()
