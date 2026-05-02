class world:
    def __init__(self):
        self.width = 15
        self.height = 10
        #initial player position
        self.direction = "N"
        self.inventory = []
        self.agent_pos = (1,1)
        self.last_action = None
        # fill the grid with 0's
        self.grid = [["." for _ in range(self.width)] for _ in range(self.height)]

    #output the world with the player
    def render(self):
        for y in range(self.height):
            row = ""
            for x in range(self.width):
                if (x, y) == self.agent_pos:
                    row += "A"
                else:
                    row += self.grid[y][x]
            print(row)
    #handle walking
    def step(self, action):
        x, y = self.agent_pos
        #remember this action
        self.last_action = action
        if action == "MOVE_FORWARD":
            if self.direction == "N":
                new_pos = (x, y-1)
            elif self.direction == "S":
                new_pos = (x, y+1)
            elif self.direction == "E":
                new_pos = (x+1, y)
            elif self.direction == "W":
                new_pos = (x-1, y)

            nx, ny = new_pos

            # boundary check
            if 0 <= nx < self.width and 0 <= ny < self.height:
                # wall check
                if self.grid[ny][nx] != "#":
                    self.agent_pos = new_pos
        #handle turns
        elif action == "TURN_LEFT":
            dirs = ["N", "W", "S", "E"]
            self.direction = dirs[(dirs.index(self.direction)+1) % 4]

        elif action == "TURN_RIGHT":
            dirs = ["N", "E", "S", "W"]
            self.direction = dirs[(dirs.index(self.direction)+1) % 4]

    def get_tile(self, x, y):
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.grid[y][x]
        return "#"   # treat out-of-bounds as wall
    
    def get_observation(self):

        x, y = self.agent_pos
        #get the neighbouting tiles
        if self.direction == "N":
            front = (x, y-1)
            left = (x-1, y)
            right = (x+1, y)

        elif self.direction == "S":
            front = (x, y+1)
            left = (x+1, y)
            right = (x-1, y)

        elif self.direction == "E":
            front = (x+1, y)
            left = (x, y-1)
            right = (x, y+1)

        elif self.direction == "W":
            front = (x-1, y)
            left = (x, y+1)
            right = (x, y-1)
        #structure information
        obs = {
            "position": [x, y],
            "direction": self.direction,
            "inventory": self.inventory,
            "current_tile": self.get_tile(x, y),
            "last_action": self.last_action,
            "visible": {
                "front": self.get_tile(*front),
                "left": self.get_tile(*left),
                "right": self.get_tile(*right),
            },
            "goal": "Pick up key, open door, reach an apple"
        }

        return obs


grid = world()

obs = grid.get_observation()
print(obs)
grid.render()