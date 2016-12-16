import os
from collections import defaultdict

import cocos
import pyglet
from cocos.draw import Canvas
from cocos.euclid import Point2

# THINGS to tweak to get different effects
g_should_trace_walls = True  # If this is False we don't trace against walls for line of sight. Meaning you will see everything withing a radius.
g_fog_neighbour_radius = 1  # This is the radius that fog is uncovered from visible slots.
g_player_view_radius = 28  # The radius that the player can see
g_check_around_player = True  # If True we will check from the point of view around the player.
g_steps_fog_stays_around = 100  # The number of steps/moves that fog stays obstructed
g_steps_half_fog_stays_around = 2  # The number of steps/moves that fog is gone until it becomes unvisited

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


class ColoredGridCanvas(Canvas):
    def __init__(self, x, y, full_grid, local_cache_size, line_color):
        super(ColoredGridCanvas, self).__init__()
        self._current_state = full_grid
        self._cached_state = defaultdict(lambda: True)
        self.grid_x = x
        self.grid_y = y
        self.cache_size = local_cache_size
        self.line_color = line_color
        self.debug_on = False

    def needs_update(self):
        for x in xrange(self.grid_x, self.grid_x + self.cache_size + 1):
            for y in xrange(self.grid_y, self.grid_y + self.cache_size + 1):
                world_grid_pos = x, y
                if self._cached_state[world_grid_pos] != self._current_state[world_grid_pos]:
                    return True

        return False

    def render(self):
        line_color = self.line_color
        self.set_stroke_width(g_grid_size)
        self.set_color(line_color)
        self.set_endcap(cocos.draw.SQUARE_CAP)

        is_drawing = False
        start_grid_offset = Point2(g_grid_size / 2, +g_grid_size / 2)
        end_grid_offset = Point2(g_grid_size / 2, -g_grid_size / 2 + 0.01)

        for x in xrange(self.grid_x, self.grid_x + self.cache_size):
            # if we are drawing then finish the line when we move to a new line
            if is_drawing:
                is_drawing = False
                old_x = x - 1
                old_y = self.grid_y + self.cache_size
                self.line_to((old_x * g_grid_size, old_y * g_grid_size) + end_grid_offset)

            # move to new line
            new_x = x
            new_y = 0
            self.move_to((new_x * g_grid_size, new_y * g_grid_size) + start_grid_offset)

            for y in xrange(self.grid_y, self.grid_y + self.cache_size):
                world_grid_pos = x, y
                square_visible = self._current_state[world_grid_pos]
                self._cached_state[world_grid_pos] = square_visible

                if square_visible and not is_drawing:
                    is_drawing = True
                    new_x = x
                    new_y = y
                    self.move_to((new_x * g_grid_size, new_y * g_grid_size) + start_grid_offset)
                elif not square_visible and is_drawing:
                    is_drawing = False
                    old_x = x
                    old_y = y
                    self.line_to((old_x * g_grid_size, old_y * g_grid_size) + end_grid_offset)

        if is_drawing:
            is_drawing = False
            old_x = self.grid_x + self.cache_size - 1
            old_y = self.grid_y + self.cache_size
            self.line_to((old_x * g_grid_size, old_y * g_grid_size) + end_grid_offset)

        # draw a frame for debug
        if self.debug_on:
            self.set_stroke_width(1)
            self.move_to(self.local_grid_to_world((0, 0)))
            self.line_to(self.local_grid_to_world((self.cache_size, 0)))
            self.line_to(self.local_grid_to_world((self.cache_size, self.cache_size)))
            self.line_to(self.local_grid_to_world((0, self.cache_size)))
            self.line_to(self.local_grid_to_world((0, 0)))

    def local_grid_to_world(self, local_grid_pos):
        return (
            (self.grid_x + local_grid_pos[0]) * g_grid_size,
            (self.grid_y + local_grid_pos[1]) * g_grid_size
        )


