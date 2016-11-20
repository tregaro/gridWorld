import heapq
import math

max_player_size = 10


class PriorityQueue:
    def __init__(self):
        self.elements = []

    def empty(self):
        return len(self.elements) == 0

    def put(self, item, priority):
        heapq.heappush(self.elements, (priority, item))

    def get(self):
        return heapq.heappop(self.elements)[1]


class DistanceGridCell:
    def __init__(self, coordinate, grid):
        self._grid = grid

        self.cache_version = -1
        self._coordinate = coordinate
        x_cord, y_cord = coordinate

        # by default all walls are far away
        self.wall_dist = -1

        # by default all edges has 8 connections
        self.edges = [
            (-1, (x_cord, y_cord + 1)),
            (-1, (x_cord + 1, y_cord + 1)),
            (-1, (x_cord + 1, y_cord)),
            (0, (x_cord + 1, y_cord - 1)),
            (0, (x_cord, y_cord - 1)),
            (0, (x_cord - 1, y_cord - 1)),
            (0, (x_cord - 1, y_cord)),
            (0, (x_cord - 1, y_cord + 1)),
        ]

        # small edges is edges without the diagonals and is used for small characters
        self.small_edges = [
            (0, (x_cord, y_cord + 1)),
            (0, (x_cord, y_cord - 1)),
            (0, (x_cord + 1, y_cord)),
            (0, (x_cord - 1, y_cord)),
        ]

    @property
    def is_obstacle(self):
        return self.wall_dist == 0

    @property
    def coord(self):
        return self._coordinate

    def update_wall_dist(self, player_size):
        if self.wall_dist == 0:
            return

        if self.cache_version != self._grid.cache_version:
            self.cache_version = self._grid.cache_version
            grid = self._grid
            xc, yc = self.coord
            best_dist = player_size + 1
            for x in range(0, player_size):
                for y in range(0, player_size):
                    if x == 0 and y == 0:
                        continue

                    if x > 0 and y > 0:
                        cells = [
                            grid.get_cell((xc + x, yc + y)),
                            grid.get_cell((xc + x, yc - y)),
                            grid.get_cell((xc - x, yc - y)),
                            grid.get_cell((xc - x, yc + y)),
                        ]
                    elif x > 0:
                        cells = [
                            grid.get_cell((xc + x, yc)),
                            grid.get_cell((xc - x, yc)),
                        ]
                    else:
                        cells = [
                            grid.get_cell((xc, yc + y)),
                            grid.get_cell((xc, yc - y)),
                        ]

                    for cell in cells:
                        if cell.wall_dist == 0:
                            dist = cell.distance(self)
                            if dist < best_dist:
                                best_dist = dist

            self.wall_dist = best_dist

    def neighbors(self, player_size):
        self.update_wall_dist(player_size)

        if self.wall_dist < player_size / 2.0:
            return []

        if player_size == 1:
            edges = self.small_edges
        else:
            edges = self.edges

        grid = self._grid
        with_obstacles = []
        for offset, edge in edges:
            edge_cell = grid.get_cell(edge)
            edge_cell.update_wall_dist(player_size)
            if edge_cell.wall_dist > player_size / 2.0:
                with_obstacles.append(edge)

        return with_obstacles

    def cost(self, next_cell, max_cost):
        if self.is_obstacle or next_cell.is_obstacle:
            return max_cost
        return self.distance(next_cell)

    def distance(self, other_cell):
        current_coord = self._coordinate
        next_coord = other_cell.coord
        return math.hypot(next_coord[0] - current_coord[0], next_coord[1] - current_coord[1])


class DistanceGrid:
    def __init__(self):
        self._grid = {}
        self.cache_version = 0

    def get_cell(self, coordinate):
        cell = self._grid.get(coordinate, None)
        if cell is None:
            cell = DistanceGridCell(coordinate, self)
            self._grid[coordinate] = cell
        return cell

    @staticmethod
    def heuristic(a, b):
        (x1, y1) = a.coord
        (x2, y2) = b.coord
        return abs(x1 - x2) + abs(y1 - y2)

    def reconstruct_path(self, came_from, start, goal, reversed_path=True):
        current = self.get_cell(goal)
        path = [current.coord]
        start_cell = self.get_cell(start)
        while current != start_cell:
            current = came_from.get(current, None)
            if current is None:
                return []
            path.append(current.coord)

        if not reversed_path:
            path.reverse()

        return path

    def a_star_search(self, start, goal, player_size, max_cost=50):
        frontier = PriorityQueue()
        start_cell = self.get_cell(start)
        goal_cell = self.get_cell(goal)
        frontier.put(start_cell, 0)
        came_from = {}
        cost_so_far = {start_cell: 0}
        came_from[start_cell] = None

        if start_cell.cost(goal_cell, max_cost) >= max_cost:
            return {}, {}

        while not frontier.empty():
            current = frontier.get()

            if current == goal_cell:
                break

            for next_cell_coord in current.neighbors(player_size):
                next_cell = self.get_cell(next_cell_coord)
                new_cost = cost_so_far[current] + current.cost(next_cell, max_cost)
                if new_cost >= max_cost:
                    continue
                if next_cell not in cost_so_far or new_cost < cost_so_far[next_cell]:
                    cost_so_far[next_cell] = new_cost
                    priority = new_cost + self.heuristic(goal_cell, next_cell)
                    frontier.put(next_cell, priority)
                    came_from[next_cell] = current

        return came_from, cost_so_far

    def get_path(self, start, goal, player_size, max_cost=50):
        came_from, cost = self.a_star_search(
            start=start,
            goal=goal,
            player_size=player_size,
            max_cost=max_cost
        )

        if len(came_from) == 0:
            return [], -1

        path = self.reconstruct_path(
            came_from=came_from,
            start=start,
            goal=goal,
            reversed_path=True
        )

        return path, cost.get(self.get_cell(goal), 0)

    def set_cell_is_obstacle(self, coord, is_obstacle):
        if is_obstacle:
            self.get_cell(coord).wall_dist = 0
        else:
            self.get_cell(coord).wall_dist = -1
        self.cache_version += 1

    def update_player_size(self):
        self.cache_version += 1


