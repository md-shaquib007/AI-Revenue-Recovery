from fastapi import APIRouter, Depends, Query

from apps.api.auth import OperatorContext, require_chaos
from simulator.runner import benchmark_runner

router = APIRouter(prefix="/benchmark", tags=["Benchmark Evaluation"])


@router.get("/run")
async def run_comparative_benchmark(
    seed: int = Query(42, description="Random seed for reproducible dataset"),
    customers: int = Query(1000, ge=100, le=5000),
    events: int = Query(5000, ge=500, le=10000),
    _: OperatorContext = Depends(require_chaos),
):
    benchmark_runner.generator.seed = seed
    results = benchmark_runner.run_benchmark(num_customers=customers, num_events=events)
    return results
