from mesa import Model
from mesa.time import BaseScheduler
from mesa.space import ContinuousSpace
from components import Source, Sink, SourceSink, Bridge, Link, Intersection
import pandas as pd
from collections import defaultdict
import networkx as nx
import math
# ---------------------------------------------------------------
def set_lat_lon_bound(lat_min, lat_max, lon_min, lon_max, edge_ratio=0.02):
    """
    Set the HTML continuous space canvas bounding box (for visualization)
    give the min and max latitudes and Longitudes in Decimal Degrees (DD)

    Add white borders at edges (default 2%) of the bounding box
    """

    lat_edge = (lat_max - lat_min) * edge_ratio
    lon_edge = (lon_max - lon_min) * edge_ratio

    x_max = lon_max + lon_edge
    y_max = lat_min - lat_edge
    x_min = lon_min - lon_edge
    y_min = lat_max + lat_edge
    return y_min, y_max, x_min, x_max
#-------------------------------------------------------------------------
# Scenario set up
SCENARIOS = {
    0: {"A": 0, "B": 0, "C": 0, "D": 0},
    1: {"A": 0, "B": 0, "C": 0, "D": 5},
    2: {"A": 0, "B": 0, "C": 5, "D": 10},
    3: {"A": 0, "B": 5, "C": 10, "D": 20},
    4: {"A": 5, "B": 10, "C": 20, "D": 40},
}

# ---------------------------------------------------------------
class BangladeshModel(Model):
    """
    The main (top-level) simulation model

    One tick represents one minute; this can be changed
    but the distance calculation need to be adapted accordingly

    Class Attributes:
    -----------------
    step_time: int
        step_time = 1 # 1 step is 1 min

    path_ids_dict: defaultdict
        Key: (origin, destination)
        Value: the shortest path (Infra component IDs) from an origin to a destination

        Only straight paths in the Demo are added into the dict;
        when there is a more complex network layout, the paths need to be managed differently

    sources: list
        all sources in the network

    sinks: list
        all sinks in the network

    """

    step_time = 1

    file_name = '../data/preprocessing/processed_data.csv'

    def __init__(self, seed=None, x_max=500, y_max=500, x_min=0, y_min=0, scenario_A3 = 0, run_number=0):

        super().__init__(seed=seed)
        self.scenario_A3= scenario_A3
        self.run_number = run_number
        self.output_data = []
        self.schedule = BaseScheduler(self)
        self.running = True
        self.path_ids_dict = defaultdict(lambda: pd.Series())
        self.space = None
        self.sources = []
        self.sinks = []

        self.graph = nx.Graph() # network: creates graph
        self.active_scenario = SCENARIOS.get(scenario_A3,SCENARIOS[0])
        self.generate_model()

    def get_driving_times(self):
        """Calculates the mean travel time for all trucks that reached the sink."""
        if not self.output_data:
            # If no trucks reached the sink yet, return 0 to avoid errors
            return 0

        # Pull all travel times from the list we collected
        times = [d['travel_time'] for d in self.output_data]
        return times

    def get_route_lengths(self):
        if not self.output_data:
            return 0

        lengths = [d['route_length'] for d in self.output_data if d['route_length'] is not None]
        return lengths

    def save_scenario_results(self, replication_results):
        """
        Saves the 10 replications into a single CSV for this scenario.
        Called from the run script, not from inside the model.
        """
        df = pd.DataFrame(replication_results)
        filename = f"scenario{self.scenario_A3}.csv"
        df.to_csv(filename, index=False)
        print(f" Saved results to {filename}")


    def generate_model(self):
        """
        generate the simulation model according to the csv file component information

        Warning: the labels are the same as the csv column labels
        """

        df = pd.read_csv(self.file_name)

        # a list of names of roads to be generated
        # TODO You can also read in the road column to generate this list automatically
        roads = df['road'].unique().tolist()

        df_objects_all = []
        for road in roads:
            # Select all the objects on a particular road in the original order as in the cvs
            df_objects_on_road = df[df['road'] == road]

            if not df_objects_on_road.empty:
                df_objects_all.append(df_objects_on_road)

                """
                Set the path 
                1. get the serie of object IDs on a given road in the cvs in the original order
                2. add the (straight) path to the path_ids_dict
                3. put the path in reversed order and reindex
                4. add the path to the path_ids_dict so that the vehicles can drive backwards too
                """
                path_ids = df_objects_on_road['id']
                path_ids.reset_index(inplace=True, drop=True)
                self.path_ids_dict[path_ids[0], path_ids.iloc[-1]] = path_ids
                self.path_ids_dict[path_ids[0], None] = path_ids
                path_ids = path_ids[::-1]
                path_ids.reset_index(inplace=True, drop=True)
                self.path_ids_dict[path_ids[0], path_ids.iloc[-1]] = path_ids
                self.path_ids_dict[path_ids[0], None] = path_ids

                # network: adds edges
                path_ids_list = df_objects_on_road['id'].tolist()
                for i in range(len(path_ids_list) - 1):
                    node1 = path_ids_list[i]
                    node2 = path_ids_list[i + 1]

                    pos1 = df_objects_on_road.iloc[i]
                    pos2 = df_objects_on_road.iloc[i + 1]

                    #distance = ((pos1['lat'] - pos2['lat']) ** 2 + (pos1['lon'] - pos2['lon']) ** 2) ** 0.5

                    distance = self.get_harvesian_distance(pos1['lat'], pos2['lat'], pos1['lon'], pos2['lon'])

                    self.graph.add_edge(node1, node2, weight=distance)

        # put back to df with selected roads so that min and max and be easily calculated
        df = pd.concat(df_objects_all)
        y_min, y_max, x_min, x_max = set_lat_lon_bound(
            df['lat'].min(),
            df['lat'].max(),
            df['lon'].min(),
            df['lon'].max(),
            0.05
        )
