import simpy
from Entity import Entity
from MessageBroker import MessageBroker

class Door(Entity):
    """
    【v13.2】乗降サービス全体の責任者（店長）に昇格したドア
    """
    def __init__(self, env: simpy.Environment, name: str, broker: MessageBroker, open_time=1.5, close_time=1.5):
        super().__init__(env, name)
        self.broker = broker
        self.open_time = open_time
        self.close_time = close_time
        self.command_topic = f"door/{self.name}/command"
        print(f"{self.env.now:.2f} [{self.name}] Door entity created. Listening on topic '{self.command_topic}'.")

    def run(self):
        """
        ドアのライフサイクル。エレベータからのサービス指示を待つ。
        """
        while True:
            task = yield self.broker.get(self.command_topic)
            task_type = task.get("task_type")
            if task_type == "SERVICE_FLOOR":
                yield self.env.process(self._process_service_floor(task))
            else:
                print(f"{self.env.now:.2f} [{self.name}] Received unknown task type: {task_type}")

    def _process_service_floor(self, task):
        """
        【師匠大改造】乗降サービス全体を取り仕切る店長の仕事
        """
        elevator_name = task.get("elevator_name")
        passengers_to_exit = task.get("passengers_to_exit")
        boarding_queues = task.get("boarding_queues")
        callback_event = task.get("callback_event")

        # 【師匠修正】乗車した乗客を記録するリスト
        boarded_passengers = []

        # 1. ドアを開ける
        print(f"{self.env.now:.2f} [{elevator_name}] Door Opening...")
        yield self.env.timeout(self.open_time)
        print(f"{self.env.now:.2f} [{elevator_name}] Door Opened.")
        
        # 2. 降車客を一人ずつ、本人のペースで降ろす
        for p in passengers_to_exit:
            exit_permission_event = self.env.event()
            yield p.exit_permission_event.put(exit_permission_event)
            yield exit_permission_event

        # 3. 乗車客を一人ずつ、本人のペースで乗せる
        for queue in boarding_queues:
            while len(queue.items) > 0:
                passenger = yield queue.get()
                board_permission_event = self.env.event()
                yield passenger.board_permission_event.put(board_permission_event)
                yield board_permission_event
                # 【師匠修正】乗車が完了した乗客をリストに追加
                boarded_passengers.append(passenger)

        # 4. ドアを閉める
        print(f"{self.env.now:.2f} [{elevator_name}] Door Closing...")
        yield self.env.timeout(self.close_time)
        print(f"{self.env.now:.2f} [{elevator_name}] Door Closed.")

        # 5. 運転手に業務完了報告書（乗車した乗客リスト付き）を提出する
        if callback_event and not callback_event.triggered:
            report = {"boarded": boarded_passengers}
            callback_event.succeed(report)

