import os
from collections import defaultdict
from functools import partial

import cocos
import pyglet
from cocos.batch import BatchNode
from cocos.draw import Canvas
from cocos.euclid import Point2

# THINGS to tweak to get different effects
g_should_trace_walls = True  # If this is False we don't trace against walls for line of sight. Meaning you will see everything withing a radius.
g_fog_neighbour_radius = 0  # This is the radius that fog is uncovered from visible slots.
g_player_view_radius = 28  # The radius that the player can see
g_check_around_player = True  # If True we will check from the point of view around the player.

# Don't change these values...
# Constants
director = cocos.director.director
g_player_size = 1
g_grid_size = 16
FULL_COVER, HALF_COVER, NO_COVER = range(3)
FRIEND, ENEMY = range(2)

def world_to_grid(world_pos):
    return tuple(int(x // g_grid_size) for x in world_pos)


def grid_to_world(grid_pos):
    return grid_pos[0] * g_grid_size, grid_pos[1] * g_grid_size


def align_pos_to_grid(position):
    return grid_to_world(world_to_grid(position))


class PlayerNode(cocos.cocosnode.CocosNode):
    def __init__(self, player_type):
        super(PlayerNode, self).__init__()

        player_path = os.path.abspath('../assets/circle.png')
        player_img = pyglet.image.load(player_path)
        player = cocos.sprite.Sprite(
            image=player_img,
            scale=g_grid_size / 32.0,
            color=(108, 255, 108) if player_type is FRIEND else (255, 108, 108),
            anchor=(0, 0)
        )

        self.add(player)
        self.player = player


class FogOfWarCanvas(Canvas):
    def __init__(self, x, y, fog_squares, cache_size):
        super(FogOfWarCanvas, self).__init__()
        self._current_state = fog_squares
        self._cached_state = defaultdict(lambda: True)
        self.x = x - 1 if x > 0 else 0
        self.y = y - 1 if y > 0 else 0
        self.cache_size = cache_size

    def needs_update(self):
        for x in xrange(self.x, self.x + self.cache_size):
            for y in xrange(self.y, self.y + self.cache_size):
                world_grid_pos = x, y
                if self._cached_state[world_grid_pos] != self._current_state[world_grid_pos]:
                    return True

        return False

    def render(self):
        line_color = (50, 50, 50, 255)

        self.set_stroke_width(g_grid_size + 2)
        self.set_color(line_color)
        # self.set_endcap(cocos.draw.SQUARE_CAP)
        self.set_join(cocos.draw.MITER_JOIN)

        for x in xrange(self.x, self.x + self.cache_size + 1):
            for y in xrange(self.y, self.y + self.cache_size + 1):
                world_grid_pos = x, y
                fog_visible = self._current_state[world_grid_pos]
                self._cached_state[world_grid_pos] = fog_visible

                if fog_visible:
                    world_pos = grid_to_world(world_grid_pos)
                    aligned_world_pos = (x * g_grid_size, y * g_grid_size) - Point2(g_grid_size / 2, g_grid_size / 2)

                    self.move_to(aligned_world_pos)  # + Point2(0, g_grid_size))
                    self.line_to(aligned_world_pos + Point2(g_grid_size, 0))


class FogOfWarNode(cocos.cocosnode.CocosNode):
    def __init__(self, game_world):
        super(FogOfWarNode, self).__init__()

        self.game_world = game_world
        self.fog_squares = defaultdict(lambda: True)
        self.fog_squares_screen_space = defaultdict(lambda: True)

        win_size = director.get_window_size()
        grid_size = (win_size[0] / g_grid_size), (win_size[1] / g_grid_size)
        self.fog_grid = []
        cache_size = 16
        for x in xrange(grid_size[0]):
            for y in xrange(grid_size[1]):
                if x % cache_size == 0 and y % cache_size == 0:
                    self.fog_grid.append(
                        FogOfWarCanvas(
                            x=x,
                            y=y,
                            fog_squares=self.fog_squares_screen_space,
                            cache_size=cache_size
                        )
                    )

        for grid in self.fog_grid:
            self.add(grid)

        self.update_fog_grid()

    def update_fog_grid(self):
        win_size = director.get_window_size()
        grid_size = (win_size[0] / g_grid_size), (win_size[1] / g_grid_size)

        for x in xrange(grid_size[0] + 1):
            for y in xrange(grid_size[1] + 1):
                world_grid_pos = x, y

                world_pos = grid_to_world(world_grid_pos)
                aligned_world_pos = align_pos_to_grid(self.game_world.point_to_local(world_pos))

                # Visible if anything is visible within a radius
                fog_grid_pos = world_to_grid(aligned_world_pos)
                fog_visible = self.fog_squares[fog_grid_pos]

                if fog_visible:
                    radius = g_fog_neighbour_radius
                    for radius_x in xrange(-radius, radius + 1):
                        if not fog_visible:
                            break
                        for radius_y in xrange(-radius, radius + 1):
                            new_fog_grid_pos = tuple(fog_grid_pos + Point2(radius_x, radius_y))
                            fog_visible = self.fog_squares[new_fog_grid_pos]
                            if not fog_visible:
                                break

                self.fog_squares_screen_space[world_grid_pos] = fog_visible

        for square in self.fog_grid:
            if square.needs_update():
                square.free()

    def set_grid_pos_visible(self, grid_pos, is_visible):
        self.fog_squares[tuple(grid_pos)] = not is_visible


class GameLayer(cocos.layer.Layer):
    is_event_handler = True  #: enable director.window events

    def __init__(self):
        super(GameLayer, self).__init__()

        self.game_world = cocos.cocosnode.CocosNode()
        self.add(self.game_world)

        self.keys_pressed = set()
        self.player = PlayerNode(FRIEND)
        self.game_world.add(self.player)

        # Fog of war Node
        self.fow = FogOfWarNode(self.game_world)

        # Update camera
        self.update_camera()

        bg_path = os.path.abspath("../assets/grid.png")
        bg_img = pyglet.image.load(bg_path)
        bg = cocos.sprite.Sprite(bg_img, anchor=(0, 0))
        # self.add(bg)

        # Batched node to draw obstacles
        self.obstacles_batch_node = BatchNode()
        self.game_world.add(self.obstacles_batch_node)
        self.obstacle_squares = {}

        # Load obstacles from image
        bg_texture_data = bg.image.get_image_data()
        full_cover_colors = [[145, 145, 145]]
        half_cover_colors = [[133, 175, 133]]
        self.mark_cover_from_colors(full_cover_colors, FULL_COVER, bg)
        self.mark_cover_from_colors(half_cover_colors, HALF_COVER, bg)

        self.enemies = []
        enemy_colors = [[255, 0, 0]]
        self.do_something_from_colors(enemy_colors, bg, self.add_enemy)

        self.add(self.fow)

    def add_enemy(self, position):
        enemy = PlayerNode(ENEMY)
        enemy.position = align_pos_to_grid(position)
        self.enemies.append(enemy)
        self.game_world.add(enemy)

    @staticmethod
    def do_something_from_colors(colors, sprite, callback):
        bg_texture_data = sprite.image.get_image_data()
        data = bg_texture_data.get_data('RGB', sprite.width * 3)
        for x in range(g_grid_size / 2, sprite.width, g_grid_size):
            for y in range(g_grid_size / 2, sprite.height, g_grid_size):
                pos = (sprite.width * y + x) * 3
                rgb = map(ord, data[pos:pos + 3])
                valid = False
                limit = 2
                for valid_color in colors:
                    if valid:
                        break
                    valid = True
                    for i in range(0, 3):
                        valid = valid and abs(valid_color[i] - rgb[i]) < limit

                if valid:
                    callback(position=(x, y))

    def mark_cover_from_colors(self, colors, cover_type, sprite):
        self.do_something_from_colors(colors, sprite, partial(self.set_grid_obstructed, obstructed_type=cover_type))

    def on_key_press(self, key, modifiers):
        self.keys_pressed.add(key)

    def on_key_release(self, key, modifiers):
        self.keys_pressed.remove(key)

        move_key_map = {
            ord('w'): Point2(0, 1),
            ord('a'): Point2(-1, 0),
            ord('s'): Point2(0, -1),
            ord('d'): Point2(1, 0),
        }
        if key in move_key_map:
            grid_pos = world_to_grid(self.player.position)
            new_pos = Point2(grid_pos[0], grid_pos[1]) + move_key_map[key]
            if self.is_valid_player_grid_pos(new_pos):
                self.player.position = grid_to_world(new_pos)

                # Do circle around player
                radius = g_player_view_radius
                square_radius = radius * radius
                for x in xrange(-radius, radius + 1):
                    for y in xrange(-radius, radius + 1):
                        if (x * x + y * y) <= square_radius:
                            target_pos = new_pos + (x, y)
                            hit, hit_pos = self.raytrace(new_pos, target_pos, ignore_half_cover=True)
                            if hit:
                                self.fow.set_grid_pos_visible(hit_pos, True)

                            # Check from around the player if we can't see.
                            if hit and g_check_around_player:
                                moves = [
                                    Point2(1, 0),
                                    Point2(-1, 0),
                                    Point2(0, 1),
                                    Point2(0, -1),
                                    Point2(1, 1),
                                    Point2(1, -1),
                                    Point2(-1, 1),
                                    Point2(-1, -1),
                                ]
                                for move in moves:
                                    if self.is_valid_player_grid_pos(new_pos + move):
                                        hit, hit_pos = self.raytrace(new_pos + move, target_pos, ignore_half_cover=True)
                                        if hit:
                                            self.fow.set_grid_pos_visible(hit_pos, True)
                                        elif not hit:
                                            break

                            if not hit:
                                self.fow.set_grid_pos_visible(new_pos + (x, y), True)

                self.update_camera()

    def update_camera(self):
        world_pos = self.game_world.point_to_world(self.player.position)
        win_size = director.get_window_size()
        padding = 96
        if world_pos[0] < padding:
            self.game_world.position += Point2(padding - world_pos[0], 0)
        elif (win_size[0] - world_pos[0]) < padding:
            self.game_world.position -= Point2(padding - (win_size[0] - world_pos[0]), 0)
        if world_pos[1] < padding:
            self.game_world.position += Point2(0, padding - world_pos[1])
        elif (win_size[1] - world_pos[1]) < padding:
            self.game_world.position -= Point2(0, padding - (win_size[1] - world_pos[1]))

        self.fow.update_fog_grid()

    def is_valid_player_grid_pos(self, grid_pos):
        grid_pos = tuple(int(v) for v in grid_pos)
        return grid_pos not in self.obstacle_squares

    def set_grid_obstructed(self, position, obstructed_type):
        grid_pos = world_to_grid(position)

        # Check if we don't need to do anything
        if grid_pos in self.obstacle_squares and self.obstacle_squares[grid_pos].cover_type == obstructed_type:
            return

        if obstructed_type == FULL_COVER or obstructed_type == HALF_COVER:
            obstacle_path = os.path.abspath('../assets/white.png')
            obstacle_img = pyglet.image.load(obstacle_path)
            obstacle = cocos.sprite.Sprite(
                image=obstacle_img,
                scale=g_grid_size,
                color=(128, 128, 128) if obstructed_type == FULL_COVER else (50, 128, 50)
            )
            obstacle.cover_type = obstructed_type
            obstacle.position = grid_to_world(grid_pos)
            self.obstacles_batch_node.add(obstacle)
            self.obstacle_squares[grid_pos] = obstacle
        else:
            current_obstacle = self.obstacle_squares.get(grid_pos, None)
            self.obstacles_batch_node.remove(current_obstacle)
            del self.obstacle_squares[grid_pos]

    def raytrace(self, grid_pos_start, grid_pos_end, ignore_half_cover=False):
        if not g_should_trace_walls:
            return False, None

        x0, y0 = grid_pos_start
        x1, y1 = grid_pos_end
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        x, y = x0, y0
        n = 1 + dx + dy
        x_inc = 1 if (x1 > x0) else -1
        y_inc = 1 if (y1 > y0) else -1
        error = dx - dy
        dx *= 2
        dy *= 2

        for _ in xrange(n):
            if (x, y) in self.obstacle_squares:
                if ignore_half_cover and self.obstacle_squares[(x, y)].cover_type != HALF_COVER:
                    return True, (x, y)  # We hit something
            if error > 0:
                x += x_inc
                error -= dy
            else:
                y += y_inc
                error += dx

        # We hit nothing
        return False, None


class DebugConsole(cocos.layer.Layer):
    is_event_handler = True  #: enable director.window events

    def __init__(self):
        super(DebugConsole, self).__init__()

        win_size = director.get_window_size()

        self._drag_start = (0, 0)
        self._grid_pos_start = (0, 0)

        self.text_bg = cocos.layer.ColorLayer(50, 50, 50, 255, win_size[0], 23)
        self.text_bg.position = (0, 0)

        self.add(self.text_bg)
        self.text = cocos.text.Label(':', font_size=11, x=5, y=6)
        self.text_bg.add(self.text)

        self.keys_pressed = set()
        self._console_enabled = False
        self.text_bg.visible = self._console_enabled

    def on_key_press(self, key, modifiers):
        self.keys_pressed.add(key)

    def on_key_release(self, key, modifiers):
        self.keys_pressed.remove(key)

        if key == ord('`'):
            self._console_enabled = not self._console_enabled
            self.text_bg.visible = self._console_enabled


if __name__ == "__main__":
    director.init(
        fullscreen=False,
        width=16 * 80,
        height=16 * 50
    )
    # director.show_FPS = True
    game_layer = GameLayer()
    #game_layer.scale = 0.5
    director.run(cocos.scene.Scene(
        game_layer,
        DebugConsole()
    ))
