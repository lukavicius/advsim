import pandas as pd
import numpy as np
from tqdm import tqdm
from model import BangladeshModel
import sys

# 5 days * 24 hours * 60 minutes
run_length = 7200

np.random.seed(42)  # fixed master seed
max_seed = np.iinfo(np.int32).max
seeds = np.random.randint(0, max_seed, size=10)

print("Seeds used for all scenarios:")
print(seeds)

for s_num in range(9):

    print(f"\n=== Running Scenario {s_num} ===")

    replication_results = []
    bridge_delay_accumulator = {}
    # tqdm for replications
    for rep_index, seed in enumerate(tqdm(seeds, desc=f"Scenario {s_num} Replications")):

        model = BangladeshModel(scenario=s_num, seed=int(seed))

        # tqdm for simulation steps
        for _ in tqdm(range(run_length),
                      desc=f"Scenario {s_num} - Rep {rep_index+1}",
                      leave=False):
            model.step()

        avg_time = model.get_average_driving_time()

        replication_results.append({
            "scenario": s_num,
            "replication": rep_index + 1,
            "seed": int(seed),
            "average_driving_time": avg_time
        })

        bridge_df = model.get_bridge_delay_summary()

        for _, row in bridge_df.iterrows():

            bid = row["bridge_id"]

            if bid not in bridge_delay_accumulator:
                bridge_delay_accumulator[bid] = []

            bridge_delay_accumulator[bid].append(row["total_delay"])

    bridge_results = []

    for bid, delays in bridge_delay_accumulator.items():
        mean = np.mean(delays)
        std = np.std(delays)
        ci95 = 1.96 * std / np.sqrt(len(delays))

        bridge_results.append({
            "bridge_id": bid,
            "mean_total_delay": mean,
            "std": std,
            "ci95": ci95
        })

    bridge_df = pd.DataFrame(bridge_results)
    bridge_df = bridge_df.sort_values("mean_total_delay", ascending=False)

    top10 = bridge_df.head(10)
    top10.to_csv(f"experiment/top10_bridges_scenario{s_num}.csv", index=False)


    df = pd.DataFrame(replication_results)

    mean = df["average_driving_time"].mean()
    std = df["average_driving_time"].std()
    n = len(df)
    stderr = std / np.sqrt(n)

    # 95% confidence interval
    ci_low = mean - 1.96 * stderr
    ci_high = mean + 1.96 * stderr

    df["scenario_mean"] = mean
    df["scenario_std"] = std
    df["standard_error"] = stderr
    df["ci_95_lower"] = ci_low
    df["ci_95_upper"] = ci_high

    df.to_csv(f"experiment/scenario{s_num}.csv", index=False)

    print(f"Scenario {s_num} results saved.")
    print(f"Mean = {mean:.2f} min | 95% CI = [{ci_low:.2f}, {ci_high:.2f}]")