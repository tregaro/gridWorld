import os

import cocos
import pyglet
from cocos.batch import BatchNode
from cocos.euclid import Point2

director = cocos.director.director
g_player_size = 1
g_grid_size = 16


def world_to_grid(world_pos):
    return tuple(int(x // g_grid_size) for x in world_pos)


def grid_to_world(grid_pos):
    return grid_pos[0] * g_grid_size, grid_pos[1] * g_grid_size


def align_pos_to_grid(position):
    return grid_to_world(world_to_grid(position))


class PlayerNode(cocos.cocosnode.CocosNode):
    def __init__(self):
        super(PlayerNode, self).__init__()

        player_path = os.path.abspath('../assets/white.png')
        player_img = pyglet.image.load(player_path)
        player = cocos.sprite.Sprite(
            image=player_img,
            scale=g_grid_size,
            color=(108, 255, 108)
        )

        self.add(player)
        self.player = player


class GameLayer(cocos.layer.Layer):
    is_event_handler = True  #: enable director.window events

    def __init__(self):
        super(GameLayer, self).__init__()

        self.keys_pressed = set()
        self.player = PlayerNode()
        self.add(self.player)

        bg_path = os.path.abspath("../assets/grid.png")
        bg_img = pyglet.image.load(bg_path)
        bg = cocos.sprite.Sprite(bg_img, anchor=(0, 0))
        # self.add(bg)

        # Batched node to draw obstacles
        self.obstacles_batch_node = BatchNode()
        self.add(self.obstacles_batch_node)
        self.obstacle_squares = {}

        # Load obstacles from image
        bg_texture_data = bg.image.get_image_data()
        data = bg_texture_data.get_data('RGB', bg.width * 3)
        valid_colors = [
            [192, 192, 191],
            [102, 112, 102],
            [91, 91, 91],
            [168, 168, 168],
        ]

        for x in range(g_grid_size / 2, bg.width, g_grid_size):
            for y in range(g_grid_size / 2, bg.height, g_grid_size):
                pos = (bg.width * y + x) * 3
                rgb = map(ord, data[pos:pos + 3])
                valid = False
                limit = 2
                for valid_color in valid_colors:
                    if valid:
                        break
                    valid = True
                    for i in range(0, 3):
                        valid = valid and abs(valid_color[i] - rgb[i]) < limit

                if not valid:
                    self.set_grid_obstructed((x, y), True)

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

                world_pos = self.point_to_world(self.player.position)
                win_size = director.get_window_size()
                padding = 100
                if world_pos[0] < padding:
                    self.position += Point2(padding - world_pos[0], 0)
                elif (win_size[0] - world_pos[0]) < padding:
                    self.position -= Point2(padding - (win_size[0] - world_pos[0]), 0)
                if world_pos[1] < padding:
                    self.position += Point2(0, padding - world_pos[1])
                elif (win_size[1] - world_pos[1]) < padding:
                    self.position -= Point2(0, padding - (win_size[1] - world_pos[1]))

    def is_valid_player_grid_pos(self, grid_pos):
        grid_pos = tuple(int(v) for v in grid_pos)
        return grid_pos not in self.obstacle_squares

    def set_grid_obstructed(self, position, is_obstructed):
        grid_pos = world_to_grid(position)

        # Check if we don't need to do anything
        if grid_pos in self.obstacle_squares and is_obstructed:
            return

        if is_obstructed:
            obstacle_path = os.path.abspath('../assets/white.png')
            obstacle_img = pyglet.image.load(obstacle_path)
            obstacle = cocos.sprite.Sprite(
                image=obstacle_img,
                scale=g_grid_size,
                color=(128, 128, 128)
            )
            obstacle.position = grid_to_world(grid_pos)
            self.obstacles_batch_node.add(obstacle)
            self.obstacle_squares[grid_pos] = obstacle
        else:
            current_obstacle = self.obstacle_squares.get(grid_pos, None)
            self.obstacles_batch_node.remove(current_obstacle)
            del self.obstacle_squares[grid_pos]


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
        width=1036,
        height=510
    )

    director.run(cocos.scene.Scene(
        GameLayer(),
        DebugConsole()
    ))
