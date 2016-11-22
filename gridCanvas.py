from cocos.director import director
from cocos.draw import Canvas


class GridCanvas(Canvas):
    def __init__(self, grid_cell_size):
        super(GridCanvas, self).__init__()
        self._grid_cell_size = grid_cell_size

    def render(self):
        win_size = director.get_window_size()
        line_color = (50, 50, 50, 255)

        self.set_stroke_width(1)
        self.set_color(line_color)

        for x_pos in range(0, win_size[0], self._grid_cell_size):
            self.move_to((x_pos, 0))
            self.line_to((x_pos, win_size[1]))

        for y_pos in range(0, win_size[1], self._grid_cell_size):
            self.move_to((0, y_pos))
            self.line_to((win_size[0], y_pos))
