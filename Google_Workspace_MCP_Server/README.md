# Google Workspace MCP Server

## Step 1: Configure your Google Cloud Project

You need to authorize this application to access your Google data. This is a one-time setup.

1. **Go to the Google Cloud Console:** https://console.cloud.google.com/

2. **Create a new project** (or use an existing one).

3. **Enable APIs:**
   - Go to **"APIs & Services"** → **"Library"**.
   - Search for and **Enable the Gmail API**.
   - Search for and **Enable the Google Calendar API**.
   - Search for and **Enable the Google Drive API**.

4. **Create OAuth Credentials:**
   - Go to **"APIs & Services"** → **"Credentials"**.
   - Click **"Create Credentials"** → **"OAuth client ID"**.
   - If prompted, configure the **"OAuth consent screen"**. Choose **External** and provide a name for the app. You can skip most other fields for personal use. Add your Google account email as a **Test User**.
   - For **"Application type"**, select **Desktop app**.
   - Give it a name (e.g., **"GSuite MCP Client"**).

5. **Download Credentials:**
   - After creating the client ID, click the **"Download JSON"** icon.
   - Rename the downloaded file to **`client_secrets.json`** and place it in the root directory of this project.
