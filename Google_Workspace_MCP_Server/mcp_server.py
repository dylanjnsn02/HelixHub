# mcp_server.py
import base64
import html as html_module
import os
import re
import sys
from typing import Dict, Any, AsyncIterator, Optional, List
from contextlib import asynccontextmanager
import io
from email.message import EmailMessage

import google.oauth2.credentials
import googleapiclient.discovery
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload

from mcp.server.fastmcp import FastMCP, Context
from pydantic import BaseModel, Field

from config import TOKEN_PATH, SCOPES

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

class EventDetails(BaseModel):
    summary: str = Field(description="The title or summary of the calendar event.")
    start_time: str = Field(description="The start time of the event in ISO 8601 format (e.g., '2025-07-05T15:00:00').")
    end_time: str = Field(description="The end time of the event in ISO 8601 format (e.g., '2025-07-05T16:00:00').")
    description: Optional[str] = Field(None, description="A detailed description for the event. Can include notes from the source email.")

"""
EventUpdateDetails is for updating an event. When you update an event, you often only want to change one or two things (e.g., just the title,
or just the end time). If we used the original EventDetails model, the agent would be forced to provide values for all fields, even the ones 
it wasn't changing. By making all fields in EventUpdateDetails Optional, we allow for partial updates. The agent can provide only the fields 
it wants to change, making the tool much more flexible and easier to use.
"""
class EventUpdateDetails(BaseModel):
    summary: Optional[str] = Field(None, description="The new title for the event.")
    start_time: Optional[str] = Field(None, description="The new start time in ISO 8601 format.")
    end_time: Optional[str] = Field(None, description="The new end time in ISO 8601 format.")
    description: Optional[str] = Field(None, description="The new description for the event.")

class EmailContent(BaseModel):
    to: str = Field(description="The recipient's email address.")
    subject: str = Field(description="The subject line of the email.")
    body: str = Field(description="The plain text body of the email.")

class ListedEvent(BaseModel):
    id: str = Field(description="The unique ID of the event.")
    summary: str = Field(description="The title of the event.")
    start_time: str = Field(description="The start time of the event in ISO 8601 format.")
    end_time: str = Field(description="The end time of the event in ISO 8601 format.")

class ListedDriveFile(BaseModel):
    id: str = Field(description="The unique ID of the file.")
    name: str = Field(description="The name of the file.")
    mime_type: str = Field(description="The MIME type of the file (e.g., 'application/vnd.google-apps.document').")


# --- Lifespan Management for Credentials ---

@asynccontextmanager
async def credential_manager(server: FastMCP) -> AsyncIterator[Dict[str, Any]]:
    """
    Manages loading and refreshing Google API credentials on server startup.
    """
    creds = None
    if not os.path.exists(TOKEN_PATH):
        print(f"ERROR: Token file '{TOKEN_PATH}' not found.", file=sys.stderr)
        print("Please run 'python get_credentials.py' first to authorize the application.", file=sys.stderr)
        # Yield an empty context and let tool calls fail gracefully
        yield {"creds": None}
        return

    # print(f"Loading credentials from {TOKEN_PATH}", file=sys.stderr)
    creds = google.oauth2.credentials.Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if creds and creds.expired and creds.refresh_token:
        print("Credentials expired. Refreshing...", file=sys.stderr)
        try:
            creds.refresh(Request())
            # Re-save the refreshed token
            with open(TOKEN_PATH, 'w') as token_file:
                token_file.write(creds.to_json())
            print("Token refreshed and saved.", file=sys.stderr)
        except Exception as e:
            print(f"ERROR: Failed to refresh token: {e}", file=sys.stderr)
            creds = None # Mark credentials as invalid
            
    # Make credentials available to all tool handlers via context
    yield {"creds": creds}
    print("Server shutting down.", file=sys.stderr)

# Initialize the server with the lifespan manager
server = FastMCP(
    "GsuiteMCPServer",
    lifespan=credential_manager
)

def get_creds_from_context(ctx: Context) -> google.oauth2.credentials.Credentials:
    """Helper to get credentials from the context and handle errors."""
    creds = ctx.request_context.lifespan_context.get("creds")
    if not creds or not creds.valid:
        raise Exception(
            "Google API credentials are not available or invalid. "
            "Please run 'python get_credentials.py' to authenticate."
        )
    return creds

