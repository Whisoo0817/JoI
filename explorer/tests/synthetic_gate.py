"""Historical language/search fixtures intentionally use invented services.

Keep their original model explicit. Actual catalog conformance is exercised
separately in test_service_model; production gate defaults to catalog checks.
"""
from functools import partial
from explorer.verification.gate import gate_pair as _gate_pair, prepare_pair as _prepare_pair

gate_pair = partial(_gate_pair, service_catalog=False)
prepare_pair = partial(_prepare_pair, service_catalog=False)
