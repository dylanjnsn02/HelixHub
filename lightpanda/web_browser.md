Below is a workspace skill style document you could drop into something like skills/web_browser.md for an agent. It explains the tools, shows examples, and clarifies the state issue with goto when using mcporter CLI.

:::writing{variant=“standard” id=“48261”}

Web Browser MCP Skill

Purpose

This skill allows the agent to retrieve HTML content from websites, extract readable content, and interact with web forms using the web_browser MCP server. The server exposes tools that run JavaScript inside a headless browser.

This is useful for:
	•	scraping page content
	•	extracting links
	•	retrieving rendered HTML
	•	interacting with login forms
	•	submitting data

⸻

Important Behavior

When using mcporter from the CLI, each command runs in a new process.
Because of this, browser state is not preserved between commands.

Example of what does NOT work reliably:

mcporter call web_browser.goto url="http://example.com"
mcporter call web_browser.evaluate script="document.body.innerText"

The second command launches a new browser instance and the previous page is not loaded.

Correct Approach

Always include the url parameter in the command so navigation and extraction happen in the same call.

Example:

mcporter call web_browser.evaluate script="document.documentElement.outerHTML" url="http://example.com"


⸻

Retrieving Page Content

Get rendered HTML

Return the entire HTML of the page.

mcporter call web_browser.evaluate \
script="document.documentElement.outerHTML" \
url="https://example.com"

This returns the full DOM including JavaScript-rendered content.

⸻

Get only body HTML

mcporter call web_browser.evaluate \
script="document.body ? document.body.outerHTML : 'no body'" \
url="https://example.com"


⸻

Get readable text

mcporter call web_browser.evaluate \
script="document.body.innerText" \
url="https://example.com"


⸻

Extracting Markdown

The browser tool can convert the page to markdown automatically.

mcporter call web_browser.markdown url="https://example.com"

This is usually the best format when sending page content to an LLM because it removes unnecessary HTML structure.

⸻

Extracting Links

mcporter call web_browser.links url="https://example.com"

This returns all hyperlinks found on the page.

⸻

Interacting With Forms

Forms can be filled using JavaScript inside evaluate.

Example login form

mcporter call web_browser.evaluate script="
document.querySelector('input[name=username]').value='admin';
document.querySelector('input[name=password]').value='password123';
document.querySelector('button[type=submit]').click();
" url="http://example.com/login"

This script:
	1.	finds the username field
	2.	fills the username
	3.	fills the password
	4.	clicks the submit button

⸻

Example form submission

mcporter call web_browser.evaluate script="
document.querySelector('input[name=email]').value='user@example.com';
document.querySelector('form').submit();
" url="https://example.com/register"


⸻

Inspecting Page Structure

If the input field names are unknown, inspect the page first.

Example returning the full HTML:

mcporter call web_browser.evaluate \
script="document.documentElement.outerHTML" \
url="https://example.com"

Then examine the <input> elements and determine the selectors.

Example selectors:

input[name=username]
input[id=password]
button[type=submit]
form


⸻

Best Practices

Always include the url argument when using evaluate, markdown, or links.

Prefer markdown when extracting content for LLM processing.

Use evaluate when interacting with forms or running custom JavaScript.

Use document.documentElement.outerHTML when the full HTML structure is required.

⸻

Example Workflow

Retrieve readable content from a page:

mcporter call web_browser.markdown url="https://example.com"

Extract links:

mcporter call web_browser.links url="https://example.com"

Submit login form:

mcporter call web_browser.evaluate script="
document.querySelector('input[name=username]').value='admin';
document.querySelector('input[name=password]').value='password123';
document.querySelector('button[type=submit]').click();
" url="https://example.com/login"

:::

If you want, I can also show you a much stronger version of this skill that teaches the agent how to automatically discover form fields and log into arbitrary sites, which dramatically improves reliability when used with reasoning models.