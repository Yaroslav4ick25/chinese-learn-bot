import math
from PIL import Image, ImageDraw

SIZE = 512
RED = (222, 41, 16)
YELLOW = (255, 222, 0)

img = Image.new("RGB", (SIZE, SIZE), RED)
draw = ImageDraw.Draw(img)


def star(cx, cy, r_outer, r_inner, angle_offset):
    points = []
    for i in range(10):
        angle = math.radians(angle_offset + i * 36)
        r = r_outer if i % 2 == 0 else r_inner
        points.append((cx + r * math.sin(angle), cy - r * math.cos(angle)))
    return points


def angle_to(cx, cy, tx, ty):
    return math.degrees(math.atan2(tx - cx, -(ty - cy)))


# Большая звезда — примерно как на флаге КНР (левый верхний квадрант)
big_cx, big_cy, big_r = SIZE * 0.19, SIZE * 0.19, SIZE * 0.11
draw.polygon(star(big_cx, big_cy, big_r, big_r * 0.382, 0), fill=YELLOW)

# 4 маленькие звезды дугой справа от большой, каждая направлена вершиной на большую
small_positions = [
    (SIZE * 0.335, SIZE * 0.085),
    (SIZE * 0.385, SIZE * 0.165),
    (SIZE * 0.375, SIZE * 0.265),
    (SIZE * 0.315, SIZE * 0.345),
]
small_r = SIZE * 0.035
for sx, sy in small_positions:
    ang = angle_to(sx, sy, big_cx, big_cy)
    draw.polygon(star(sx, sy, small_r, small_r * 0.382, ang), fill=YELLOW)

img.save("avatar.png")
print("saved avatar.png")
