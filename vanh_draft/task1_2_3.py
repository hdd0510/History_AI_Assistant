from langchain_community.tools import BraveSearch
from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent
from langgraph_swarm import create_swarm, create_handoff_tool

def search_content_api(query: str) -> str:
    """Fetch textual historical data relevant to the query."""
    return f"[Mocked historical text results for '{query}']"

def search_image_api(query: str) -> list:
    """Fetch a list of image URLs relevant to the query."""
    # TODO: replace with real image search logic
    return [f"https://images.example.com/{query.replace(' ', '_')}.jpg"]

# --- Define Tools ---
search_history_tool = Tool(
    name="search_history",
    func=search_history_api,
    description="Use this tool to search and retrieve historical text content."
)

search_image_tool = Tool(
    name="search_image",
    func=search_image_api,
    description="Use this tool to search and fetch relevant image URLs."
)

# --- Handoff Tools for Swarm ---
handoff_to_image_agent = create_handoff_tool(
    agent_name="image_agent",
    description="Hand off to the image agent when images are needed."
)

handoff_to_content_agent = create_handoff_tool(
    agent_name="content_agent",
    description="Hand off back to the content agent after images are fetched."
)

# --- Initialize Chat Model Factory ---
def get_llm():
    # Using GPT-4o-mini via Langchain
    return init_chat_model(
        model="gpt-4o-mini",
        model_provider="openai",
        streaming=False
    )

# --- Create Content Agent ---
content_agent = create_react_agent(
    model="gpt-4o-mini",
    tools=[search_history_tool, handoff_to_image_agent],
    prompt=(
        "You are a history content assistant. "
        "User profile: language={language}, preferences={preferences}. "
        "When you receive a question, always use the search_history tool to fetch text. "
        "If the final answer would benefit from images, invoke the handoff tool to the image agent."
    ),
    name="content_agent",
    config={
        "user_profile": {
            "language": "en",          # e.g. 'en' or 'vi'
            "preferences": ["history", "images"]
        }
    }
)

# --- Create Image Agent ---
image_agent = create_react_agent(
    model="gpt-4o-mini",
    tools=[search_image_tool, handoff_to_content_agent],
    prompt=(
        "You are an image assistant. "
        "When handed off, use the search_image tool to fetch relevant image URLs for the query. "
        "Return the image links and pass back control to the content agent."
    ),
    name="image_agent",
    config={
        "user_profile": {
            "language": "en",
            "preferences": ["history", "images"]
        }
    }
)

# --- Combine Agents into a Swarm ---
swarm = create_swarm(
    agents=[content_agent, image_agent],
    default_active_agent="content_agent"
)

# --- Example of running the swarm ---
if __name__ == "__main__":
    question = "When was the Battle of Waterloo and what were its outcomes?"
    response = swarm.run(question, context={
        "language": "en", 
        "preferences": ["history", "images"]
    })
    print(response)