def _get_part_by_mime(payload: Dict[str, Any], mime: str) -> Optional[str]:
    """Recursively finds a part with the given MIME type and returns its decoded body."""
    if 'parts' in payload:
        for part in payload['parts']:
            if part.get('mimeType') == mime and part.get('body', {}).get('data'):
                return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
            found = _get_part_by_mime(part, mime)
            if found:
                return found
    elif payload.get('mimeType') == mime and payload.get('body', {}).get('data'):
        return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
    return None


def _html_to_plain(html_str: str) -> str:
    """Convert HTML to plain text: strip tags, unescape entities, normalize whitespace."""
    # Replace block elements with newlines so structure is preserved
    html_str = re.sub(r'<(br|p|div|tr|li|h[1-6])\b[^>]*>', '\n', html_str, flags=re.IGNORECASE)
    html_str = re.sub(r'<[^>]+>', ' ', html_str)
    html_str = html_module.unescape(html_str)
    html_str = re.sub(r'[ \t]+', ' ', html_str)
    html_str = re.sub(r'\n\s*\n', '\n\n', html_str)
    return html_str.strip()


def get_email_body(payload: Dict[str, Any]) -> Optional[str]:
    """Recursively finds the body: prefers text/plain, falls back to text/html (converted to plain)."""
    plain = _get_part_by_mime(payload, 'text/plain')
    if plain:
        return plain
    html = _get_part_by_mime(payload, 'text/html')
    if html:
        return _html_to_plain(html)
    return None

# --- GMAIL TOOLS ---

@server.tool()
def read_gmail_emails(num_emails: int, ctx: Context) -> str:
    """
    Reads the latest emails (count defined by num_emails) from the user's Gmail inbox, excluding 
    auto-generated Gmail messages (like "This message was automatically generated by Gmail.") and 
    those without a plain text or HTML body. Returns a markdown string.
    """
    creds = get_creds_from_context(ctx)
    try:
        gmail_service = googleapiclient.discovery.build('gmail', 'v1', credentials=creds)
        # Fetch more than requested so we can skip auto-generated and blank ones
        messages_list = gmail_service.users().messages().list(userId='me', maxResults=max(50, num_emails * 4)).execute()

        if not messages_list.get('messages'):
            return "No emails found."
        
        _GMAIL_AUTO_BODY_MARKER = "This message was automatically generated by Gmail."
        kept = []
        for msg_info in messages_list['messages']:
            if len(kept) >= num_emails:
                break
            msg = gmail_service.users().messages().get(userId='me', id=msg_info['id'], format='full').execute()
            body = get_email_body(msg['payload'])
            if not body:
                continue
            body_stripped = body.strip()
            if body_stripped == _GMAIL_AUTO_BODY_MARKER or _GMAIL_AUTO_BODY_MARKER in body_stripped:
                continue
            kept.append({
                'id': msg.get('id', '<unknown>'),
                'snippet': msg.get('snippet', ''),
                'body': body,
            })

        if not kept:
            return "No emails found (after excluding auto-generated Gmail messages and empty bodies)."

        md_lines = [f"# Last {len(kept)} Emails\n"]
        for idx, item in enumerate(kept, 1):
            md_lines.append(
                f"## Email {idx}\n- **ID:** `{item['id']}`\n- **Snippet:** {item['snippet']}\n\n**Body:**\n\n```\n{item['body']}\n```\n"
            )
        return "\n".join(md_lines)
    except HttpError as e:
        raise Exception(f"API Gmail error (HTTP {e.status_code}): {e.reason}")

# Body text that marks Gmail auto-generated messages (e.g. labels, filters); we skip these in get_last_10_emails.
_GMAIL_AUTO_BODY_MARKER = "This message was automatically generated by Gmail."

