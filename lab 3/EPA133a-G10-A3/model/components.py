from mesa import Agent
from enum import Enum

from networkx import volume


# ---------------------------------------------------------------
class Infra(Agent):
    """
    Base class for all infrastructure components

    Attributes
    __________
    vehicle_count : int
        the number of vehicles that are currently in/on (or totally generated/removed by)
        this infrastructure component

    length : float
        the length in meters
    """

    def __init__(self, unique_id, model, length=0,
                 name='Unknown', road_name='Unknown'):
        super().__init__(unique_id, model)
        self.length = length
        self.name = name
        self.road_name = road_name
        self.vehicle_count = 0
        self.total_delay = 0
        self.truck_count = 0
        self.throughput = 0

    def step(self):
        def step(self):
            if self.state == Vehicle.State.WAIT:
                self.waiting_time = max(self.waiting_time - 1, 0)
                if self.waiting_time == 0:
                    self.waited_at = self.location
                    self.state = Vehicle.State.DRIVE
                    self.drive_to_next(Vehicle.speed * Vehicle.step_time)
                    return

            if self.state == Vehicle.State.DRIVE:
                self.drive()

    def get_congestion_delay(self):
        n = self.vehicle_count
        if n < 8:
            delay = 0
        elif n < 16:
            delay = 5
        elif n < 25:
            delay = 8
        elif n < 40:
            delay = 10.5
        else:
            delay = 14

        self.total_delay += delay
        self.truck_count += 1
        return delay

    def __str__(self):
        return type(self).__name__ + str(self.unique_id)


# ---------------------------------------------------------------
class Bridge(Infra):
    """
    Creates delay time based on bridge condition and scenario breakdown probabilities.

    Attributes
    __________
    condition : str
        condition category of the bridge (A, B, C, or D)

    breakdown_prob : float
        probability of breakdown per crossing, set from scenario

    is_broken : bool
        current breakdown state

    total_delay : float
        accumulated breakdown delay across all trucks

    truck_count : int
        number of trucks that have crossed this bridge
    """

    def __init__(self, unique_id, model, length=0,
                 name='Unknown', road_name='Unknown', condition='Unknown'):
        super().__init__(unique_id, model, length, name, road_name)

        self.condition = condition
        self.is_broken = False
        self.total_delay = 0
        self.truck_count = 0

        scenario_probs = self.model.active_scenario
        self.breakdown_prob = scenario_probs.get(str(condition).strip(), 0) / 100

    def get_delay_time(self):
        """
        Calculate delay time for a truck crossing this bridge.
        Includes base driving delay plus stochastic breakdown and congestion delays.
        """
        # Base driving time at truck speed (48 km/h)
        self.broken = self.model.random.random() < self.breakdown_prob

        if self.broken:
            if self.length > 200:
                breakdown_delay = self.model.random.triangular(60, 240, 120)
            elif 50 <= self.length <= 200:
                breakdown_delay = self.model.random.uniform(45, 90)
            elif 10 <= self.length < 50:
                breakdown_delay = self.model.random.uniform(15, 60)
            else:
                breakdown_delay = self.model.random.uniform(10, 20)
        else:
            breakdown_delay = 0

        congestion_delay = self.get_congestion_delay()
        crossing_delay = breakdown_delay + congestion_delay
        self.total_delay += breakdown_delay

        return crossing_delay

# ---------------------------------------------------------------
class Link(Infra):
    pass


# ---------------------------------------------------------------
class Intersection(Infra):
    pass


# ---------------------------------------------------------------
class Sink(Infra):
    """
    Sink removes vehicles when they reach their destination.

    Attributes
    __________
    vehicle_removed_toggle : bool
        toggles each time a vehicle is removed (used for visualization)
    """
    vehicle_removed_toggle = False

    def remove(self, vehicle):
        self.model.schedule.remove(vehicle)
        self.vehicle_removed_toggle = not self.vehicle_removed_toggle


# ---------------------------------------------------------------
class Source(Infra):
    """
    Source generates vehicles at a fixed frequency.

    Class Attributes
    ----------------
    truck_counter : int
        global counter used as Truck ID across all sources

    Attributes
    __________
    generation_frequency : int
        number of ticks between truck generations (default: 5 minutes)

    vehicle_generated_flag : bool
        True when a truck is generated in this tick
    """

    truck_counter = 0

    def __init__(self, unique_id, model, length=0,
                 name='Unknown', road_name='Unknown'):
        super().__init__(unique_id, model, length, name, road_name)

        self.vehicle_generated_flag = False

        # Get traffic rate from model (per timestep, already split per end)
        if road_name in self.model.traffic_dict:
            # Sum only truck types (you can adjust this!)
            data = self.model.traffic_dict[road_name]

            self.lambda_rate = (
                    data.get('Heavy Truck per timestep (each end)', 0) +
                    data.get('Medium Truck per timestep (each end)', 0) +
                    data.get('Small Truck per timestep (each end)', 0)
            )
        else:
            self.lambda_rate = 0

    def step(self):
        self.vehicle_generated_flag = False

        lam = self.lambda_rate

        if lam <= 0:
            return

        # Normal approximation
        std = lam ** 0.5
        num_trucks = int(round(self.model.random.gauss(lam, std)))

        # Avoid negative trucks
        num_trucks = max(0, num_trucks)

        for _ in range(num_trucks):
            self.generate_truck()

    def generate_truck(self):
        try:
            agent = Vehicle('Truck' + str(Source.truck_counter), self.model, self)
            if agent:
                self.model.schedule.add(agent)
                agent.set_path()
                Source.truck_counter += 1
                self.vehicle_count += 1
                self.vehicle_generated_flag = True

        except Exception as e:
            print("Oops!", e.__class__, "occurred.")


