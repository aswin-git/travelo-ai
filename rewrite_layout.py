import re

with open("frontend/src/App.jsx", "r") as f:
    content = f.read()

# Add chatCollapsed state
content = content.replace("const [sidebarCollapsed, setSidebarCollapsed] = useState(false)", "const [sidebarCollapsed, setSidebarCollapsed] = useState(false)\n  const [chatCollapsed, setChatCollapsed] = useState(false)")

# Find chat-pane
start_chat = content.find('<div className="chat-pane">')
# Find context-pane which is immediately after chat-pane
start_context = content.find('          {/* Right Pane: Context & Results */}')
# Find the end of context-pane, which is before the Pin Popover
end_context = content.find('        {/* Pin to Day Popover */}')

chat_pane_code = content[start_chat:start_context]
context_pane_code = content[start_context:end_context]

# Replace the chat pane class and add header
chat_pane_code = chat_pane_code.replace(
    '<div className="chat-pane">',
    '<div className={`chat-side-panel ${chatCollapsed ? \'collapsed\' : \'\'}`}>\n            <div className="chat-header">\n              <button className="collapse-chat-btn" onClick={() => setChatCollapsed(!chatCollapsed)} title="Toggle Chat">\n                {chatCollapsed ? \'💬\' : \'▶\'}\n              </button>\n              {!chatCollapsed && <h2>Travel Assistant</h2>}\n            </div>'
)
chat_pane_code = chat_pane_code.replace('disabled={loading}', 'disabled={loading || chatCollapsed}')
chat_pane_code = chat_pane_code.replace('disabled={loading || !message.trim()}', 'disabled={loading || !message.trim() || chatCollapsed}')

# Replace context pane class
context_pane_code = context_pane_code.replace('<div className="context-pane">', '<div className="workspace-canvas context-pane">')

# Now rebuild the main-content
new_main_content = context_pane_code + "\n" + chat_pane_code

content = content[:start_chat] + new_main_content + content[end_context:]

with open("frontend/src/App.jsx", "w") as f:
    f.write(content)

