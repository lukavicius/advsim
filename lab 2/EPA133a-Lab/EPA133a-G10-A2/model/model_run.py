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
# # run_length = 5 * 24 * 60
#
# # run time 1000 ticks
# run_length = 1000
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
from model import BangladeshModel

# 5 days * 24 hours * 60 minutes
run_length = 7200

# Scenarios 0 through 8
for s_num in range(9):
    replication_averages = []

    for r_num in range(1, 11):
        print(f"Running Scenario {s_num}, Replication {r_num}...")

        # Initialize model with the scenario index and the replication as seed
        model = BangladeshModel(scenario=s_num, seed=r_num)

        # Run the simulation
        for i in range(run_length):
            model.step()

        # Calculate the average for this specific 5-day run
        avg_time = model.get_average_driving_time()

        # Store it
        replication_averages.append({
            "replication": r_num,
            "average_driving_time": avg_time
        })

    # After 10 runs, save the summary to scenarioX.csv
    summary_df = pd.DataFrame(replication_averages)
    summary_df.to_csv(f"scenario{s_num}.csv", index=False)
    print(f"--- Finished Scenario {s_num} ---")
