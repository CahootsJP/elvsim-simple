import simpy

class MessageBroker:
    """
    Mediates communication between components within the simulation.
    Implements a topic-based publish-subscribe model.
    """
    def __init__(self, env: simpy.Environment):
        """
        Initialize the message broker

        Args:
            env (simpy.Environment): SimPy environment
        """
        self.env = env
        self.topics = {}  # Dictionary to hold Store for each topic
        self.broadcast_pipe = simpy.Store(self.env)

    def get_pipe(self, topic: str) -> simpy.Store:
        """
        Get or create a communication pipe (Store) for the specified topic
        """
        if topic not in self.topics:
            self.topics[topic] = simpy.Store(self.env)
        return self.topics[topic]

    def put(self, topic: str, message):
        """
        Publish (put) a message to the specified topic
        """
        print(f"{self.env.now:.2f} [Broker] Publish on '{topic}': {message}")
        pipe = self.get_pipe(topic)
        self.broadcast_pipe.put({'topic': topic, 'message': message})
        return pipe.put(message)

    def get(self, topic: str):
        """
        Wait to receive (get) a message from the specified topic
        """
        pipe = self.get_pipe(topic)
        return pipe.get()

    def get_broadcast_pipe(self) -> simpy.Store:
        """
        Method for Statistics class to access this pipe
        Returns the global broadcast pipe
        """
        return self.broadcast_pipe
    
    def get_current_time(self) -> float:
        """
        Get current simulation time
        
        This method provides time abstraction, allowing external systems
        (like GroupControlSystem) to access time without direct dependency
        on SimPy environment.
        
        Returns:
            Current simulation time
        """
        return self.env.now