import sys
print(f"Python: {sys.executable}", flush=True)

try:
    from langchain.agents import create_agent
    import inspect
    sig = inspect.signature(create_agent)
    print(f"create_agent signature: {sig}", flush=True)
except ImportError as e:
    print(f"create_agent not found: {e}", flush=True)

try:
    import langchain
    print(f"langchain version: {langchain.__version__}", flush=True)
except Exception as e:
    print(f"langchain import error: {e}", flush=True)

try:
    from langchain_openai import ChatOpenAI
    print("ChatOpenAI imported successfully", flush=True)
except ImportError as e:
    print(f"ChatOpenAI import error: {e}", flush=True)