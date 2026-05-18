import os, sys, json

project_dir = "D:/python/tcl/project/点餐智能体"
os.chdir(project_dir)
sys.path.insert(0, project_dir)

import dotenv
dotenv.load_dotenv("smart_dian_can/.env")

from smart_dian_can.agent.smart_agent import default_agent

print("=" * 60)
print("测试 smart_agent.py 中的 default_agent")
print("=" * 60)

try:
    response = default_agent.invoke({"messages": [{"role": "user", "content": "我想品尝正宗的川菜"}]})
    print(f"\n响应类型: {type(response)}")
    if isinstance(response, dict):
        print(f"keys: {response.keys()}")
        if "messages" in response:
            msgs = response["messages"]
            for i, m in enumerate(msgs):
                print(f"\n--- 消息 {i} ({type(m).__name__}) ---")
                print(f"工具调用: {m.tool_calls if hasattr(m, 'tool_calls') else 'N/A'}")
                content = str(m.content)[:300] if m.content else 'None'
                print(f"内容: {content}")
except Exception as e:
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("测试完成")