# ---------------------------------------------------------------
class SourceSink(Source, Sink):
    """
    Combines Source and Sink functionality.
    Generates vehicles heading to random destinations,
    and removes vehicles that arrive here as their destination.
    """
    pass


# ---------------------------------------------------------------
class Vehicle(Agent):
    """
    A truck agent that drives along a path through the road network.
    """

    # 48 km/h in meters per minute
    speed = 48 * 1000 / 60
    step_time = 1

    class State(Enum):
        DRIVE = 1
        WAIT = 2

    def __init__(self, unique_id, model, generated_by,
                 location_offset=0, path_ids=None):
        super().__init__(unique_id, model)
        self.generated_by = generated_by
        self.generated_at_step = model.schedule.steps
        self.location = generated_by
        self.location_offset = location_offset
        self.pos = generated_by.pos
        self.path_ids = path_ids
        self.state = Vehicle.State.DRIVE
        self.location_index = 0
        self.waiting_time = 0
        self.waited_at = None
        self.removed_at_step = None
        self.route_length = 0
        self.sink_id = None

    def __str__(self):
        return (
            "Vehicle" + str(self.unique_id) +
            " +" + str(self.generated_at_step) +
            " -" + str(self.removed_at_step) +
            " " + str(self.state) +
            '(' + str(self.waiting_time) + ') ' +
            str(self.location) +
            '(' + str(self.location.vehicle_count) + ') ' +
            str(self.location_offset)
        )

    def set_path(self):
        """
        Assign a route to this vehicle by calling the model's routing logic.
        Uses the ID of the SourceSink where this vehicle was generated.
        The last node in the path is stored as sink_id to ensure the truck
        is only removed at its intended destination.
        """
        self.path_ids = self.model.get_route(self.generated_by.unique_id)
        self.sink_id = self.path_ids.iloc[-1]

    def step(self):
        """
        Vehicle either waits (bridge delay) or drives each tick.
        """
        if self.state == Vehicle.State.WAIT:
            self.waiting_time = max(self.waiting_time - 1, 0)
            if self.waiting_time == 0:
                self.waited_at = self.location
                self.state = Vehicle.State.DRIVE

        if self.state == Vehicle.State.DRIVE:
            self.drive()

    def drive(self):
        distance = Vehicle.speed * Vehicle.step_time
        distance_rest = self.location_offset + distance - self.location.length

        if distance_rest > 0:
            self.drive_to_next(distance_rest)
        else:
            self.location_offset += distance

    def drive_to_next(self, distance):
        self.location_index += 1
        next_id = self.path_ids[self.location_index]
        next_infra = self.model.infra_dict[next_id]

        self.route_length += next_infra.length

        if isinstance(next_infra, Sink):
            self.arrive_at_next(next_infra, 0)
            self.removed_at_step = self.model.schedule.steps
            travel_time = self.removed_at_step - self.generated_at_step
            self.model.output_data.append({
                'travel_time': travel_time,
                'route_length': self.route_length,
                'generated_at': self.generated_at_step,
                'removed_at': self.removed_at_step,
                'source_id': self.generated_by.unique_id,
                'sink_id': next_infra.unique_id,
            })
            self.location.remove(self)
            return

        elif isinstance(next_infra, Bridge):
            self.waiting_time = next_infra.get_delay_time()
            if self.waiting_time > 0:
                self.arrive_at_next(next_infra, 0)
                self.state = Vehicle.State.WAIT
                return

        else:
            # Links and intersections: congestion only
            self.waiting_time = next_infra.get_congestion_delay()
            if self.waiting_time > 0:
                self.arrive_at_next(next_infra, 0)
                self.state = Vehicle.State.WAIT
                return

        if next_infra.length > distance:
            self.arrive_at_next(next_infra, distance)
        else:
            self.arrive_at_next(next_infra, 0)
            self.drive_to_next(distance - next_infra.length)

    def arrive_at_next(self, next_infra, location_offset):
        self.location.vehicle_count -= 1
        self.location = next_infra
        self.location_offset = location_offset
        self.location.vehicle_count += 1
        self.location.throughput += 1

# EOF -----------------------------------------------------------