class ColoredGridNode(cocos.cocosnode.CocosNode):
    def __init__(self, game_world, inverted, line_color, cache_size=16):
        super(ColoredGridNode, self).__init__()

        self.game_world = game_world
        self._grid_squares = defaultdict(lambda: (inverted, -1))
        self.squares_screen_space = defaultdict(lambda: True)
        self.inverted = inverted

        win_size = director.get_window_size()
        grid_size = (win_size[0] / g_grid_size), (win_size[1] / g_grid_size)
        self.grid_canvases = []
        cache_size = 16
        for x in xrange(grid_size[0]):
            for y in xrange(grid_size[1]):
                if x % cache_size == 0 and y % cache_size == 0:
                    self.grid_canvases.append(
                        ColoredGridCanvas(
                            x=x,
                            y=y,
                            full_grid=self.squares_screen_space,
                            local_cache_size=cache_size,
                            line_color=line_color
                        )
                    )

        for grid in self.grid_canvases:
            self.add(grid)

    def grid_pos_is_active(self, grid_pos):
        grid_visible, turn_visible = self._grid_squares[grid_pos]
        return grid_visible if (
            turn_visible < 0 or
            turn_visible > self.game_world.current_turn
        ) else not grid_visible

    def update_grid(self):
        win_size = director.get_window_size()
        grid_size = (win_size[0] / g_grid_size), (win_size[1] / g_grid_size)

        for x in xrange(grid_size[0] + 1):
            for y in xrange(grid_size[1] + 1):
                world_grid_pos = x, y

                world_pos = grid_to_world(world_grid_pos)
                aligned_world_pos = align_pos_to_grid(self.game_world.point_to_local(world_pos))

                grid_pos = world_to_grid(aligned_world_pos)
                grid_visible, num_turns_visible = self._grid_squares[grid_pos]

                self.squares_screen_space[world_grid_pos] = grid_visible

        for square in self.grid_canvases:
            if square.needs_update():
                square.free()

    def set_grid_pos_visible(self, grid_pos, is_visible, num_turns_visible=-1):
        self._grid_squares[tuple(grid_pos)] = (
            is_visible if not self.inverted else not is_visible,
            num_turns_visible
        )


class FogOfWarNode(ColoredGridNode):
    def update_grid(self):
        win_size = director.get_window_size()
        grid_size = (win_size[0] / g_grid_size), (win_size[1] / g_grid_size)

        for x in xrange(grid_size[0] + 1):
            for y in xrange(grid_size[1] + 1):
                world_grid_pos = x, y

                world_pos = grid_to_world(world_grid_pos)
                aligned_world_pos = align_pos_to_grid(self.game_world.point_to_local(world_pos))

                # Visible if anything is visible within a radius
                fog_grid_pos = world_to_grid(aligned_world_pos)
                fog_visible = self.grid_pos_is_active(fog_grid_pos)

                if fog_visible:
                    radius = g_fog_neighbour_radius
                    for radius_x in xrange(-radius, radius + 1):
                        if not fog_visible:
                            break
                        for radius_y in xrange(-radius, radius + 1):
                            new_fog_grid_pos = tuple(fog_grid_pos + Point2(radius_x, radius_y))
                            fog_visible = self.grid_pos_is_active(new_fog_grid_pos)
                            if not fog_visible:
                                break

                self.squares_screen_space[world_grid_pos] = fog_visible

        for square in self.grid_canvases:
            if square.needs_update():
                square.free()


class GameWorld(cocos.cocosnode.CocosNode):
    def __init__(self):
        super(GameWorld, self).__init__()
        self.current_turn = 0


