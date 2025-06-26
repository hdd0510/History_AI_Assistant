#!/usr/bin/env python3
import asyncio
import os
import uuid
import argparse
from dotenv import load_dotenv
import logging
from contextlib import AsyncExitStack
import concurrent.futures

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import the agent application
from src.graph_structure.graph import get_graph

async def chat_session(session_id=None, interactive=True):
    """
    Start a chat session with the agent.
    
    Args:
        session_id: Optional session ID to continue a previous conversation
        interactive: If True, runs in interactive mode; if False, processes a single message
    """
    # Generate a session ID if not provided
    if not session_id:
        session_id = 'test'
        print(f"Started new session with ID: {session_id}")
    else:
        print(f"Continuing session with ID: {session_id}")
    
    # Get graph, agent, and MongoDB context manager
    agent, saver_ctx = await get_graph(session_id)
    
    try:
        while True:
            # Get user input
            user_message = input("\nYou: ")
            
            # Exit conditions
            if user_message.lower() in ["exit", "quit", "q", "bye"]:
                print("Exiting chat session.")
                break
                
            # Process message with the graph
            print("\nAgent is thinking...")
            
            # Hàm này sẽ chạy agent.invoke trong một thread riêng biệt
            with concurrent.futures.ThreadPoolExecutor() as executor:
                result = await asyncio.get_event_loop().run_in_executor(
                    executor,
                    lambda: agent.invoke(
                        {"messages": [{"role": "user", "content": user_message}]},
                        {"configurable": {"thread_id": session_id}}
                    )
                )
            
            # Display the response
            if "messages" in result:
                # Get the latest assistant message
                assistant_messages = [msg for msg in result["messages"] if msg.type == "ai"]
                if assistant_messages:
                    latest_message = assistant_messages[-1].content
                    print(f"\nAgent: {latest_message}")
                else:
                    print("\nAgent: No response generated.")
            else:
                print(f"\nAgent: {result.get('output', 'No response generated.')}")
            
            # If not interactive, break after one exchange
            if not interactive:
                break
                
    except KeyboardInterrupt:
        print("\nChat session interrupted.")
    finally:
        # Ensure MongoDB connection is properly closed
        try:
            saver_ctx.__exit__(None, None, None)
        except Exception as e:
            logger.error(f"Error closing MongoDB connection: {e}")
    
    return session_id

async def process_single_message(message, session_id=None):
    """Process a single message and properly clean up MongoDB connection"""
    session_id = session_id or "single_message"
    
    # Get graph, agent, and MongoDB context manager
    agent, saver_ctx = await get_graph(session_id)
    
    try:
        # Process the message using ThreadPoolExecutor
        with concurrent.futures.ThreadPoolExecutor() as executor:
            result = await asyncio.get_event_loop().run_in_executor(
                executor,
                lambda: agent.invoke(
                    {"messages": [{"role": "user", "content": message}]},
                    {"configurable": {"thread_id": session_id}}
                )
            )
        
        # Display the response
        if "messages" in result:
            assistant_messages = [msg for msg in result["messages"] if msg.type == "ai"]
            if assistant_messages:
                latest_message = assistant_messages[-1].content
                print(f"\nAgent: {latest_message}")
            else:
                print("\nAgent: No response generated.")
        else:
            print(f"\nAgent: {result.get('output', 'No response generated.')}")
    finally:
        # Ensure MongoDB connection is properly closed
        try:
            saver_ctx.__exit__(None, None, None)
        except Exception as e:
            logger.error(f"Error closing MongoDB connection: {e}")

def main():
    parser = argparse.ArgumentParser(description='CLI test for Gemini History Chatbot')
    parser.add_argument('--session', '-s', help='Session ID to continue a previous conversation')
    parser.add_argument('--message', '-m', help='Single message to process (non-interactive mode)')
    
    args = parser.parse_args()
    
    # Check environment variables
    required_vars = ["GOOGLE_API_KEY", "GOOGLE_CSE_ID"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"Error: The following environment variables are missing: {', '.join(missing_vars)}")
        print("Please set them in your .env file or environment.")
        exit(1)
    
    # Run the chat session
    if args.message:
        # Non-interactive mode with a single message
        print(f"Processing message: {args.message}")
        asyncio.run(process_single_message(args.message, args.session))
    else:
        # Interactive mode
        print("Welcome to the Gemini History Chatbot CLI!")
        print("Type 'exit', 'quit', 'q', or 'bye' to end the conversation.")
        session_id = asyncio.run(chat_session(args.session))
        print(f"\nSession ID: {session_id}")
        print("You can continue this conversation later by using --session flag with this ID.")

if __name__ == "__main__":
    main() 