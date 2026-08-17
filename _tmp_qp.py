
from lightrag.lightrag import QueryParam
import dataclasses
fields = {f.name for f in dataclasses.fields(QueryParam)}
print("has addon_params:", "addon_params" in fields)
try:
    qp = QueryParam(mode="hybrid", only_need_context=True, hl_keywords=["a"], ll_keywords=["b"],
                    enable_rerank=False, max_entity_tokens=2000, max_relation_tokens=2000,
                    max_total_tokens=6000, addon_params={"language": "Vietnamese"})
    print("full kwargs OK ->", qp.max_entity_tokens, qp.max_total_tokens)
except TypeError as exc:
    print("full kwargs TypeError:", exc)
# mid variant: budgets WITHOUT addon_params
try:
    qp2 = QueryParam(mode="hybrid", only_need_context=True, hl_keywords=["a"], ll_keywords=["b"],
                     enable_rerank=False, max_entity_tokens=2000, max_relation_tokens=2000,
                     max_total_tokens=6000)
    print("budget-only kwargs OK ->", qp2.max_entity_tokens, qp2.max_relation_tokens, qp2.max_total_tokens, "top_k:", qp2.top_k, "chunk_top_k:", qp2.chunk_top_k)
except TypeError as exc:
    print("budget-only TypeError:", exc)
