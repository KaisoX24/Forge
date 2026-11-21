from api.services.reasoning_models.model_settings import *
print(load_max_context())       # None (Auto)
save_max_context(12288)
print(load_max_context())       # 12288
print(load_max_context())       # None again