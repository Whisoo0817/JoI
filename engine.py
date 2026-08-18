"""단일 모델 엔진 — vLLM 을 라이브러리로 프로세스 안에 하나만 올려 세 가지 일을 다 시킨다.

  1. word_states(text)   : 층 2·6 의 단어별 은닉 상태 (joi_slm 의 선형 head 입력) — decoder layer 에 hook
  2. chat(messages, ...) : 채팅 생성 (lowering · 이름 짓기)
  3. choice(prompt, letters): 1토큰 객관식 로그확률 (joi_slm 저확신 게이트)

모델은 `LLM_MODEL`(기본 cyankiwi/Qwen3.5-2B-AWQ-4bit) 하나. 프로세스당 한 번 적재(`get_engine()`),
호출은 잠금으로 직렬화한다(hook 이 잡는 상태가 그 호출의 것이도록). prefix caching 은 켜 두되(긴 lowering
프롬프트 재사용), 은닉 상태 요청만 요청별 cache_salt 로 캐시를 비켜 간다 — 캐시된 앞부분은 층 출력이 안 나오므로.
"""

from __future__ import annotations

import os
import threading
import time
import uuid

os.environ.setdefault("VLLM_ENABLE_V1_MULTIPROCESSING", "0")   # 엔진을 이 프로세스 안에 (모델 모듈에 접근하려고)

import numpy as np

MODEL_ID = os.environ.get("LLM_MODEL", "cyankiwi/Qwen3.5-2B-AWQ-4bit")
LAYERS = (2, 6)                     # 경계 head = 층 2, 타입·mods·그래프 head = 층 6 (joi_slm 학습 기준)
_GPU_MEM = float(os.environ.get("LLM_GPU_MEM", "0.5"))
_MAX_LEN = int(os.environ.get("LLM_MAX_LEN", "16384"))


class Engine:
    def __init__(self, model_id: str = MODEL_ID, layers=LAYERS):
        from vllm import LLM
        self.model_id = model_id
        self.layers = tuple(layers)
        self.llm = LLM(model=model_id, max_model_len=_MAX_LEN, gpu_memory_utilization=_GPU_MEM,
                       enforce_eager=True, enable_prefix_caching=True, max_num_seqs=8)
        self.tok = self.llm.get_tokenizer()
        self._lock = threading.RLock()
        self._cap: dict[int, np.ndarray] = {}
        self._hook_layers()

    # ── 은닉 상태 hook ──
    def _model(self):
        ec = self.llm.llm_engine.engine_core
        core = getattr(ec, "engine_core", ec)
        dw = core.model_executor.driver_worker
        mr = dw.worker.model_runner if hasattr(dw, "worker") else dw.model_runner
        return mr.model

    def _hook_layers(self):
        model = self._model()
        lm = getattr(model, "language_model", model)
        layers = lm.model.layers if hasattr(lm, "model") else lm.layers

        def mk(i):
            def hook(_mod, _inp, out):
                # vLLM decoder layer 는 (hidden, residual) 를 돌려준다 — 잔차 흐름 = 둘의 합 (HF hidden_states[i+1] 과 같음)
                h, r = out if isinstance(out, tuple) else (out, None)
                x = h if r is None else h + r
                self._cap[i] = x.detach().float().cpu().numpy()
            return hook
        for i in self.layers:
            layers[i].register_forward_hook(mk(i))

    def word_states(self, text: str):
        """텍스트 → (words, states[n_words, len(layers), H]) — 채팅 템플릿 없이 원문 그대로, 단어 마지막 토큰."""
        from vllm import SamplingParams, TokensPrompt
        words = text.split()
        enc = self.tok(text, return_offsets_mapping=True, add_special_tokens=False)
        ids, offsets = enc["input_ids"], enc["offset_mapping"]
        spans, p = [], 0
        for w in words:
            s = text.index(w, p); spans.append((s, s + len(w))); p = s + len(w)
        last = [max((ti for ti, (ts, te) in enumerate(offsets) if te > ts and ts < we and te > ws), default=None)
                for ws, we in spans]
        with self._lock:
            self._cap.clear()
            self.llm.generate([TokensPrompt(prompt_token_ids=ids, cache_salt=uuid.uuid4().hex)],   # 캐시 우회: 모든 토큰이 층을 지나야 hook 이 다 잡힘
                              SamplingParams(max_tokens=1, temperature=0), use_tqdm=False)
            cap = {i: self._cap[i] for i in self.layers}
        for i in self.layers:
            if cap[i].shape[0] != len(ids):
                raise RuntimeError(f"layer {i} states {cap[i].shape[0]} != tokens {len(ids)}")
        return words, np.stack([cap[i][last] for i in self.layers], axis=1)

    # ── 생성 ──
    def chat(self, messages, *, max_tokens=512, temperature=0.1, enable_thinking=False, prefill=None):
        """→ (text, prompt_tokens, completion_tokens, finish_reason, seconds).
        prefill: 응답이 이 텍스트로 시작하도록 강제(미완성 assistant 턴 이어쓰기)."""
        from vllm import SamplingParams
        msgs = list(messages)
        kw = {}
        if prefill:
            msgs.append({"role": "assistant", "content": prefill})
            kw = {"add_generation_prompt": False, "continue_final_message": True}
        sp = SamplingParams(max_tokens=max_tokens, temperature=temperature)
        t = time.perf_counter()
        with self._lock:
            out = self.llm.chat(msgs, sp, chat_template_kwargs={"enable_thinking": enable_thinking},
                                use_tqdm=False, **kw)[0]
        o = out.outputs[0]
        text = (prefill or "") + o.text
        return text, len(out.prompt_token_ids or []), len(o.token_ids), o.finish_reason, time.perf_counter() - t

    def choice(self, prompt: str, letters: str):
        """객관식 1토큰: 각 글자의 로그확률(없으면 -30)."""
        from vllm import SamplingParams
        with self._lock:
            out = self.llm.generate([prompt], SamplingParams(max_tokens=1, temperature=0, logprobs=20),
                                    use_tqdm=False)[0]
        top = out.outputs[0].logprobs[0] if out.outputs[0].logprobs else {}
        sc = {}
        for tid, lp in top.items():
            s = (lp.decoded_token or self.tok.decode([tid])).strip()
            if s in letters:
                sc[s] = max(sc.get(s, -30.0), lp.logprob)
        return [sc.get(L, -30.0) for L in letters]


_ENGINE = {"e": None}
_ENGINE_LOCK = threading.Lock()


def get_engine() -> Engine:
    with _ENGINE_LOCK:
        if _ENGINE["e"] is None:
            _ENGINE["e"] = Engine()
        return _ENGINE["e"]
