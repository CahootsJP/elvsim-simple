import simpy
from Entity import Entity

class Door(Entity):
    """
    Door that operates via direct communication from the elevator operator
    """
    def __init__(self, env: simpy.Environment, name: str, open_time=1.5, close_time=1.5):
        super().__init__(env, name)
        self.open_time = open_time
        self.close_time = close_time
        print(f"{self.env.now:.2f} [{self.name}] Door entity created.")

    def run(self):
        """
        This method is no longer used. The door waits for direct calls from the elevator operator.
        """
        yield self.env.timeout(0)  # Idle process

    def service_floor_process(self, elevator_name, passengers_to_exit, boarding_queues):
        """
        Main boarding/alighting service process called directly by the elevator operator
        """
        boarded_passengers = []

        # 1. Open the door
        print(f"{self.env.now:.2f} [{elevator_name}] Door Opening...")
        yield self.env.timeout(self.open_time)
        print(f"{self.env.now:.2f} [{elevator_name}] Door Opened.")
        
        # 2. Let passengers exit one by one at their own pace
        for p in passengers_to_exit:
            exit_permission_event = self.env.event()
            yield p.exit_permission_event.put(exit_permission_event)
            yield exit_permission_event

        # 3. Let passengers board one by one at their own pace
        for queue in boarding_queues:
            while len(queue.items) > 0:
                passenger = yield queue.get()
                board_permission_event = self.env.event()
                yield passenger.board_permission_event.put(board_permission_event)
                yield board_permission_event
                boarded_passengers.append(passenger)

        # 4. Close the door
        print(f"{self.env.now:.2f} [{elevator_name}] Door Closing...")
        yield self.env.timeout(self.close_time)
        print(f"{self.env.now:.2f} [{elevator_name}] Door Closed.")

        # 5. Return completion report directly to the elevator operator
        return {"boarded": boarded_passengers}

