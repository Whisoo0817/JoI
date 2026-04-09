import time
import os
import sys

from config import get_client, get_model_id
from loader import PROMPTS

def warmup(debug=False, base_url=None):
    """서버 시작 후 모든 system prompt를 미리 캐싱하여 첫 요청의 지연시간을 줄임"""
    client = get_client(base_url)
    model = get_model_id(client)
    
    # 기기 규칙을 제외한 일반 프롬프트들만 캐싱 (용량 조절)
    prompts_copy = {k: v for k, v in PROMPTS.items()
                     if not k.startswith("device_rules_")}
    prompts_copy.pop("service_summary", None)
    
    print(f"[warmup] Caching {len(prompts_copy)} PROMPTS...")
    start = time.perf_counter()
    
    for name, prompt in prompts_copy.items():
        try:
            # 1개 토큰만 생성하도록 유도하여 캐싱만 진행
            client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": "hi"}
                ],
                max_tokens=1,
                temperature=0.0,
                stream=False,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}}
            )
            if debug:
                print(f"[warmup] cached: {name}")
        except Exception as e:
            print(f"[warmup] failed: {name} ({e})")
            
    print(f"[warmup] Done in {time.perf_counter() - start:.2f}s")

if __name__ == "__main__":
    # Usage: python warmup.py [debug] [base_url]
    debug_mode = "debug" in sys.argv
    url = None
    for arg in sys.argv:
        if arg.startswith("http"):
            url = arg
            print(arg)
            break
            
    warmup(debug=debug_mode, base_url=url)
