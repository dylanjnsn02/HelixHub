# Chrome CDP Browser Control

Control a Chrome browser via the Chrome DevTools Protocol. Supports both local and remote browsers. No screenshot capability — text-only interaction to save tokens.

## Prerequisites

Chrome must be running with remote debugging enabled:

**macOS:**
```
open -a "Google Chrome" --args --remote-debugging-port=9222
```

**Linux:**
```
google-chrome --remote-debugging-port=9222
```

**Remote browser (via SSH tunnel):**
```
ssh -L 9222:localhost:9222 user@remote-host
```
Then connect as if it's local on localhost:9222.

## When to Use

- Navigating web pages and reading their content
- Filling out forms and clicking buttons
- Running JavaScript on pages
- Scraping text content from web pages
- Interacting with web applications
- Any browser automation that doesn't need screenshots

## Available Tools

### list_tabs
List all open Chrome tabs with their titles and URLs.
- `host` (str, default "localhost"): Chrome DevTools host
- `port` (int, default 9222): Chrome DevTools port

### navigate
Navigate a tab to a URL and optionally wait for the page to load.
- `url` (str): URL to navigate to
- `tab_index` (int, default 0): which tab to use
- `wait_for_load` (bool, default true): wait for page load event

### evaluate
Run JavaScript in the page and return the result.
- `expression` (str): JavaScript expression to evaluate
- `tab_index` (int, default 0): which tab to use

### get_page_content
Get the current page content as text or HTML.
- `format` (str, default "text"): "text" for innerText (saves tokens) or "html" for full HTML
- `tab_index` (int, default 0): which tab to use

### click
Click a DOM element by CSS selector.
- `selector` (str): CSS selector for the element
- `tab_index` (int, default 0): which tab to use

### type_text
Type text into an input or textarea element.
- `selector` (str): CSS selector for the input
- `text` (str): text to type
- `clear_first` (bool, default true): clear existing value first
- `tab_index` (int, default 0): which tab to use

### query_elements
Find elements matching a CSS selector and return tag, id, classes, text, href, type, value, and name.
- `selector` (str): CSS selector to query
- `limit` (int, default 20): max elements to return
- `tab_index` (int, default 0): which tab to use

### get_element_attributes
Get all attributes of a specific element by CSS selector.
- `selector` (str): CSS selector for the element
- `tab_index` (int, default 0): which tab to use

## Example Requests

- "Open google.com in Chrome and search for something"
- "List all the links on the current page"
- "Fill out the login form with username and password"
- "Click the submit button"
- "Get the text content of the page"
- "Run this JavaScript on the page"
- "Find all buttons on the page"
