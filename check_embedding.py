from api.config import Settings
s = Settings()
print('AIBox model:', s.embedding_model)
print('Jina model:', s.jina_embedding_model)
print('AIBox dim:', s.embedding_dim)
print('Jina dim:', s.jina_embedding_dim)
print()
print('WARNING: Different models = different vector spaces!')
print('Switching binding WITHOUT re-embed will BREAK retrieval.')
