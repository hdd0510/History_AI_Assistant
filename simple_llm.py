from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.checkpoint.memory import MemorySaver
from langmem.short_term import SummarizationNode
from langchain_core.messages.utils import count_tokens_approximately
from langgraph.graph import START, StateGraph
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage
from langgraph.graph.message import add_messages
from typing import Sequence
from typing_extensions import Annotated, TypedDict
import asyncio

import os

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("⚠️ OPENAI_API_KEY chưa được set trong môi trường!")

model = init_chat_model("gpt-4o-mini", model_provider="openai", streaming=True,)

class State(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    language: str

prompt_template = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful assistant. Answer all questions to the best of your ability in {language}.",
        ),
        MessagesPlaceholder(variable_name="messages"),
    ]
)

async def call_model(state: State):
    prompt = prompt_template.invoke(state)
    respond = await model.ainvoke(prompt)
    return {"messages": [respond]}

# Define the node (func) in the graph
workflow = StateGraph(state_schema=State)
workflow.add_edge(START, "model")
workflow.add_node("model", call_model)

app = workflow.compile(checkpointer=MemorySaver())

async def main():
    language = "Vietnamese"
    config = {"configurable": {"thread_id": "1"}}
    while True:
        query = input("Input: ")
        if not query:
            break
        input_messages = [HumanMessage(content=query)]

        async for chunk, metadata in app.astream({"messages": input_messages, "language": language}, config, stream_mode="messages"):
            print(chunk.content, end="", flush=True)

if __name__ == "__main__":
    asyncio.run(main())