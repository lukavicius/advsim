 # from model import BangladeshModel
#
# """
#     Run simulation
#     Print output at terminal
# """
#
# # ---------------------------------------------------------------
#
# # run time 5 x 24 hours; 1 tick 1 minute
# run_length = 5 * 24 * 60
#
# # run time 1000 ticks
# # run_length = 1000
#
# seed = 1234567
#
# sim_model = BangladeshModel(seed=seed)
#
# # Check if the seed is set
# print("SEED " + str(sim_model._seed))
#
# # One run with given steps
# for i in range(run_length):
#     sim_model.step()

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
        for _ in tqdm(range(run_length),
                      desc=f"Scenario {s_num} - Rep {rep_index+1}",
                      leave=False):
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
        for rl, dt in zip(route_lengths, driving_times):
            routes_results.append({
                "scenario": s_num,
                "replication": rep_index + 1,
                "route_length_km": rl / 1000,  # convert meters to km
                "driving_time_min": dt
            })

        # log bridge delays
        bridge_df = model.get_bridge_delay_summary()

        for _, row in bridge_df.iterrows():

            bid = row["bridge_id"]

            if bid not in bridge_delay_accumulator:
                bridge_delay_accumulator[bid] = []

            bridge_delay_accumulator[bid].append(row["total_delay"])

    bridge_results = []

    # Calculate bridge delay statistics
    # for bid, delays in bridge_delay_accumulator.items():
    #     mean = np.mean(delays)
    #     std = np.std(delays)
    #     ci95 = 1.96 * std / np.sqrt(len(delays))
    #
    #     bridge_results.append({
    #         "bridge_id": bid,
    #         "mean_total_delay": mean,
    #         "std": std,
    #         "ci95": ci95
    #     })
    #
    # # save bridge delay results
    # bridge_df = pd.DataFrame(bridge_results)
    # bridge_df = bridge_df.sort_values("mean_total_delay", ascending=False)

    # top10 = bridge_df.head(10)
    # top10.to_csv(f"experiment/top10_bridges_scenario{s_num}.csv", index=False)


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