"""诊断 LLM 客户端状态"""
import asyncio, time, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

async def test():
    from server.infra.llm_client.config import LLMRuntimeConfig, create_clients_from_runtime
    
    runtime = LLMRuntimeConfig.from_env()
    clients = create_clients_from_runtime(runtime)
    
    for key in ('advisor', 'law', 'enemy'):
        c = clients[key]
        print(f'[{key}]')
        print(f'  api_key: {"SET" if c.api_key else "EMPTY"} (prefix={c.api_key[:12] if c.api_key else "N/A"})')
        print(f'  model_name: {c.model_name}')
        print(f'  agent_group: {c.agent_group}')
        print(f'  fallback_mode: {c.fallback_mode}')
        print()
    
    # 测试实际调用
    print('Testing advisor chat_role...')
    c = clients['advisor']
    result = await c.chat_role(prompt='请用一句话介绍自己', system_prompt='你是AI助手')
    print(f'  Result: {repr(result[:100])}')
    print(f'  Length: {len(result)}')
    print(f'  fallback_mode after: {c.fallback_mode}')

asyncio.run(test())
