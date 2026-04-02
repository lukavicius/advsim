from mesa import Model
from mesa.time import BaseScheduler
from mesa.space import ContinuousSpace
from components import Source, Sink, SourceSink, Bridge, Link, Intersection
import pandas as pd
from collections import defaultdict
import networkx as nx

#calculating the bounds of the model with the small buffer
def set_lat_lon_bound(lat_min, lat_max, lon_min, lon_max, edge_ratio=0.02):
    lat_edge = (lat_max - lat_min) * edge_ratio
    lon_edge = (lon_max - lon_min) * edge_ratio
    x_max = lon_max + lon_edge
    y_max = lat_min - lat_edge
    x_min = lon_min - lon_edge
    y_min = lat_max + lat_edge
    return y_min, y_max, x_min, x_max

# ---------------------------------------------------------------
#defining probabilities of bridge failure
SCENARIOS = {
    0: {"A": 0,  "B": 0,  "C": 0,  "D": 0},
    1: {"A": 0,  "B": 0,  "C": 0,  "D": 5},
    2: {"A": 0,  "B": 0,  "C": 5,  "D": 10},
    3: {"A": 0,  "B": 5,  "C": 10, "D": 20},
    4: {"A": 5,  "B": 10, "C": 20, "D": 40},
}

# ---------------------------------------------------------------
class BangladeshModel(Model):

    step_time = 1
    file_name = '../data/preprocessing/processed_data.csv'

    def __init__(self, seed=None, x_max=500, y_max=500, x_min=0, y_min=0,
                 scenario_A3=0, run_number=0):

        #initialising mesa model and creating tracking dictionarties and schedulers
        super().__init__(seed=seed)
        self.scenario_A3  = scenario_A3
        self.run_number   = run_number
        self.output_data  = []

        self.schedule      = BaseScheduler(self)
        self.running       = True
        #for efficiency, store pre-calculated paths
        self.path_ids_dict = defaultdict(lambda: pd.Series(dtype=int))
        self.space         = None
        self.sources       = []
        self.sinks         = []

        #initialise the map to represent the road topology
        self.graph         = nx.Graph()

        self.active_scenario = SCENARIOS.get(scenario_A3, SCENARIOS[0])

        self.traffic_data = pd.read_csv("../data/traffic/traffic_metrics_per_timestep.csv")
        self.traffic_dict = self.traffic_data.set_index("Road").to_dict("index")

        self.generate_model()

    #build the simulation environment, so create the agents, space and graph
    def generate_model(self):

        df = pd.read_csv(self.file_name)

        roads = df['road'].unique().tolist()
        df_objects_all = []

        for road in roads:
            #process every road section to find path IDS of both ways
            df_objects_on_road = df[df['road'] == road]
            if df_objects_on_road.empty:
                continue

            df_objects_all.append(df_objects_on_road)

            # Get the sequence of IDs as they appear in the CSV (the canonical path)
            #map both the start and end
            path_ids = df_objects_on_road['id'].reset_index(drop=True)
            path_ids_rev = path_ids[::-1].reset_index(drop=True)

            # Straight-path fallback (source -> None)
            self.path_ids_dict[path_ids.iloc[0], None] = path_ids
            self.path_ids_dict[path_ids_rev.iloc[0], None] = path_ids_rev

            # Pre-load forward and reverse endpoint pairs from CSV order,
            # as described in the assignment: path_ids_dict[(start, end)] = path
            self.path_ids_dict[path_ids.iloc[0], path_ids.iloc[-1]] = path_ids
            self.path_ids_dict[path_ids.iloc[-1], path_ids.iloc[0]] = path_ids_rev

        # create space bounds using the extremes
        df_all = pd.concat(df_objects_all)
        y_min, y_max, x_min, x_max = set_lat_lon_bound(
            df_all['lat'].min(), df_all['lat'].max(),
            df_all['lon'].min(), df_all['lon'].max(),
            0.05
        )
        self.space = ContinuousSpace(x_max, y_max, True, x_min, y_min)

        # Create agents and build graph
        created_ids = set()

        for df_road in df_objects_all:
            prev_id = None
            prev_length = 0.0  # track source node length for correct edge weights

            for _, row in df_road.iterrows():

                model_type = row['model_type'].strip()
                agent_id   = int(row['id'])
                name       = "" if pd.isna(row['name']) else str(row['name']).strip()
                length     = float(row['length']) if not pd.isna(row['length']) else 0.0
                agent      = None

                # Create the Mesa agent only once per ID and add to the scheduler
                if agent_id not in created_ids:
                    if model_type == 'sourcesink':
                        agent = SourceSink(agent_id, self, length, name, row['road'])
                        self.sources.append(agent_id)
                        self.sinks.append(agent_id)
                    elif model_type == 'bridge':
                        agent = Bridge(agent_id, self, length, name, row['road'],
                                       row['condition'])
                    elif model_type == 'link':
                        agent = Link(agent_id, self, length, name, row['road'])
                    elif model_type == 'intersection':
                        agent = Intersection(agent_id, self, length, name, row['road'])

                    if agent:
                        self.schedule.add(agent)
                        self.space.place_agent(agent, (row['lon'], row['lat']))
                        agent.pos = (row['lon'], row['lat'])
                        created_ids.add(agent_id)

                # Always add graph node + edge — even for already-created intersections.
                # This is what stitches the two roads together through the shared node.
                if agent_id not in self.graph.nodes:
                    self.graph.add_node(agent_id)

                if prev_id is not None and not self.graph.has_edge(prev_id, agent_id):
                    # Use prev_length (the source node's length) as the edge weight,
                    # since a truck spends time traversing the component it is leaving.
                    self.graph.add_edge(prev_id, agent_id, weight=prev_length)

                prev_id = agent_id
                prev_length = length  # carry forward for the next edge

        zero_edges = [(u, v) for u, v, d in self.graph.edges(data=True) if d['weight'] == 0]
        print(f"[GRAPH] {len(zero_edges)} zero-weight edges: {zero_edges[:20]}")

        n_comp = nx.number_connected_components(self.graph)
        print(f"[GRAPH] {self.graph.number_of_nodes()} nodes, "
              f"{self.graph.number_of_edges()} edges, "
              f"{n_comp} connected component(s)")
        if n_comp > 1:
            print(f"[GRAPH] WARNING: {n_comp} disconnected components — "
                  f"check intersection IDs in processed_data.csv")
        self.infra_dict = {a.unique_id: a for a in self.schedule.agents}

    #starting point for agents to ask for a destination and route
    def get_route(self, source_id):
        return self.get_random_route(source_id)

    #selecting a random end point and using nx shorthest path to find the way
    def get_random_route(self, source_id):
        attempts = 0
        while True:
            sink_id = self.random.choice(self.sinks)
            if sink_id == source_id:
                continue

            # Check if route was already calculated and cached
            cached = self.path_ids_dict[source_id, sink_id]
            if not cached.empty:
                return cached

            # Try NetworkX shortest path
            try:
                node_path = nx.shortest_path(self.graph, source=source_id,
                                             target=sink_id, weight='weight')
                path_series = pd.Series(node_path, dtype=int)
                self.path_ids_dict[source_id, sink_id] = path_series
                self.path_ids_dict[sink_id, source_id] = path_series[::-1].reset_index(drop=True)
                return path_series
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                attempts += 1
                if attempts > 50:
                    return self.get_straight_route(source_id)

    def get_straight_route(self, source_id):
        return self.path_ids_dict[source_id, None]

    #advance the simulation one tick
    def step(self):
        self.schedule.step()

    #retrieving driving time
    def get_driving_times(self):
        if not self.output_data:
            return [0]
        return [d['travel_time'] for d in self.output_data]

    #retrieving route length
    def get_route_lengths(self):
        if not self.output_data:
            return [0]
        return [d['route_length'] for d in self.output_data if d['route_length'] is not None]

    #retrieve bridge delay summary in records
    def get_bridge_delay_summary(self):
        records = []
        for agent in self.schedule.agents:
            if isinstance(agent, Bridge):
                records.append({
                    'bridge_id':   agent.unique_id,
                    'bridge_name': agent.name,
                    'total_delay': agent.total_delay,
                    'truck_count': agent.truck_count,
                })
        return pd.DataFrame(records)

    #save the scenario results to a csv
    def save_scenario_results(self, replication_results):
        df = pd.DataFrame(replication_results)
        df.to_csv(f"scenario{self.scenario_A3}.csv", index=False)
        print(f"Saved results to scenario{self.scenario_A3}.csv")

    #important part of this specific assignment 4;
    #this function analyses total delay time across all infrastructure to find high impact failure points
    def get_vulnerability_summary(self, top_n=10):
        records = []
        for agent in self.schedule.agents:
            if isinstance(agent, (Bridge, Link, Intersection)):
                if agent.truck_count > 0:
                    records.append({
                        'id': agent.unique_id,
                        'name': agent.name,
                        'road': agent.road_name,
                        'type': type(agent).__name__,
                        'condition': getattr(agent, 'condition', '-'),
                        'length_m': agent.length,
                        'throughput': agent.throughput,
                        'truck_count': agent.truck_count,
                        'total_delay_min': agent.total_delay,
                        'avg_delay_per_truck': agent.total_delay / agent.truck_count,
                        'current_vehicles': agent.vehicle_count,
                    })
        df = pd.DataFrame(records)
        if df.empty:
            return df

        # Top overall
        #use .sort_values() method to sort infrastructure by the total accummulated delay
        # top down with highest delay as first values (because ascending=false)
        top_overall = df.sort_values('total_delay_min', ascending=False).head(top_n)

        # Top per type so bridges don't bury links/intersections
        top_per_type = (
            df.sort_values('total_delay_min', ascending=False)
            .groupby('type')
            .head(top_n)
            .sort_values(['type', 'total_delay_min'], ascending=[True, False])
        )

        return top_overall.reset_index(drop=True), top_per_type.reset_index(drop=True)

    #important part of this specific assignment 4 part 2:
    #this function identifies the locations with the highest throughput == most vehicles passed
    def get_traffic_hotspots(self, top_n=10):
        records = []
        for agent in self.schedule.agents:
            if isinstance(agent, (Bridge, Link, Intersection)):
                records.append({
                    'id': agent.unique_id,
                    'name': agent.name,
                    'road': agent.road_name,
                    'type': type(agent).__name__,
                    'condition': getattr(agent, 'condition', '-'),
                    'length_m': agent.length,
                    'throughput': agent.throughput,
                    'current_vehicles': agent.vehicle_count,
                })
        df = pd.DataFrame(records)
        if df.empty:
            return df
        return df.sort_values('throughput', ascending=False).head(top_n).reset_index(drop=True)
# EOF -----------------------------------------------------------