from simulator.runner import benchmark_runner


def test_reproducible_benchmark_simulation():
    # Run simulation with seed 42
    results = benchmark_runner.run_benchmark(num_customers=500, num_events=2000)

    assert results["dataset_meta"]["seed"] == 42
    assert results["revive"]["recovery_rate_pct"] > results["baseline"]["recovery_rate_pct"]
    assert results["revive"]["policy_violations_count"] == 0
    assert results["revive"]["duplicate_actions_count"] == 0
    assert results["revive"]["unnecessary_nudges_count"] == 0
    assert results["comparison"]["net_incremental_recovered_rupees"] > 0