@server.tool()
def get_last_10_emails(ctx: Context) -> str:
    """
    Gets the last 10 emails from the user's Gmail inbox, excluding auto-generated Gmail
    messages (e.g. "This message was automatically generated by Gmail."). Returns a
    markdown string with id, snippet, and body for each.
    """
    creds = get_creds_from_context(ctx)
    try:
        gmail_service = googleapiclient.discovery.build('gmail', 'v1', credentials=creds)
        # Fetch more than 10 so we can skip auto-generated and still return 10 real emails
        messages_list = gmail_service.users().messages().list(userId='me', maxResults=50).execute()

        if not messages_list.get('messages'):
            return "No emails found."

        kept = []
        for msg_info in messages_list['messages']:
            if len(kept) >= 10:
                break
            msg = gmail_service.users().messages().get(userId='me', id=msg_info['id'], format='full').execute()
            body = get_email_body(msg['payload']) or "Could not extract plain text body."
            body_stripped = body.strip()
            if body_stripped == _GMAIL_AUTO_BODY_MARKER or _GMAIL_AUTO_BODY_MARKER in body_stripped:
                continue
            kept.append({
                'id': msg.get('id', '<unknown>'),
                'snippet': msg.get('snippet', ''),
                'body': body,
            })

        if not kept:
            return "No emails found (after excluding auto-generated Gmail messages)."

        md_lines = ["# Last 10 Emails\n"]
        for idx, item in enumerate(kept, 1):
            md_lines.append(
                f"## Email {idx}\n- **ID:** `{item['id']}`\n- **Snippet:** {item['snippet']}\n\n**Body:**\n\n```\n{item['body']}\n```\n"
            )
        return "\n".join(md_lines)
    except HttpError as e:
        raise Exception(f"API Gmail error (HTTP {e.status_code}): {e.reason}")

@server.tool()
def read_email_by_subject(subject: str, ctx: Context) -> List[Dict[str, str]]:
    """
    Searches for emails by subject and returns the body and snippet of the most recent matches.
    
    Args:
        subject: The subject line to search for.
    """
    creds = get_creds_from_context(ctx)
    try:
        gmail_service = googleapiclient.discovery.build('gmail', 'v1', credentials=creds)
        # Search for messages with the given subject, get the most recent 5
        results = gmail_service.users().messages().list(userId='me', q=f'subject:"{subject}"', maxResults=5).execute()
        messages = results.get('messages', [])

        if not messages:
            return [{"status": f"No emails found with subject: '{subject}'"}]

        emails = []
        for msg_info in messages:
            msg = gmail_service.users().messages().get(userId='me', id=msg_info['id'], format='full').execute()
            body = get_email_body(msg['payload']) or "Could not extract plain text body."
            emails.append({'id': msg['id'], 'snippet': msg.get('snippet', ''), 'body': body})
        return emails
    except HttpError as e:
        raise Exception(f"API Gmail error (HTTP {e.status_code}): {e.reason}")

@server.tool()
def send_email(email_content: EmailContent, ctx: Context) -> Dict[str, str]:
    """
    Sends an email from the user's Gmail account.

    Args:
        email_content: A structured object containing the recipient, subject, and body.
    """
    creds = get_creds_from_context(ctx)
    try:
        gmail_service = googleapiclient.discovery.build('gmail', 'v1', credentials=creds)
        message = EmailMessage()
        message.set_content(email_content.body)
        message['To'] = email_content.to
        message['Subject'] = email_content.subject

        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {'raw': encoded_message}
        
        send_message = gmail_service.users().messages().send(userId="me", body=create_message).execute()
        return {"status": "Email sent successfully", "messageId": send_message['id']}
    except HttpError as e:
        raise Exception(f"API Gmail error (HTTP {e.status_code}): {e.reason}")

@server.tool()
def mark_email_as_read(message_id: str, ctx: Context) -> Dict[str, str]:
    """
    Marks an email as read by removing the UNREAD label. Use the message ID returned
    by get_last_10_emails, read_latest_gmail_email, or read_email_by_subject.

    Args:
        message_id: The Gmail message ID of the email to mark as read.
    """
    creds = get_creds_from_context(ctx)
    try:
        gmail_service = googleapiclient.discovery.build('gmail', 'v1', credentials=creds)
        gmail_service.users().messages().modify(
            userId='me',
            id=message_id,
            body={'removeLabelIds': ['UNREAD']}
        ).execute()
        return {"status": "Email marked as read", "messageId": message_id}
    except HttpError as e:
        raise Exception(f"API Gmail error (HTTP {e.status_code}): {e.reason}")

# --- CALENDAR TOOLS ---

