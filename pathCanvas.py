from cocos.draw import Canvas


class PathCanvas(Canvas):
    def __init__(self, path=[]):
        super(PathCanvas, self).__init__()
        self._path = []

    def set_path(self, path):
        self._path = path
        self.free()

    def render(self):
        path = self._path
        if len(path) == 0:
            return

        line_color = (255, 255, 255, 255)
        self.set_color(line_color)

        self.move_to(path[0])
        for point in path[1:]:
            self.line_to(point)
