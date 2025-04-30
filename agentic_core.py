# ------------------------------------------------------------------
# agentic_core.py  (S‑F)
# ------------------------------------------------------------------
"""OpenAI ReAct loop with self‑reflection memory via Chroma."""
import openai
import chromadb
import datetime
import os
import json

# Ensure API key is loaded
if 'OPENAI_API_KEY' not in os.environ:
    print("Warning: OPENAI_API_KEY environment variable not set.")
    # Potentially load from a config file or other source as fallback
    # For now, agent will likely fail if key isn't set.
openai.api_key = os.getenv('OPENAI_API_KEY')

# Setup ChromaDB client
DB_PATH = os.path.join(os.path.dirname(__file__), 'agent_memory')
print(f"Initializing ChromaDB client at path: {DB_PATH}")
try:
    chroma_client = chromadb.PersistentClient(path=DB_PATH)
    # Get or create the collection for Dynasty agent memory
    memory_collection = chroma_client.get_or_create_collection('dynasty_agent_memory')
    print("ChromaDB client and collection initialized successfully.")
except Exception as e:
    print(f"Error initializing ChromaDB: {e}")
    print("Agent memory/reflection capabilities may be limited.")
    memory_collection = None # Set to None to handle potential errors gracefully

# Define the available functions for the OpenAI agent
# TODO: Expand with more functions (e.g., get_market_data, check_account_status)
FUNC_LIST = [
    {
        "name": "place_trade",
        "description": "Execute a trade (buy, sell, or hold) for a given stock ticker and quantity.",
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "The stock symbol (e.g., 'MSTR', 'AAPL')."
                },
                "action": {
                    "type": "string",
                    "enum": ["BUY", "SELL", "HOLD"],
                    "description": "The trading action to take."
                },
                "size": {
                    "type": "integer",
                    "description": "The number of shares or units to trade. Use 0 for HOLD."
                }
            },
            "required": ["ticker", "action", "size"]
        }
    }
]

def decide(features):
    """Gets a trading decision from the OpenAI agent based on input features."""
    if not openai.api_key:
        print("Error: OpenAI API key not configured. Cannot get agent decision.")
        # Return a default/safe action, e.g., HOLD
        return {"role": "assistant", "content": "Cannot decide: OpenAI API key missing.", "function_call": None}

    # TODO: Add relevant memories retrieved from ChromaDB to the prompt context
    # Example (needs refinement):
    # relevant_memories = []
    # if memory_collection:
    #     results = memory_collection.query(query_texts=[json.dumps(features)], n_results=3)
    #     if results and results.get('documents'):
    #         relevant_memories = results['documents'][0]
    # memory_context = "\n".join(relevant_memories)
    # prompt_content = f"Current Market Features:\n{json.dumps(features)}\n\nRelevant Past Experiences:\n{memory_context}"

    prompt_content = f"Current Market Features:\n{json.dumps(features)}"

    messages = [
        {'role': 'system', 'content': 'You are a disciplined volatility-harvest trading agent. Analyze the market features and decide whether to BUY, SELL, or HOLD. Use the place_trade function.'},
        {'role': 'user', 'content': prompt_content}
    ]

    try:
        response = openai.ChatCompletion.create(
            model='gpt-4o', # Or specify another suitable model
            messages=messages,
            functions=FUNC_LIST,
            function_call='auto' # Let the model decide whether to call a function
        )
        return response.choices[0].message # Return the message object (contains content and/or function_call)
    except openai.error.OpenAIError as e:
        print(f"OpenAI API error during decision making: {e}")
        # Return a safe default or error indicator
        return {"role": "assistant", "content": f"Error getting decision: {e}", "function_call": None}
    except Exception as e:
        print(f"Unexpected error during agent decision: {e}")
        return {"role": "assistant", "content": f"Unexpected error: {e}", "function_call": None}

def reflect(trade_dict, pnl):
    """Adds a reflection about a completed trade to the ChromaDB memory."""
    if not memory_collection:
        print("ChromaDB collection not available. Skipping reflection.")
        return

    try:
        # Format the reflection document
        reflection_doc = f"Timestamp: {datetime.datetime.now().isoformat()}\nTrade: {trade_dict.get('action','N/A')} {trade_dict.get('size',0)} {trade_dict.get('ticker','N/A')}\nRealized PnL: {pnl:.2f}\nNotes: [Add any qualitative notes or context here]"

        # Add the document to ChromaDB with a unique ID (timestamp)
        doc_id = str(datetime.datetime.now().timestamp())
        memory_collection.add(
            documents=[reflection_doc],
            ids=[doc_id]
            # TODO: Consider adding metadata (e.g., {'ticker': trade_dict['ticker'], 'pnl': pnl})
        )
        print(f"Reflection added to memory (ID: {doc_id}).")
    except Exception as e:
        print(f"Error adding reflection to ChromaDB: {e}")

# Example usage (for testing):
# if __name__ == '__main__':
#     test_features = {'price': 150.0, 'iv_rank': 45, 'btc_correlation': 0.7}
#     decision_msg = decide(test_features)
#     print("Decision Message:", decision_msg)
# 
#     if decision_msg.get('function_call'):
#         print("Function Call:", decision_msg['function_call'])
#         # Simulate executing the trade and getting PnL
#         args = json.loads(decision_msg['function_call']['arguments'])
#         simulated_pnl = 150.50 # Example PnL
#         reflect(args, simulated_pnl)
#     else:
#         print("Agent Response:", decision_msg.get('content'))
