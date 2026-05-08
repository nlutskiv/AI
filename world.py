DEFAULT_LAYOUT = [
    "###############",
    "#A...#........#",
    "#....#........#",
    "#....#........#",
    "#....D........#",
    "#....#...T....#",
    "#....#........#",
    "#....#...K....#",
    "#....#........#",
    "###############",
]


class World:
    """2D grid world. Holds full ground truth.
    The agent only knows what get_observation reveals each turn."""

    LEGEND = {
        ".": "empty",
        "#": "wall",
        "K": "key",
        "D": "door",
        "A": "apple",
        "T": "trap",
    }

    def __init__(self, layout=None, start=(10, 8), facing="W", hp=5):
        layout = layout or DEFAULT_LAYOUT
        self.grid = [list(row) for row in layout]
        self.height = len(self.grid)
        self.width = len(self.grid[0])

        self.agent_pos = tuple(start)
        self.direction = facing
        self.inventory = []
        self.hp = hp
        self.steps = 0
        self.last_action = None
        self.last_action_result = None
        self.done = False
        self.win = False

    # ---------- helpers ----------
    def in_bounds(self, x, y):
        return 0 <= x < self.width and 0 <= y < self.height

    def get_tile(self, x, y):
        if self.in_bounds(x, y):
            return self.grid[y][x]
        return "#"

    def _forward_vec(self):
        return {"N": (0, -1), "E": (1, 0), "S": (0, 1), "W": (-1, 0)}[self.direction]

    def _right_vec(self):
        # 90 degrees clockwise of forward
        fx, fy = self._forward_vec()
        return (-fy, fx)

    # ---------- step ----------
    def step(self, action):
        self.last_action = action
        self.last_action_result = "ok"
        x, y = self.agent_pos

        if action == "MOVE_FORWARD":
            fx, fy = self._forward_vec()
            nx, ny = x + fx, y + fy
            tile = self.get_tile(nx, ny)
            if tile == "#":
                self.last_action_result = "blocked: wall"
            elif tile == "D":
                self.last_action_result = "blocked: closed door"
            elif not self.in_bounds(nx, ny):
                self.last_action_result = "blocked: edge of world"
            else:
                self.agent_pos = (nx, ny)
                if tile == "T":
                    self.hp -= 2
                    self.grid[ny][nx] = "."
                    self.last_action_result = f"stepped on trap, HP -2 (now {self.hp})"
                    if self.hp <= 0:
                        self.done = True
                        self.win = False
                        self.last_action_result += " — died"
                elif tile == "A":
                    self.done = True
                    self.win = True
                    self.last_action_result = "reached the apple"

        elif action == "TURN_LEFT":
            dirs = ["N", "W", "S", "E"]
            self.direction = dirs[(dirs.index(self.direction) + 1) % 4]

        elif action == "TURN_RIGHT":
            dirs = ["N", "E", "S", "W"]
            self.direction = dirs[(dirs.index(self.direction) + 1) % 4]

        elif action == "PICK_UP":
            tile = self.grid[y][x]
            if tile == "K":
                self.inventory.append("key")
                self.grid[y][x] = "."
                self.last_action_result = "picked up a key"
            else:
                self.last_action_result = "nothing to pick up here"

        elif action == "OPEN_DOOR":
            fx, fy = self._forward_vec()
            nx, ny = x + fx, y + fy
            if self.get_tile(nx, ny) != "D":
                self.last_action_result = "no door in front"
            elif "key" not in self.inventory:
                self.last_action_result = "you have no key"
            else:
                self.grid[ny][nx] = "."
                self.inventory.remove("key")
                self.last_action_result = "opened the door (key consumed)"

        elif action == "WAIT":
            self.last_action_result = "waited"

        else:
            self.last_action_result = f"unknown action: {action}"

        self.steps += 1

    # ---------- observation ----------
    def get_observation(self):
        x, y = self.agent_pos
        fx, fy = self._forward_vec()
        rx, ry = self._right_vec()

        # 8 tiles relative to facing direction
        rel = {
            "front":       (fx,        fy       ),
            "front_right": (fx + rx,   fy + ry  ),
            "right":       (rx,        ry       ),
            "back_right":  (-fx + rx,  -fy + ry ),
            "back":        (-fx,       -fy      ),
            "back_left":   (-fx - rx,  -fy - ry ),
            "left":        (-rx,       -ry      ),
            "front_left":  (fx - rx,   fy - ry  ),
        }
        visible = {name: self.get_tile(x + dx, y + dy) for name, (dx, dy) in rel.items()}

        return {
            "position": list(self.agent_pos),
            "direction": self.direction,
            "inventory": list(self.inventory),
            "hp": self.hp,
            "current_tile": self.get_tile(x, y),
            "last_action": self.last_action,
            "last_action_result": self.last_action_result,
            "visible": visible,
            "steps": self.steps,
        }

    # ---------- render ----------
    def render(self):
        glyph = {"N": "^", "E": ">", "S": "v", "W": "<"}[self.direction]
        print()
        for y in range(self.height):
            row = ""
            for x in range(self.width):
                row += glyph if (x, y) == self.agent_pos else self.grid[y][x]
            print(row)
        print(f"pos={self.agent_pos}  dir={self.direction}  hp={self.hp}  "
              f"inv={self.inventory}  step={self.steps}")
        if self.last_action:
            print(f"last: {self.last_action} -> {self.last_action_result}")