class GameLayer(cocos.layer.Layer):
    is_event_handler = True  #: enable director.window events

    def __init__(self):
        super(GameLayer, self).__init__()

        self.game_world = GameWorld()
        self.add(self.game_world)

        self.keys_pressed = set()
        self.player = PlayerNode(FRIEND)
        self.game_world.add(self.player)

        # Fog of war Node
        self.fow = FogOfWarNode(self.game_world, inverted=True, line_color=(50, 50, 50, 255))
        self.fow_visited = FogOfWarNode(self.game_world, inverted=True, line_color=(50, 50, 50, 128))

        # Full cover
        self.full_cover = ColoredGridNode(self.game_world, inverted=False, line_color=(128, 128, 128, 255),
                                          cache_size=64)

        # Half cover
        self.half_cover = ColoredGridNode(self.game_world, inverted=False, line_color=(50, 128, 50, 255), cache_size=64)

        # Enemies
        self.enemies = ColoredGridNode(self.game_world, inverted=False, line_color=(255, 108, 108, 255), cache_size=64)

        # Update camera
        self.update_camera()

        bg_path = os.path.abspath("../assets/grid.png")
        bg_img = pyglet.image.load(bg_path)
        bg = cocos.sprite.Sprite(bg_img, anchor=(0, 0))
        # self.add(bg)

        # Load obstacles from image
        # bg_texture_data = bg.image.get_image_data()

        full_cover_colors = [[145, 145, 145]]
        self.do_something_from_colors(full_cover_colors, bg, self.add_full_cover)

        half_cover_colors = [[133, 175, 133]]
        self.do_something_from_colors(half_cover_colors, bg, self.add_half_cover)

        enemy_colors = [[255, 0, 0]]
        self.do_something_from_colors(enemy_colors, bg, self.add_enemy)

        self.add(self.full_cover)
        self.add(self.half_cover)
        self.add(self.enemies)
        self.add(self.fow)
        self.add(self.fow_visited)

        self.fow.update_grid()
        self.fow_visited.update_grid()
        self.full_cover.update_grid()
        self.half_cover.update_grid()
        self.enemies.update_grid()

    def add_full_cover(self, position):
        self.full_cover.set_grid_pos_visible(world_to_grid(position), True)

    def add_half_cover(self, position):
        self.half_cover.set_grid_pos_visible(world_to_grid(position), True)

    def add_enemy(self, position):
        self.enemies.set_grid_pos_visible(world_to_grid(position), True)

    @staticmethod
    def do_something_from_colors(colors, sprite, callback):
        bg_texture_data = sprite.image.get_image_data()
        data = bg_texture_data.get_data('RGB', sprite.width * 3)
        for x in xrange(g_grid_size / 2, sprite.width, g_grid_size):
            for y in xrange(g_grid_size / 2, sprite.height, g_grid_size):
                pos = (sprite.width * y + x) * 3
                rgb = map(ord, data[pos:pos + 3])
                valid = False
                limit = 2
                for valid_color in colors:
                    if valid:
                        break
                    valid = True
                    for i in xrange(0, 3):
                        valid = valid and abs(valid_color[i] - rgb[i]) < limit

                if valid:
                    callback(position=(x, y))

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
                self.game_world.current_turn += 1
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
                                self.fow.set_grid_pos_visible(
                                    hit_pos,
                                    True,
                                    self.game_world.current_turn + g_steps_fog_stays_around)
                                self.fow_visited.set_grid_pos_visible(
                                    hit_pos,
                                    True,
                                    self.game_world.current_turn + g_steps_half_fog_stays_around)

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
                                            self.fow.set_grid_pos_visible(
                                                hit_pos,
                                                True,
                                                self.game_world.current_turn + g_steps_fog_stays_around)
                                            self.fow_visited.set_grid_pos_visible(
                                                hit_pos,
                                                True,
                                                self.game_world.current_turn + g_steps_half_fog_stays_around)
                                        elif not hit:
                                            break

                            if not hit:
                                self.fow.set_grid_pos_visible(
                                    new_pos + (x, y),
                                    True,
                                    self.game_world.current_turn + g_steps_fog_stays_around)
                                self.fow_visited.set_grid_pos_visible(
                                    new_pos + (x, y),
                                    True,
                                    self.game_world.current_turn + g_steps_half_fog_stays_around)

                self.update_camera()

    def update_camera(self):
        world_pos = self.game_world.point_to_world(self.player.position)
        win_size = director.get_window_size()
        padding = 96

        old_pos = self.game_world.position
        new_pos = old_pos

        if world_pos[0] < padding:
            new_pos += Point2(padding - world_pos[0], 0)
        elif (win_size[0] - world_pos[0]) < padding:
            new_pos -= Point2(padding - (win_size[0] - world_pos[0]), 0)
        if world_pos[1] < padding:
            new_pos += Point2(0, padding - world_pos[1])
        elif (win_size[1] - world_pos[1]) < padding:
            new_pos -= Point2(0, padding - (win_size[1] - world_pos[1]))

        if old_pos != new_pos:
            self.game_world.position = new_pos

            self.full_cover.update_grid()
            self.half_cover.update_grid()
            self.enemies.update_grid()

        self.fow.update_grid()
        self.fow_visited.update_grid()

    def is_valid_player_grid_pos(self, grid_pos):
        grid_pos = tuple(int(v) for v in grid_pos)
        return not self.full_cover.grid_pos_is_active(grid_pos) and not self.half_cover.grid_pos_is_active(grid_pos)

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
            if self.full_cover.grid_pos_is_active((x, y)) or \
                    (not ignore_half_cover and self.half_cover.grid_pos_is_active((x, y))):
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
    #director.show_FPS = True
    game_layer = GameLayer()
    director.run(cocos.scene.Scene(
        game_layer,
        DebugConsole()
    ))
