# Keeps state of collision
# Generates path from a to b
# Generates possible paths from point with max distance, used to generate path visualization,
# can be used to show field of view as well.


import heapq
import math


class PriorityQueue:
    def __init__(self):
        self.elements = []

    def empty(self):
        return len(self.elements) == 0

    def put(self, item, priority):
        heapq.heappush(self.elements, (priority, item))

    def get(self):
        return heapq.heappop(self.elements)[1]


class GridCell:
    def __init__(self, coordinate, grid):
        self._grid = grid
        self.cache_version = -1

        self.neighbor_cache = {}

        # by default we are not an obstacle
        self.is_obstacle = False
        self._coordinate = coordinate
        x_cord, y_cord = coordinate

        # by default all edges has 8 connections
        self.edges = [
            (x_cord, y_cord + 1),
            (x_cord + 1, y_cord + 1),
            (x_cord + 1, y_cord),
            (x_cord + 1, y_cord - 1),
            (x_cord, y_cord - 1),
            (x_cord - 1, y_cord - 1),
            (x_cord - 1, y_cord),
            (x_cord - 1, y_cord + 1),
        ]

        # small edges is edges without the diagonals and is used for small characters
        self.small_edges = [
            (x_cord, y_cord + 1),
            (x_cord, y_cord - 1),
            (x_cord + 1, y_cord),
            (x_cord - 1, y_cord),
        ]

    @property
    def coord(self):
        return self._coordinate

    def neighbors(self, player_size):
        if self.is_obstacle:
            return []

        cache = self.neighbor_cache.get((self.coord, player_size), None)
        if cache is not None and self._grid.cache_version == self.cache_version:
            return cache

        edges = []
        if player_size == 1:
            edges = self.small_edges
        else:
            edges = self.edges

        grid = self._grid
        with_obstacles = []
        for edge in edges:
            if not grid.get_cell(edge).is_obstacle:
                with_obstacles.append(edge)

        with_size = []
        for edge in with_obstacles:
            if grid.check_square_size(edge, player_size):
                with_size.append(edge)

        self.neighbor_cache[(self.coord, player_size)] = with_size
        self.cache_version = self._grid.cache_version
        return with_size

    def cost(self, next_cell, max_cost):
        if self.is_obstacle or next_cell.is_obstacle:
            return max_cost
        current_coord = self._coordinate
        next_coord = next_cell.coord
        return math.hypot(next_coord[0] - current_coord[0], next_coord[1] - current_coord[1])


class Grid:
    def __init__(self):
        self._grid = {}
        self.cache_version = 0

    def get_cell(self, coordinate):
        cell = self._grid.get(coordinate, None)
        if cell is None:
            cell = GridCell(coordinate, self)
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

    def check_square_size(self, coord, player_size):
        for x in range(0, player_size):
            for y in range(0, player_size):
                x_coord, y_coord = coord
                check_cell = (x_coord + x, y_coord + y)
                if self.get_cell(check_cell).is_obstacle:
                    return False

        return True

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
        self.get_cell(coord).is_obstacle = is_obstacle
        self.cache_version += 1

    def update_player_size(self):
        self.cache_version += 1