# viola and finn
        df_full = pd.concat(df_objects_all)
        for _, row in df_full[df_full['model_type'] == 'intersection'].iterrows():
            int_id = row['id']
            others = df_full[df_full['model_type'] != 'intersection']
            #dists = ((others['lat'] - row['lat']) ** 2 + (others['lon'] - row['lon']) ** 2) ** 0.5
            dists = []
            for idx, other_row in others.iterrows():
                distance = self.get_harvesian_distance(row['lat'], other_row['lat'], row['lon'], other_row['lon'])
                dists.append((idx, distance))

            #for idx in dists.nsmallest(2).index:
            #  neighbor_id = df_full.loc[idx, 'id']
            #   self.graph.add_edge(int_id, neighbor_id, weight=dists[idx])

            dists.sort(key=lambda x: x[1])
            for idx, distance in dists[:2]:
                neighbor_id = df_full.loc[idx, 'id']
                self.graph.add_edge(int_id, neighbor_id, weight=distance)

        # ContinuousSpace from the Mesa package;
        # not to be confused with the SimpleContinuousModule visualization
        self.space = ContinuousSpace(x_max, y_max, True, x_min, y_min)

        for df in df_objects_all:
            for _, row in df.iterrows():  # index, row in ...

                # create agents according to model_type
                model_type = row['model_type'].strip()
                agent = None

                name = row['name']
                if pd.isna(name):
                    name = ""
                else:
                    name = name.strip()

                # I think we can get rid of this since we only have soucesink

                # if model_type == 'source':
                #     agent = Source(row['id'], self, row['length'], name, row['road'])
                #     self.sources.append(agent.unique_id)
                # elif model_type == 'sink':
                #     agent = Sink(row['id'], self, row['length'], name, row['road'])
                #     self.sinks.append(agent.unique_id)


                if model_type == 'sourcesink':
                    agent = SourceSink(row['id'], self, row['length'], name, row['road'])
                    self.sources.append(agent.unique_id)
                    self.sinks.append(agent.unique_id)
                elif model_type == 'bridge':
                    agent = Bridge(row['id'], self, row['length'], name, row['road'], row['condition'])
                elif model_type == 'link':
                    agent = Link(row['id'], self, row['length'], name, row['road'])
                elif model_type == 'intersection':
                    if not row['id'] in self.schedule._agents:
                        agent = Intersection(row['id'], self, row['length'], name, row['road'])

                if agent:
                    self.schedule.add(agent)
                    y = row['lat']
                    x = row['lon']
                    self.space.place_agent(agent, (x, y))
                    agent.pos = (x, y)

                    self.graph.add_node(agent.unique_id) # network: adds nodes to graph

    def get_harvesian_distance(self, lat1, lat2, lon1, lon2):
        R = 6371000  # Earth radius in meters

        lat1 = math.radians(lat1)
        lon1 = math.radians(lon1)
        lat2 = math.radians(lat2)
        lon2 = math.radians(lon2)

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        distance = 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return distance


    def get_random_route(self, source):
        """
        pick up a random route given an origin
        """

        while True:
            # different source and sink
            sink = self.random.choice(self.sinks)
            if sink is not source:
                break

        # network
        # check if route already cached
        if (source, sink) in self.path_ids_dict:
            return self.path_ids_dict[source, sink]

        # if not compute shortest path
        route = nx.shortest_path(
            self.graph,
            source=source,
            target=sink,
            weight='weight'
        )
        #print(len(route))

        route_series = pd.Series(route)

        # cache the route
        self.path_ids_dict[source, sink] = route_series

        return route_series

    # TODO
    def get_route(self, source):
        return self.get_random_route(source)

    def get_straight_route(self, source):
        """
        pick up a straight route given an origin
        """
        return self.path_ids_dict[source, None]

    def step(self):
        """
        Advance the simulation by one step.
        """
        self.schedule.step()

    def get_bridge_delay_summary(self):
        results = []
        for agent in self.schedule.agents:  # <-- use scheduler's public agents list
            if isinstance(agent, Bridge):
                results.append({
                    "bridge_id": agent.unique_id,
                    "name": agent.name,
                    "condition": agent.condition,
                    "length": agent.length,
                    "total_delay": agent.total_delay,
                    "truck_count": agent.truck_count,
                    "avg_delay_per_truck":
                        agent.total_delay / agent.truck_count
                        if agent.truck_count > 0 else 0
                })

        df = pd.DataFrame(results)
        return df.sort_values("total_delay", ascending=False)

# EOF -----------------------------------------------------------