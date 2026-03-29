import pandas as pd
import numpy as np
from tqdm import tqdm
from model import BangladeshModel
import sys

# 5 days * 24 hours * 60 minutes
run_length = 7200

# set up seeds
np.random.seed(42)  # fixed master seed
max_seed = np.iinfo(np.int32).max
seeds = np.random.randint(0, max_seed, size=10)

print("Seeds used for all scenarios:")

print(seeds)

# Run all scenarios
for s_num in range(5):

    print(f"\n=== Running Scenario {s_num} ===")

    replication_results = []
    bridge_delay_accumulator = {}
    routes_results = []
    # tqdm for replications
    for rep_index, seed in enumerate(tqdm(seeds, desc=f"Scenario {s_num} Replications")):

        model = BangladeshModel(scenario_A3=s_num, seed=int(seed))

        # tqdm for simulation steps
        for _, _ in enumerate(tqdm(range(run_length), desc=f"scenario running")):
            model.step()
        # calculate average time
        driving_times = model.get_driving_times()
        avg_time = sum(driving_times) / len(driving_times)
        route_lengths = model.get_route_lengths()
        avg_distance = sum(route_lengths) / len(route_lengths) / 1000
        min_distance = min(route_lengths) / 1000
        max_distance = max(route_lengths) / 1000

        # log results
        replication_results.append({
            "scenario": s_num,
            "replication": rep_index + 1,
            "seed": int(seed),
            "average_driving_time": avg_time,
            "average_distance_km": avg_distance,
            "time_per_km": avg_time / avg_distance if avg_distance > 0 else 0,
            "shortest_route_km": min_distance,
            "longest_route_km": max_distance
        })

        # log routes
        for entry in model.output_data:
            src = model.schedule._agents.get(entry['source_id'])
            snk = model.schedule._agents.get(entry['sink_id'])
            routes_results.append({
                "scenario": s_num,
                "replication": rep_index + 1,
                "route_length_km": entry['route_length'] / 1000,
                "driving_time_min": entry['travel_time'],
                "source_id": entry['source_id'],
                "source_name": src.name if src else '?',
                "sink_id": entry['sink_id'],
                "sink_name": snk.name if snk else '?',
            })

        hotspots = model.get_traffic_hotspots(top_n=200)
        vuln_overall, vuln_by_type = model.get_vulnerability_summary(top_n=200)
        hotspots.to_csv(f"experiment/scenario{s_num}_rep{rep_index + 1}_hotspots.csv", index=False)
        vuln_overall.to_csv(f"experiment/scenario{s_num}_rep{rep_index + 1}_vulnerability.csv", index=False)
        vuln_by_type.to_csv(f"experiment/scenario{s_num}_rep{rep_index + 1}_vulnerability_by_type.csv", index=False)

    bridge_results = []

    df_A3 = pd.DataFrame(replication_results)

    # calculate driving time statistics
    mean = df_A3["average_driving_time"].mean()
    std = df_A3["average_driving_time"].std()
    n = len(df_A3)
    stderr = std / np.sqrt(n)

    # 95% confidence interval
    ci_low = mean - 1.96 * stderr
    ci_high = mean + 1.96 * stderr

    df_A3["scenario_mean"] = mean
    df_A3["scenario_std"] = std
    df_A3["standard_error"] = stderr
    df_A3["ci_95_lower"] = ci_low
    df_A3["ci_95_upper"] = ci_high
    # save experiment results
    df_A3.to_csv(f"experiment/scenario{s_num}_A3.csv", index=False)

    print(f"Scenario {s_num} results saved.")
    print(f"Mean = {mean:.2f} min | 95% CI = [{ci_low:.2f}, {ci_high:.2f}]")

    # crete csv for route length info
    df_routes = pd.DataFrame(routes_results)
    df_routes.to_csv(f"experiment/scenario{s_num}_routes.csv", index=False)