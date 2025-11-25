"""
SmartEstimates Package
======================

Production-grade implementation of Refinitiv's SmartEstimates methodology
with decomposed weighting (industry vs company-specific components).

Author: Quantitative Research
Date: 2025-11-25
"""

from .core import (
    SmartEstimateConfig,
    SmartEstimateBuilder
)

from .simulation import (
    SimulationConfig,
    DataSimulator,
    run_simulation
)

from .evaluation import (
    PerformanceEvaluator
)

from .data_loader import (
    IBESDataLoader,
    RealDataSmartEstimateEngine
)

__version__ = "1.0.0"

__all__ = [
    # Core
    'SmartEstimateConfig',
    'SmartEstimateBuilder',
    # Simulation
    'SimulationConfig',
    'DataSimulator',
    'run_simulation',
    # Evaluation
    'PerformanceEvaluator',
    # Data Loading
    'IBESDataLoader',
    'RealDataSmartEstimateEngine',
]
