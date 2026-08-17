
# Offline baseline harness: current rewrite timeout behavior (pre-fix).
# Reproduces the user's log: on LLMTimeoutError the correction retry runs (2 calls).
import asyncio, sys, time, types

from api.adapters.openai_compatible_llm import LLMTimeoutError
import api.rewrite as rewrite_mod

class FakeLLM:
    def __init__(self, behavior):
        self.behavior = behavior  # "timeout" | "badjson" | "ok"
        self.calls = []
    async def complete(self, messages, **kwargs):
        self.calls.append(kwargs.get("timeout"))
        if self.behavior == "timeout":
            await asyncio.sleep(0.1)  # simulate the call budget burning
            raise LLMTimeoutError(f"LLM complete timeout ({kwargs.get('timeout')}s) model=test")
        if self.behavior == "badjson":
            return "not json at all"
        return '{"routing":{"needs_rag":true,"needs_sql":false,"structured_path":"none"},"rewritten_query":"q"}'

async def go(behavior):
    fake = FakeLLM(behavior)
    rewrite_mod.llm = fake  # rebind module global
    t0 = time.perf_counter()
    res = await rewrite_mod.rewrite_query("căn CH-10 có nhìn ra biển?", [], None)
    dt = (time.perf_counter() - t0) * 1000
    return fake, res, dt

for b in ("timeout", "badjson", "ok"):
    fake, res, dt = asyncio.run(go(b))
    print(f"behavior={b}: calls={len(fake.calls)} call_timeouts={fake.calls} elapsed_ms={dt:.1f} path={res.routing['structured_path']} degraded={res.degraded}")
