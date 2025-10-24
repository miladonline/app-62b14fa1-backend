"""MCP server for simple hello world app

This server uses the official MCP SDK with FastMCP and exposes widget-backed tools
that render interactive UI components in ChatGPT. Each handler returns structured
content that hydrates the widget and provides the model with relevant context."""

from __future__ import annotations

import os
from typing import Any, Dict, List
from urllib.request import urlopen

import mcp.types as types
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP(
    name="hello-world",
    sse_path="/mcp",
    message_path="/mcp/messages",
    stateless_http=True,
)

# Fetch widget bundle from GitHub at startup
WIDGET_REPO_URL = os.environ.get("WIDGET_REPO_URL", "")
WIDGET_BUNDLE = ""

if WIDGET_REPO_URL:
    try:
        with urlopen(WIDGET_REPO_URL, timeout=10) as response:
            WIDGET_BUNDLE = response.read().decode('utf-8')
        print(f"✅ Widget bundle loaded from GitHub ({len(WIDGET_BUNDLE)} bytes)")
    except Exception as e:
        print(f"⚠️  Failed to load widget bundle: {e}")
        WIDGET_BUNDLE = "console.error('Widget bundle not loaded');"
else:
    print("⚠️  WIDGET_REPO_URL not set, widget will not load")
    WIDGET_BUNDLE = "console.error('WIDGET_REPO_URL not configured');"

# HTML template with inline embedded widget bundle
# IMPORTANT: Use plain <script> tag (NOT type=\"module\") for IIFE bundles
WIDGET_HTML = f'''
<div id="root"></div>
<script>
{WIDGET_BUNDLE}
</script>
'''.strip()

# Define widget configuration
WIDGET_URI = "ui://widget/widget.html"
MIME_TYPE = "text/html+skybridge"


# Register resources
@mcp._mcp_server.list_resources()
async def _list_resources() -> List[types.Resource]:
    """List available resources."""
    return [
        types.Resource(
            uri=WIDGET_URI,
            name="Hello World Widget",
            title="Hello World Widget",
            description="Interactive hello world widget UI",
            mimeType=MIME_TYPE,
        )
    ]


# Register resource templates
@mcp._mcp_server.list_resource_templates()
async def _list_resource_templates() -> List[types.ResourceTemplate]:
    """Register UI resource templates available to the client."""
    return [
        types.ResourceTemplate(
            uriTemplate=WIDGET_URI,
            name="Hello World Widget",
            title="Hello World Widget",
            description="Interactive hello world widget UI template",
            mimeType=MIME_TYPE,
        )
    ]


# Handle resource read requests
async def _handle_read_resource(
    request: types.ReadResourceRequest,
) -> types.ReadResourceResult:
    """Serve the HTML shell that loads the widget bundle."""
    if str(request.params.uri) != WIDGET_URI:
        raise ValueError(f"Unknown resource URI: {request.params.uri}")

    return types.ReadResourceResult(
        contents=[
            types.TextResourceContents(
                uri=WIDGET_URI,
                mimeType=MIME_TYPE,
                text=WIDGET_HTML,
                _meta={
                    "openai/widgetPrefersBorder": True,
                    "openai/widgetDomain": "https://chatgpt.com",
                    "openai/widgetCSP": {
                        "connect_domains": ["https://chatgpt.com"],
                        "resource_domains": ["https://persistent.oaistatic.com"],
                    },
                    "openai/widgetDescription": "Interactive hello world display"
                }
            )
        ]
    )


# Register tools
@mcp._mcp_server.list_tools()
async def _list_tools() -> List[types.Tool]:
    """Register tools that the model can invoke."""
    return [
        types.Tool(
            name="say_hello",
            title="Say Hello",
            description="Generates a personalized hello world greeting with optional custom message",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the person to greet (defaults to 'World')",
                    },
                    "message": {
                        "type": "string",
                        "description": "Optional custom message to display",
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
            _meta={
                "openai/outputTemplate": WIDGET_URI,
                "openai/toolInvocation/invoking": "Generating hello world greeting...",
                "openai/toolInvocation/invoked": "Greeting generated successfully",
                "openai/widgetAccessible": True,
                "openai/resultCanProduceWidget": True,
                "annotations": {
                    "destructiveHint": False,
                    "openWorldHint": False,
                    "readOnlyHint": True,
                },
            },
        )
    ]


# Handle tool calls
async def _call_tool_request(
    request: types.CallToolRequest,
) -> types.CallToolResult:
    """Handle tool invocations and return structured content for the widget."""
    tool_name = request.params.name
    arguments = request.params.arguments or {}

    if tool_name == "say_hello":
        # Extract parameters
        name = arguments.get("name", "World")
        message = arguments.get("message", "Welcome to the Hello World app!")

        # Generate greeting data
        data = {
            "greeting": f"Hello, {name}!",
            "message": message,
            "timestamp": "2024-01-01T00:00:00Z",
            "metadata": {
                "app": "Hello World MCP",
                "version": "1.0.0",
            },
        }

        # Return structured content for the widget
        return types.CallToolResult(
            content=[
                types.TextContent(
                    type="text",
                    text=f"Hello, {name}! {message}",
                )
            ],
            structuredContent={
                "greeting": data["greeting"],
                "message": data["message"],
            },
            _meta={
                "fullData": data,  # Complete dataset for component (not visible to model)
            },
        )

    raise ValueError(f"Unknown tool: {tool_name}")


# Register request handlers
mcp._mcp_server.request_handlers[types.CallToolRequest] = _call_tool_request
mcp._mcp_server.request_handlers[types.ReadResourceRequest] = _handle_read_resource


# Create ASGI app with CORS
app = mcp.streamable_http_app()

try:
    from starlette.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=False,
    )
except Exception:
    pass


# Enable local testing with: python main.py
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