@server.tool()
def list_calendar_events(ctx: Context, start_time: str, end_time: str, query: Optional[str] = None) -> List[ListedEvent]:
    """
    Lists calendar events within a specified time range, optionally filtering by a search query.

    Args:
        start_time: The start of the time range in ISO 8601 format (e.g., '2025-07-05T00:00:00Z').
        end_time: The end of the time range in ISO 8601 format (e.g., '2025-07-06T00:00:00Z').
        query: An optional text query to filter events by (e.g., 'meeting').
    """
    creds = get_creds_from_context(ctx)
    try:
        calendar_service = googleapiclient.discovery.build('calendar', 'v3', credentials=creds)
        events_result = calendar_service.events().list(
            calendarId='primary', 
            timeMin=start_time, 
            timeMax=end_time,
            q=query, # TODO: study it
            maxResults=20,  # Limit results to a reasonable number
            singleEvents=True, 
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        if not events:
            return []

        listed_events = []
        for event in events:
            # Handle all-day events which have 'date' instead of 'dateTime'
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            listed_events.append(
                ListedEvent(
                    id=event['id'],
                    summary=event.get('summary', 'No Title'),
                    start_time=start,
                    end_time=end
                )
            )
        return listed_events
    except HttpError as e:
        raise Exception(f"API Calendar error (HTTP {e.status_code}): {e.reason}")

@server.tool()
def create_calendar_event(event_details: EventDetails, ctx: Context) -> Dict[str, Any]:
    """
    Creates a Google Calendar event from structured event details.
    
    Args:
        event_details: A structured object containing the summary, start time, end time, and description.
    """
    creds = get_creds_from_context(ctx)
    event_body = {
        'summary': event_details.summary,
        'description': event_details.description or f'Created from an email automation.',
        'start': {'dateTime': event_details.start_time, 'timeZone': 'Europe/Rome'},
        'end': {'dateTime': event_details.end_time, 'timeZone': 'Europe/Rome'},
    }

    try:
        calendar_service = googleapiclient.discovery.build('calendar', 'v3', credentials=creds)
        created_event = calendar_service.events().insert(calendarId='primary', body=event_body).execute()
        return created_event
    except HttpError as e:
        raise Exception(f"API Calendar error (HTTP {e.status_code}): {e.reason}")

@server.tool()
def delete_calendar_event(event_id: str, ctx: Context) -> Dict[str, str]:
    """
    Deletes a calendar event by its ID. To get an event ID, first list or search for events.

    Args:
        event_id: The unique ID of the event to delete.
    """
    creds = get_creds_from_context(ctx)
    try:
        calendar_service = googleapiclient.discovery.build('calendar', 'v3', credentials=creds)
        calendar_service.events().delete(calendarId='primary', eventId=event_id).execute()
        return {"status": "Event deleted successfully"}
    except HttpError as e:
        raise Exception(f"API Calendar error (HTTP {e.status_code}): {e.reason}")

@server.tool()
def update_calendar_event(event_id: str, update_details: EventUpdateDetails, ctx: Context) -> Dict[str, Any]:
    """
    Updates an existing calendar event by its ID. Only provided fields will be updated.

    Args:
        event_id: The ID of the event to update.
        update_details: A structured object with the fields to update.
    """
    creds = get_creds_from_context(ctx)
    try:
        calendar_service = googleapiclient.discovery.build('calendar', 'v3', credentials=creds)
        # First, get the existing event to ensure it exists and to merge updates
        event = calendar_service.events().get(calendarId='primary', eventId=event_id).execute()

        # Create the update body with only the fields that are provided
        update_body = update_details.model_dump(exclude_unset=True)
        if 'start_time' in update_body:
            event['start']['dateTime'] = update_body['start_time']
        if 'end_time' in update_body:
            event['end']['dateTime'] = update_body['end_time']
        if 'summary' in update_body:
            event['summary'] = update_body['summary']
        if 'description' in update_body:
            event['description'] = update_body['description']
            
        updated_event = calendar_service.events().update(calendarId='primary', eventId=event['id'], body=event).execute()
        return updated_event
    except HttpError as e:
        raise Exception(f"API Calendar error (HTTP {e.status_code}): {e.reason}")

# --- GOOGLE DRIVE TOOLS ---

@server.tool()
def list_drive_files(query: str, ctx: Context) -> str:
    """
    Searches for files in Google Drive using a query string.

    Args:
        query: The search query. Examples: "name contains 'report'", "mimeType='application/vnd.google-apps.spreadsheet'".
               See Google Drive API docs for full query syntax.
    Returns:
        A markdown-formatted string listing the matching files.
    """
    creds = get_creds_from_context(ctx)
    try:
        drive_service = googleapiclient.discovery.build('drive', 'v3', credentials=creds)
        
        results = drive_service.files().list(
            q=query,
            pageSize=20,
            fields="nextPageToken, files(id, name, mimeType)"
        ).execute()
        
        files = results.get('files', [])
        if not files:
            return "No matching files found."

        md_lines = ["# Google Drive Search Results\n"]
        for idx, file in enumerate(files, 1):
            md_lines.append(
                f"## File {idx}\n"
                f"- **ID:** `{file['id']}`\n"
                f"- **Name:** {file['name']}\n"
                f"- **MIME Type:** `{file['mimeType']}`\n"
            )
        return "\n".join(md_lines)
    except HttpError as e:
        raise Exception(f"API Drive error (HTTP {e.status_code}): {e.reason}")

@server.tool()
def create_drive_document(ctx: Context, title: str, content: Optional[str] = "") -> Dict[str, str]:
    """
    Creates a new Google Document in the user's Drive with the given title and content.

    Args:
        title: The title of the new document.
        content: The initial text content for the document.
    """
    creds = get_creds_from_context(ctx)
    try:
        drive_service = googleapiclient.discovery.build('drive', 'v3', credentials=creds)
        file_metadata = {
            'name': title,
            'mimeType': 'application/vnd.google-apps.document'
        }
        
        media = MediaIoBaseUpload(io.BytesIO((content or "").encode()), mimetype='text/plain', resumable=True)
        file = drive_service.files().create(body=file_metadata, media_body=media, fields='id,name,webViewLink').execute()
        return {"status": "Document created", "id": file['id'], "name": file['name'], "link": file['webViewLink']}
    except HttpError as e:
        raise Exception(f"API Drive error (HTTP {e.status_code}): {e.reason}")

@server.tool()
def update_drive_document(file_id: str, content: str, ctx: Context) -> Dict[str, str]:
    """
    Overwrites the content of an existing Google Document.

    Args:
        file_id: The ID of the document to update.
        content: The new text content to write to the document.
    """
    creds = get_creds_from_context(ctx)
    try:
        drive_service = googleapiclient.discovery.build('drive', 'v3', credentials=creds)
        media = MediaIoBaseUpload(io.BytesIO(content.encode()), mimetype='text/plain', resumable=True)
        updated_file = drive_service.files().update(fileId=file_id, media_body=media, fields='id,name').execute()
        return {"status": "Document updated", "id": updated_file['id'], "name": updated_file['name']}
    except HttpError as e:
        raise Exception(f"API Drive error (HTTP {e.status_code}): {e.reason}")

# Dangerous. Use with caution.
@server.tool()
def delete_drive_file(file_id: str, ctx: Context) -> Dict[str, str]:
    """
    Permanently deletes a file from Google Drive. This action cannot be undone.

    Args:
        file_id: The ID of the file to delete.
    """
    creds = get_creds_from_context(ctx)
    try:
        drive_service = googleapiclient.discovery.build('drive', 'v3', credentials=creds)
        drive_service.files().delete(fileId=file_id).execute()
        return {"status": f"File with ID '{file_id}' deleted successfully."}
    except HttpError as e:
        raise Exception(f"API Drive error (HTTP {e.status_code}): {e.reason}")

@server.tool()
def move_drive_file_to_bin(file_id: str, ctx: Context) -> Dict[str, str]:
    """
    Moves a file to the Google Drive bin (trash). The file can be restored from the bin later.

    Args:
        file_id: The ID of the file to move to the bin.
    """
    creds = get_creds_from_context(ctx)
    try:
        drive_service = googleapiclient.discovery.build('drive', 'v3', credentials=creds)
        
        # To move a file to the bin, we update its metadata to set 'trashed' to True.
        body = {'trashed': True}
        drive_service.files().update(fileId=file_id, body=body).execute()
        
        return {"status": f"File with ID '{file_id}' moved to bin successfully."}
    except HttpError as e:
        raise Exception(f"API Drive error (HTTP {e.status_code}): {e.reason}")

if __name__ == "__main__":
    server.run()