import simpy
from Entity import Entity

class Door(Entity):
    """
    Door that operates via direct communication from the elevator operator
    """
    def __init__(self, env: simpy.Environment, name: str, open_time=1.5, close_time=1.5, broker=None, elevator_name: str = None):
        super().__init__(env, name)
        self.open_time = open_time
        self.close_time = close_time
        self.broker = broker
        self.elevator_name: str = elevator_name
        self._current_floor: int = 1  # デフォルト階数
        print(f"{self.env.now:.2f} [{self.name}] Door entity created.")

    def run(self):
        """
        This method is no longer used. The door waits for direct calls from the elevator operator.
        """
        yield self.env.timeout(0)  # Idle process

    def _broadcast_door_event(self, event_type: str, current_floor: int = None):
        """ドアイベントをメッセージブローカーに送信します。"""
        if not self.broker or not self.elevator_name:
            return
        
        # current_floorが指定されていない場合は、内部の_current_floorを使用
        floor = current_floor if current_floor is not None else self._current_floor
        
        door_event_message = {
            "timestamp": self.env.now,
            "elevator_name": self.elevator_name,
            "door_id": self.name,
            "event_type": event_type,
            "floor": floor
        }
        door_event_topic = f"elevator/{self.elevator_name}/door_events"
        self.env.process(self._send_message(door_event_topic, door_event_message))

    def _send_message(self, topic: str, message: dict):
        """メッセージをブローカーに送信するプロセス。"""
        if self.broker:
            yield self.broker.put(topic, message)

    def set_broker_and_elevator(self, broker, elevator_name: str):
        """後からMessageBrokerとエレベータ名を設定します。"""
        self.broker = broker
        self.elevator_name = elevator_name

    def set_current_floor(self, floor: int):
        """現在の階数を設定します。"""
        self._current_floor = floor

    def service_floor_process(self, elevator_name, passengers_to_exit, boarding_queues):
        """
        Main boarding/alighting service process called directly by the elevator operator
        """
        boarded_passengers = []

        # 1. Open the door
        print(f"{self.env.now:.2f} [{elevator_name}] Door Opening...")
        # 戸開動作開始イベントを送信
        self._broadcast_door_event("DOOR_OPENING_START")
        
        yield self.env.timeout(self.open_time)
        print(f"{self.env.now:.2f} [{elevator_name}] Door Opened.")
        # 戸開完了イベントを送信
        self._broadcast_door_event("DOOR_OPENING_COMPLETE")
        
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
        # 戸閉動作開始イベントを送信
        self._broadcast_door_event("DOOR_CLOSING_START")
        
        yield self.env.timeout(self.close_time)
        print(f"{self.env.now:.2f} [{elevator_name}] Door Closed.")
        # 戸閉完了イベントを送信
        self._broadcast_door_event("DOOR_CLOSING_COMPLETE")

        # 5. Return completion report directly to the elevator operator
        return {"boarded": boarded_passengers}

