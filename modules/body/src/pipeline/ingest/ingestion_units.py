"""
Purpose: Unit canonicalization mm/cm/m -> m. Contract: UNIT_STANDARD.
Inputs: values, source_unit, warnings list
Outputs: values in meters (array or scalar)
Status: active
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal, Union
import numpy as np


def canonicalize_units_to_m(
    values: Union[float, np.ndarray, list],
    source_unit: Literal["mm", "cm", "m"],
    warnings: list,
) -> Union[float, np.ndarray]:
    """Convert values to meters (m) with 0.001m quantization. NaN+warnings policy."""
    is_scalar = isinstance(values, (float, int))
    if isinstance(values, (list, tuple)):
        values_arr = np.array(values, dtype=np.float64)
    elif isinstance(values, np.ndarray):
        values_arr = values.astype(np.float64)
    else:
        values_arr = np.array([values], dtype=np.float64)

    if source_unit not in ["mm", "cm", "m"]:
        warnings.append(f"UNIT_FAIL: Invalid source_unit '{source_unit}'")
        return (np.nan if is_scalar else np.full_like(values_arr, np.nan))

    invalid_mask = ~np.isfinite(values_arr)
    if np.any(invalid_mask):
        warnings.append(f"UNIT_FAIL: {np.sum(invalid_mask)} invalid value(s)")

    if source_unit == "mm":
        values_m = values_arr / 1000.0
    elif source_unit == "cm":
        values_m = values_arr / 100.0
    else:
        values_m = values_arr.copy()

    quantized = np.array([
        float(Decimal(float(v)).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP))
        if np.isfinite(v) else np.nan
        for v in values_m
    ])
    quantized[invalid_mask] = np.nan
    return float(quantized[0]) if is_scalar else quantized
