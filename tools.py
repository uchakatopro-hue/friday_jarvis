import logging
import re
from livekit.agents import function_tool, RunContext
import requests
from langchain_community.tools import DuckDuckGoSearchRun
import os
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from typing import Optional
from datetime import datetime
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:
    ZoneInfo = None

DEFAULT_HTTP_TIMEOUT = int(os.getenv('HTTP_TIMEOUT_SECONDS', '20'))

def _get_google_access_token() -> Optional[str]:
    """
    Exchange a Google refresh token for an access token using OAuth2.
    Requires GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN env vars.
    """
    token_url = "https://oauth2.googleapis.com/token"
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")

    if not (client_id and client_secret and refresh_token):
        missing = []
        if not client_id:
            missing.append("GOOGLE_CLIENT_ID")
        if not client_secret:
            missing.append("GOOGLE_CLIENT_SECRET")
        if not refresh_token:
            missing.append("GOOGLE_REFRESH_TOKEN")
        logging.error(f"Google OAuth2 credentials not fully configured. Missing: {', '.join(missing)}")
        return None

    try:
        resp = requests.post(
            token_url,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=DEFAULT_HTTP_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("access_token")
        else:
            try:
                error_info = resp.json()
                error_desc = error_info.get("error_description", "Unknown error")
                logging.error(f"Google OAuth2 token refresh failed: {error_desc} (HTTP {resp.status_code})")
            except:
                logging.error(f"Google OAuth2 token refresh failed (HTTP {resp.status_code}): {resp.text}")
            return None
    except requests.RequestException as e:
        logging.error(f"Error requesting Google access token: {e}")
        return None

@function_tool()
async def get_weather(
    context: RunContext,  # type: ignore
    city: str) -> str:
    """
    Get the current weather for a given city.
    """
    try:
        import urllib.parse, time, random
        norm_city = urllib.parse.quote((city or '').strip())
        if not norm_city:
            return "City is required to fetch weather."

        headers = {"User-Agent": "friday_jarvis/1.0 (weather)"}

        # Primary: Open-Meteo via geocoding + current weather
        try:
            # 1) Geocode city to lat/lon
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={norm_city}&count=1&language=en&format=json"
            geo_resp = None
            for attempt in range(1, 4):
                geo_resp = requests.get(geo_url, timeout=DEFAULT_HTTP_TIMEOUT, headers=headers)
                if geo_resp.status_code == 200:
                    break
                if geo_resp.status_code in (429, 500, 502, 503, 504):
                    sleep_s = min(2 ** attempt + random.random(), 8)
                    logging.warning(f"Geocoding transient error {geo_resp.status_code}; retrying in {sleep_s:.1f}s")
                    time.sleep(sleep_s)
                    continue
                break
            if not geo_resp or geo_resp.status_code != 200:
                raise RuntimeError(f"Geocoding failed status={geo_resp.status_code if geo_resp else 'no response'}")
            geo = geo_resp.json()
            results = geo.get('results') or []
            if not results:
                return f"Could not locate '{city}' for weather lookup."
            lat = results[0]['latitude']
            lon = results[0]['longitude']

            # 2) Fetch current weather
            weather_url = (
                f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                f"&current_weather=true&timezone=auto"
            )
            wx_resp = None
            for attempt in range(1, 4):
                wx_resp = requests.get(weather_url, timeout=DEFAULT_HTTP_TIMEOUT, headers=headers)
                if wx_resp.status_code == 200:
                    break
                if wx_resp.status_code in (429, 500, 502, 503, 504):
                    sleep_s = min(2 ** attempt + random.random(), 8)
                    logging.warning(f"Weather transient error {wx_resp.status_code}; retrying in {sleep_s:.1f}s")
                    time.sleep(sleep_s)
                    continue
                break
            if not wx_resp or wx_resp.status_code != 200:
                raise RuntimeError(f"Weather fetch failed status={wx_resp.status_code if wx_resp else 'no response'}")
            wx = wx_resp.json()
            current = (wx.get('current_weather') or {})
            temp_c = current.get('temperature')
            wind_kph = current.get('windspeed')
            wind_kph = round(wind_kph, 1) if isinstance(wind_kph, (int, float)) else wind_kph
            desc = f"code {current.get('weathercode')}"  # Open-Meteo returns WMO code; can be mapped if needed
            out = f"{city}: {desc}, {temp_c}°C, wind {wind_kph} km/h"
            logging.info(f"Weather for {city}: {out}")
            return out
        except Exception as primary_err:
            logging.warning(f"Primary weather provider failed: {primary_err}; falling back to wttr.in")

            # Fallback: wttr.in JSON (if reachable)
            url = f"https://wttr.in/{norm_city}?format=j1"
            max_attempts = 3
            response = None
            for attempt in range(1, max_attempts + 1):
                response = requests.get(url, timeout=DEFAULT_HTTP_TIMEOUT, headers=headers)
                if response.status_code == 200:
                    break
                if response.status_code in (429, 500, 502, 503, 504):
                    sleep_s = min(2 ** attempt + random.random(), 8)
                    logging.warning(f"Wttr transient error {response.status_code}; retrying in {sleep_s:.1f}s")
                    time.sleep(sleep_s)
                    continue
                break
            if not response or response.status_code != 200:
                logging.error(f"Failed to get weather for {city}: {response.status_code if response else 'no response'}")
                return f"Could not retrieve weather for {city}."
            try:
                data = response.json()
                current = (data.get("current_condition") or [{}])[0]
                desc = (current.get("weatherDesc") or [{"value": "N/A"}])[0].get("value")
                temp_c = current.get("temp_C")
                feels_c = current.get("FeelsLikeC")
                humidity = current.get("humidity")
                wind_kph = current.get("windspeedKmph")
                out = f"{city}: {desc}, {temp_c}°C (feels {feels_c}°C), humidity {humidity}%, wind {wind_kph} km/h"
                logging.info(f"Weather for {city}: {out}")
                return out
            except ValueError:
                logging.error("Wttr API returned non-JSON body")
                return f"Could not parse weather for {city}."
    except Exception as e:
        logging.error(f"Error retrieving weather for {city}: {e}")
        return f"An error occurred while retrieving weather for {city}." 

@function_tool()
async def get_current_time(context: RunContext,  # type: ignore, noqa: F401
    timezone: Optional[str] = None,
    utc_offset_hours: Optional[float] = None) -> str:
    """
    Return the current time with timezone awareness.
    Args:
        timezone: IANA timezone like "Africa/Nairobi" or common alias like "Kenya".
        utc_offset_hours: Numeric UTC offset (e.g., 3, -5). Used only if timezone cannot be resolved.
    Resolution order:
        1) Provided timezone (including common aliases)
        2) DEFAULT_TIMEZONE env var
        3) Provided utc_offset_hours or DEFAULT_UTC_OFFSET_HOURS env var
        4) UTC
    """
    try:
        # Map common aliases to IANA names
        alias_map = {
            'kenya': 'Africa/Nairobi',
            'nairobi': 'Africa/Nairobi',
            'eat': 'Africa/Nairobi',  # East Africa Time
            'east africa': 'Africa/Nairobi',
        }

        tz = None
        # Try provided timezone first (including alias normalization)
        if timezone and ZoneInfo:
            tz_key = timezone.strip().lower()
            tz_name = alias_map.get(tz_key, timezone)
            try:
                tz = ZoneInfo(tz_name)
            except Exception:
                logging.warning(f"Invalid timezone provided: {timezone}; will try env/offset/UTC")

        # Try DEFAULT_TIMEZONE env
        if tz is None and ZoneInfo:
            default_tz = os.getenv('DEFAULT_TIMEZONE')
            if default_tz:
                try:
                    tz = ZoneInfo(default_tz)
                except Exception:
                    logging.warning(f"Invalid DEFAULT_TIMEZONE {default_tz}; ignoring")

        # Fallback: fixed offset if available
        if tz is None:
            # Determine offset from parameter or env
            try:
                offset = utc_offset_hours
                if offset is None and os.getenv('DEFAULT_UTC_OFFSET_HOURS') is not None:
                    offset = float(os.getenv('DEFAULT_UTC_OFFSET_HOURS'))
            except Exception:
                offset = None
            if offset is not None:
                # Build a fixed-offset timezone
                from datetime import timedelta, timezone as dt_timezone
                tz = dt_timezone(timedelta(hours=float(offset)))

        # Last resort: naive UTC
        now = datetime.now(tz) if tz else datetime.utcnow()
        return now.strftime("%Y-%m-%d %H:%M:%S %Z%z")
    except Exception as e:
        logging.error(f"Error getting current time: {e}")
        return "Unable to determine current time right now."

@function_tool()
async def search_web(
    context: RunContext,  # type: ignore
    query: str) -> str:
    """
    Search the web using DuckDuckGo.
    """
    try:
        results = DuckDuckGoSearchRun().run(tool_input=query)
        logging.info(f"Search results for '{query}': {results}")
        return results
    except Exception as e:
        logging.error(f"Error searching the web for '{query}': {e}")
        return f"An error occurred while searching the web for '{query}'."    

@function_tool()    
async def send_email(
    context: RunContext,  # type: ignore
    to_email: str,
    subject: str,
    message: str,
    cc_email: Optional[str] = None,
    weather_report: Optional[str] = None,
    search_report: Optional[str] = None,
    extra_html: Optional[str] = None,
) -> str:
    """
    Send an email through Gmail.
    
    Args:
        to_email: Recipient email address
        subject: Email subject line
        message: Email body content
        cc_email: Optional CC email address
    """
    try:
        # Use Gmail REST API to send messages (no SMTP)
        gmail_user = os.getenv("GMAIL_USER")

        if not gmail_user:
            logging.error("GMAIL_USER not configured")
            return "Email sending failed: GMAIL_USER not configured."

        # Validate email format
        if not _is_valid_email(to_email):
            logging.error(f"Invalid recipient email format: {to_email}")
            return f"Email sending failed: Invalid recipient email '{to_email}'."

        if cc_email and not _is_valid_email(cc_email):
            logging.error(f"Invalid CC email format: {cc_email}")
            return f"Email sending failed: Invalid CC email '{cc_email}'."

        # Build HTML content using template and embed assets
        template_path = os.path.join('templates', 'email_template.html')
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template_html = f.read()
        except Exception as e:
            logging.error(f"Failed to load email template: {e}")
            return "Email sending failed: Could not load email template."

        # Compose message body with sections
        def section(title: str, body_html: str) -> str:
            return f'''<div style="margin:16px 0;padding:16px;border:1px solid #eee;border-radius:8px;">
                    <h3 style="margin:0 0 8px;color:#333;">{title}</h3>
                    <div style="color:#444;">{body_html}</div>
                 </div>'''

        safe_message = (message or '').replace('\n', '<br>')
        content_sections = []
        # Featured animation
        content_sections.append(
            '<div style="text-align:center;margin:8px 0 16px;">'
            '<img src="cid:robot_gif" alt="Futuristic Robot Constructor" '
            'style="max-width:100%;height:auto;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.08);"/>'
            '</div>'
        )
        if safe_message:
            content_sections.append(section('Message', safe_message))
        if weather_report:
            content_sections.append(section('Weather report', (weather_report or '').replace('\n', '<br>')))
        if search_report:
            # Wrap in <pre> to preserve formatting if it's multiline text
            sr_html = f"<pre style=\"white-space:pre-wrap;word-wrap:break-word;margin:0;\">{search_report}</pre>"
            content_sections.append(section('Search report', sr_html))
        if extra_html:
            content_sections.append(extra_html)

        composed_body = "\n".join(content_sections)
        full_html = template_html.replace('{{ message_body | safe }}', composed_body)

        # MIME structure: related -> alternative -> (plain, html)
        msg = MIMEMultipart('related')
        msg['From'] = gmail_user
        msg['To'] = to_email
        msg['Subject'] = subject
        if cc_email:
            msg['Cc'] = cc_email
        alt = MIMEMultipart('alternative')
        msg.attach(alt)
        # Plain-text fallback (strip tags minimally)
        plain_fallback = re.sub('<[^<]+?>', '', composed_body)
        alt.attach(MIMEText(plain_fallback, 'plain', 'utf-8'))
        alt.attach(MIMEText(full_html, 'html', 'utf-8'))

        # Inline images
        try:
            # Agent avatar
            with open(os.path.join('static', 'agent.png'), 'rb') as f:
                img = MIMEImage(f.read())
                img.add_header('Content-ID', '<agent_logo>')
                img.add_header('Content-Disposition', 'inline; filename="agent.png"')
                msg.attach(img)
        except Exception as e:
            logging.warning(f"agent.png not attached: {e}")
        try:
            # Feature GIF
            with open(os.path.join('static', 'Futuristic Robot Constructor.gif'), 'rb') as f:
                gif = MIMEImage(f.read(), _subtype='gif')
                gif.add_header('Content-ID', '<robot_gif>')
                gif.add_header('Content-Disposition', 'inline; filename="robot.gif"')
                msg.attach(gif)
        except Exception as e:
            logging.warning(f"Futuristic Robot Constructor.gif not attached: {e}")

        # Get access token via refresh token
        access_token = _get_google_access_token()
        if not access_token:
            logging.error("Failed to obtain Google access token")
            return "Email sending failed: Could not obtain Google access token."

        # Prepare raw message for Gmail API (base64url encoded)
        try:
            raw_bytes = msg.as_bytes()
        except Exception:
            raw_bytes = msg.as_string().encode('utf-8')

        raw_b64 = base64.urlsafe_b64encode(raw_bytes).decode('utf-8').replace('=', '')

        # Validate token scopes to ensure gmail.send is permitted
        try:
            tokeninfo = requests.get(
                'https://www.googleapis.com/oauth2/v3/tokeninfo',
                params={'access_token': access_token},
                timeout=DEFAULT_HTTP_TIMEOUT,
            )
            if tokeninfo.status_code == 200:
                scopes = set((tokeninfo.json().get('scope') or '').split())
                if 'https://www.googleapis.com/auth/gmail.send' not in scopes and 'https://mail.google.com/' not in scopes:
                    logging.error('Access token missing gmail.send scope')
                    return 'Email sending failed: Access token lacks gmail.send permission.'
            else:
                logging.warning('tokeninfo request failed; proceeding to send but errors may occur')
        except requests.RequestException:
            logging.warning('tokeninfo request error; proceeding to send but errors may occur')

        gmail_send_url = 'https://gmail.googleapis.com/gmail/v1/users/me/messages/send'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }
        payload = {'raw': raw_b64}

        resp = requests.post(gmail_send_url, headers=headers, json=payload, timeout=DEFAULT_HTTP_TIMEOUT)
        if resp.status_code in (200, 202):
            logging.info(f"Email sent successfully via Gmail API to {to_email}")
            return f"Email sent successfully to {to_email}"
        else:
            logging.error(f"Gmail API send failed ({resp.status_code})")
            return f"Email sending failed: Gmail API error {resp.status_code}."

    except requests.RequestException as e:
        logging.error(f"Gmail API request failed: {e}")
        return "Email sending failed: Gmail API request error."
    except Exception as e:
        logging.error(f"Unexpected error sending email: {e}")
        return f"An error occurred while sending email: {str(e)}"


def _is_valid_email(email: str) -> bool:
    """
    Basic email validation.
    """
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None