import simpy
from Entity import Entity

class Door(Entity):
    """
    【v15.0】運転手からの直接の内線電話で動く、敏腕店長になったドア
    """
    def __init__(self, env: simpy.Environment, name: str, open_time=1.5, close_time=1.5):
        super().__init__(env, name)
        self.open_time = open_time
        self.close_time = close_time
        print(f"{self.env.now:.2f} [{self.name}] Door entity created.")

    def run(self):
        """
        このメソッドはもう使わへん。店長は、運転手からの直接の電話を待つ。
        """
        yield self.env.timeout(0) # 何もしないプロセス

    def service_floor_process(self, elevator_name, passengers_to_exit, boarding_queues):
        """
        【師匠大改造】運転手から直接呼び出される、乗降サービス本体
        """
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
                boarded_passengers.append(passenger)

        # 4. ドアを閉める
        print(f"{self.env.now:.2f} [{elevator_name}] Door Closing...")
        yield self.env.timeout(self.close_time)
        print(f"{self.env.now:.2f} [{elevator_name}] Door Closed.")

        # 5. 運転手に直接、業務完了報告書を返す
        return {"boarded": boarded_passengers}

