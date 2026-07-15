# vLLM V1 KV Cache Profiling Implementation Guide

This guide details the modifications required to implement granular KV cache profiling in the vLLM V1 engine. It distinguishes between **Active**, **Prefix-Cached**, and **Free** blocks and logs their utilization in both percentage and GB.

---

## 1. Core Logic: Block Categorization
**File**: `vllm/v1/core/block_pool.py`

Add the `get_detailed_stats` method to the `BlockPool` class to classify blocks based on their reference count and hash status.

```python
def get_detailed_stats(self) -> dict:
    all_blocks = [b for b in self.all_blocks if not b.is_null]
    total = len(all_blocks)
    
    # Active: Currently being used by a request
    active = sum(1 for b in all_blocks if b.ref_cnt > 0)
    
    # Prefix-Cached: ref_cnt is 0 but block_hash exists (available for reuse)
    cached = sum(1 for b in all_blocks if b.ref_cnt == 0 and b.block_hash is not None)
    
    # Truly Free: No data and no active references
    free = total - active - cached
    
    return {
        "total": total,
        "active": active,
        "cached": cached,
        "free": free
    }
```

---

## 2. Interface Layer: Manager Delegation
**File**: `vllm/v1/core/kv_cache_manager.py`

Expose the `BlockPool` stats through the `KVCacheManager` class.

```python
def get_detailed_stats(self) -> dict:
    return self.block_pool.get_detailed_stats()
```

---

## 3. Trigger & Logging: Scheduler Integration
**File**: `vllm/v1/core/sched/scheduler.py`

### Step 3.1: Imports
Add the necessary imports at the top of the file.
```python
import datetime
```

### Step 3.2: Logging Hook
Modify the `_free_request` method to trigger profiling whenever a request finishes.

```python
def _free_request(self, request: Request, delay_free_blocks: bool = False):
    if not delay_free_blocks:
        self._free_blocks(request)
    
    # Trigger memory profiling log
    self._log_mem_profile(f"Request {request.request_id} Finished")
```

### Step 3.3: Profile Logger Method
Add the `_log_mem_profile` method to the `Scheduler` class. This logic handles the conversion from block counts to GB based on actual allocated tensor sizes.

```python
def _log_mem_profile(self, reason: str):
    try:
        stats = self.kv_cache_manager.get_detailed_stats()
        total_blocks = stats['total']
        if total_blocks <= 0: return

        # Calculate bytes per block from actual allocated GPU tensors
        total_cache_bytes = sum(t.size for t in self.kv_cache_config.kv_cache_tensors)
        bytes_per_block = total_cache_bytes / self.kv_cache_config.num_blocks
        gb_factor = 1024 ** 3

        # Convert to GB
        active_gb = (stats['active'] * bytes_per_block) / gb_factor
        cached_gb = (stats['cached'] * bytes_per_block) / gb_factor
        free_gb = (stats['free'] * bytes_per_block) / gb_factor
        total_pool_gb = (total_blocks * bytes_per_block) / gb_factor

        # Calculate percentages
        active_ratio = stats['active'] / total_blocks * 100
        cached_ratio = stats['cached'] / total_blocks * 100
        free_ratio = stats['free'] / total_blocks * 100

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = (f"[{now}] {reason}: "
                    f"Active: {active_ratio:.2f}% ({active_gb:.2f} GB), "
                    f"Prefix-Cached: {cached_ratio:.2f}% ({cached_gb:.2f} GB), "
                    f"Free: {free_ratio:.2f}% ({free_gb:.2f} GB), "
                    f"Total Pool: {total_pool_gb:.2f} GB\n")

        # Write to dedicated log file
        log_path = "/home/gnltnwjstk/joi/vllm_mem_profile.log"
        with open(log_path, "a") as f:
            f.write(log_msg)
            
    except Exception as e:
        logger.warning("Failed to log memory profile: %s", e)
```

---

## 💡 Implementation Notes

> [!IMPORTANT]
> **Why use `kv_cache_tensors` for GB calculation?**  
> Summing up the sizes of `kv_cache_tensors` is the most reliable way to determine the total memory allocated for the KV cache on a specific GPU rank, as it accounts for all layers, heads, and data types (FP16/FP8).

> [!TIP]
> **Prefix Caching Visibility**: In vLLM V1, blocks are frequently "free" to the scheduler but "cached" in the block pool for prefix matching. This implementation allows you to monitor exactly how much space is being used to speed up subsequent requests via prefix caching.
