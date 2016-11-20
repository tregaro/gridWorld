import cocos
import pyglet.window.mouse
from cocos import batch

from gridCanvas import GridCanvas
from pathCanvas import PathCanvas

use_distance_grid = True
if use_distance_grid:
    from distanceGrid import DistanceGrid as Grid
else:
    from grid import Grid

director = cocos.director.director
g_player_size = 1
g_grid_size = 16


class GridLayer(cocos.layer.Layer):
    def __init__(self):
        super(GridLayer, self).__init__()

        self.start_square = None
        self.end_square = None

        # Canvas that draws the grid
        self.add(GridCanvas(g_grid_size))

        # Canvas to draw paths
        self.path_canvas = PathCanvas()
        self.add(self.path_canvas)

        # Batched node to draw obstacles
        self.obstacles_batch_node = cocos.batch.BatchNode()
        self.add(self.obstacles_batch_node)
        self.obstacle_squares = {}

        # Grid used for path finding
        self._grid = Grid()
        self.path_cost = 0

    def update_path(self):
        path = self.get_start_to_end_path()
        path = [self.grid_to_world(grid_pos) for grid_pos in path]
        path = [(x + g_grid_size * g_player_size/2.0,
                 y + g_grid_size * g_player_size/2.0) for x, y in path]
        self.path_canvas.set_path(path)

    @staticmethod
    def world_to_grid(world_pos):
        return tuple(int(x // g_grid_size) for x in world_pos)

    @staticmethod
    def grid_to_world(grid_pos):
        return grid_pos[0] * g_grid_size, grid_pos[1] * g_grid_size

    @staticmethod
    def world_to_aligned_world(world_pos):
        return tuple(int(x // g_grid_size) * g_grid_size for x in world_pos)

    def get_grid_obstacle(self, position):
        return self._grid.get_cell(self.world_to_grid(position)).is_obstacle

    def set_grid_obstructed(self, position, is_obstructed, update_path=True):
        # Check if we don't need to do anything
        if self.get_grid_obstacle(position) == is_obstructed:
            return

        grid_pos = self.world_to_grid(position)
        self._grid.set_cell_is_obstacle(grid_pos, is_obstructed)

        if is_obstructed:
            obstacle = cocos.sprite.Sprite(
                image='assets/white.png',
                scale=g_grid_size
            )
            obstacle.position = self.grid_to_world(grid_pos)
            self.obstacles_batch_node.add(obstacle)
            self.obstacle_squares[grid_pos] = obstacle
        else:
            current_obstacle = self.obstacle_squares.get(grid_pos, None)
            self.obstacles_batch_node.remove(current_obstacle)
            del self.obstacle_squares[grid_pos]

        if update_path:
            self.update_path()

    def toggle_grid_obstacle(self, position):
        # Toggle this obstacle
        self.set_grid_obstructed(position, not self.get_grid_obstacle(position))

    def set_start_pos(self, position):
        if self.start_square is None:
            self.start_square = cocos.layer.ColorLayer(
                0, 200, 0, 255,
                g_grid_size * g_player_size,
                g_grid_size * g_player_size)
            self.add(self.start_square)

        # align to grid
        aligned_pos = self.world_to_aligned_world(position)
        if aligned_pos != self.start_square.position:
            self.start_square.position = aligned_pos
            self.update_path()

    def set_end_pos(self, position):
        if self.end_square is None:
            self.end_square = cocos.layer.ColorLayer(
                200, 0, 0, 255,
                g_grid_size * g_player_size,
                g_grid_size * g_player_size)
            self.add(self.end_square)

        # align to grid
        aligned_pos = self.world_to_aligned_world(position)
        if aligned_pos != self.end_square.position:
            self.end_square.position = aligned_pos
            self.update_path()

    def update_player_size(self):
        if self.end_square is not None:
            end_pos = self.end_square.position
            self.remove(self.end_square)
            self.end_square = None
            self.set_end_pos(end_pos)

        if self.start_square is not None:
            start_pos = self.start_square.position
            self.remove(self.start_square)
            self.start_square = None
            self.set_start_pos(start_pos)

        self._grid.update_player_size()

    def update_state(self, state):
        if state == 'path':
            self.path_canvas.scale = 1
            self.update_path()
        else:
            self.path_canvas.scale = 0

    def get_start_to_end_path(self):
        if self.start_square is None or self.end_square is None:
            return []

        # get path
        start_pos = self.world_to_grid(self.start_square.position)
        end_pos = self.world_to_grid(self.end_square.position)

        path, cost = self._grid.get_path(
            start=start_pos,
            goal=end_pos,
            player_size=g_player_size,
            max_cost=50
        )

        self.path_cost = cost
        return path


class MouseDisplay(cocos.layer.Layer):

    is_event_handler = True     #: enable director.window events

    def __init__(self, grid_layer):
        super(MouseDisplay, self).__init__()

        win_size = director.get_window_size()

        self._grid = grid_layer
        self.state = 'path'

        self.text_bg = cocos.layer.ColorLayer(0, 0, 0, 255, win_size[0], 23)
        self.text_bg.position = (0, 0)

        self.add(self.text_bg)
        self.text = cocos.text.Label('State: {}'.format(self.state), font_size=11, x=5, y=5)
        self.add(self.text)

        self.update_text()

        self.current_grid_obstructed = False
        self.keys_pressed = set()

    def on_mouse_motion(self, x, y, dx, dy):
        pass

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        mouse_pos = director.get_virtual_coordinates(x, y)
        if self.state == 'edit':
            if buttons & pyglet.window.mouse.LEFT:
                self._grid.set_grid_obstructed(
                    mouse_pos,
                    self.current_grid_obstructed,
                    False)
        elif self.state == 'path':
            if buttons & pyglet.window.mouse.LEFT:
                self._grid.set_start_pos(mouse_pos)
            elif buttons & pyglet.window.mouse.RIGHT:
                self._grid.set_end_pos(mouse_pos)

        self.update_text()

    def on_mouse_press(self, x, y, buttons, modifiers):
        mouse_pos = director.get_virtual_coordinates(x, y)
        if self.state == 'path':
            if buttons & pyglet.window.mouse.LEFT:
                self._grid.set_start_pos(mouse_pos)
            elif buttons & pyglet.window.mouse.RIGHT:
                self._grid.set_end_pos(mouse_pos)
        elif self.state == 'edit':
            if buttons & pyglet.window.mouse.LEFT:
                self._grid.toggle_grid_obstacle(mouse_pos)
                self.current_grid_obstructed = self._grid.get_grid_obstacle(mouse_pos)

        self.update_text()

    def on_key_press(self, key, modifiers):
        self.keys_pressed.add(key)

    def update_text(self):
        if self.state == 'edit':
            self.text.element.text = 'Mode: Edit Obstructions (left click to toggle grid obstruction). \'r\' to switch to path.'
        elif self.state == 'path':
            self.text.element.text = (
                'Mode: Path cost: {cost} (left & right click to set start & end pos). \'e\' to switch to edit'.format(
                    cost=self._grid.path_cost
                )
            )
        else:
            self.text.element.text = 'State: {}'.format(self.state)

    def on_key_release(self, key, modifiers):
        global g_player_size
        self.keys_pressed.remove(key)
        if key == ord('e'):
            self.state = 'edit'
            self._grid.update_state(self.state)
        elif key == ord('r'):
            self.state = 'path'
            self._grid.update_state(self.state)
        elif key == ord('d'):
            g_player_size = min(10, g_player_size + 1)  # limit to 10 square size
            self._grid.update_player_size()
        elif key == ord('f'):
            g_player_size = max(1, g_player_size - 1)
            self._grid.update_player_size()

        self.update_text()


if __name__ == "__main__":
    director.init(fullscreen=False)

    grid = GridLayer()
    mouse_display = MouseDisplay(grid)

    director.run(cocos.scene.Scene(
        grid,
        mouse_display,
    ))