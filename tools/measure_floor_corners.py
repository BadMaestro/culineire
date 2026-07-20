"""The eight corners of the arena floor as drawn in a backdrop image.

This is the instrument the backdrop is accepted with: it finds the painted
floor in a generated hall and returns its eight corners as fractions of the
image, so they can be compared against the eight corners our SVG puts on the
screen. Acceptance is every corner within 2% of the image width — not because a
seam would show, but because the floor is clickable: if the grid and the picture
disagree, a visitor taps one seat and a different one lights up.

It lived in /tmp on the server, owned by root, while it was the only way to
reproduce that acceptance. A machine restart would have taken it, and with it
the ability to check anyone's work on the arena.

Usage:
    sudo -u deploy /srv/culineire/venv/bin/python tools/measure_floor_corners.py <image>

Reports the threshold it chose, the centre, and eight corners. Print all eight;
never report their mean. A mean hides one corner that has walked off on its own,
which is exactly the failure this is looking for.

The floor is found by Otsu's threshold over the image's own histogram rather
than a number picked by eye: an earlier detector took the brightest patch in the
middle of the floor for the whole floor and reported 0.348 where the truth was
0.602, and that wrong number was believed for a while.
"""

import math
import sys
from collections import deque

from PIL import Image


def otsu_threshold(image):
    """Split the histogram where it separates best — no hand-picked constant."""
    hist = image.histogram()
    width, height = image.size
    total = width * height
    sum_all = sum(i * hist[i] for i in range(256))
    sum_background = weight_background = 0
    best_variance, threshold = -1.0, 128
    for level in range(256):
        weight_background += hist[level]
        if weight_background == 0:
            continue
        weight_foreground = total - weight_background
        if weight_foreground == 0:
            break
        sum_background += level * hist[level]
        mean_background = sum_background / weight_background
        mean_foreground = (sum_all - sum_background) / weight_foreground
        variance = (
            weight_background
            * weight_foreground
            * (mean_background - mean_foreground) ** 2
        )
        if variance > best_variance:
            best_variance, threshold = variance, level
    return threshold


def largest_bright_region(image, threshold):
    """The floor is the biggest bright blob — the stands around it are dark."""
    width, height = image.size
    pixels = image.load()
    seen = [[False] * width for _ in range(height)]
    region = []
    # Seeds on a coarse grid: the floor is far larger than the step, so it is
    # never missed, and this keeps the scan cheap on a 1024px frame.
    for seed_y in range(0, height, 2):
        for seed_x in range(0, width, 2):
            if pixels[seed_x, seed_y] <= threshold or seen[seed_y][seed_x]:
                continue
            queue = deque([(seed_x, seed_y)])
            seen[seed_y][seed_x] = True
            blob = []
            while queue:
                x, y = queue.popleft()
                blob.append((x, y))
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if (
                        0 <= nx < width
                        and 0 <= ny < height
                        and not seen[ny][nx]
                        and pixels[nx, ny] > threshold
                    ):
                        seen[ny][nx] = True
                        queue.append((nx, ny))
            if len(blob) > len(region):
                region = blob
    return region


def convex_hull(points):
    ordered = sorted(set(points))

    def half(sequence):
        out = []
        for point in sequence:
            while len(out) >= 2:
                (x1, y1), (x2, y2) = out[-2], out[-1]
                cross = (x2 - x1) * (point[1] - y1) - (y2 - y1) * (point[0] - x1)
                if cross <= 0:
                    out.pop()
                else:
                    break
            out.append(point)
        return out

    return half(ordered)[:-1] + half(ordered[::-1])[:-1]


def polygon_area(polygon):
    total = 0.0
    for i in range(len(polygon)):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % len(polygon)]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def reduce_to_eight(hull):
    """Drop the vertex whose removal costs the least area, until eight remain.

    A generated edge is soft, so the hull comes back with dozens of vertices
    strung along each side. The ones that matter are the corners: removing a
    corner changes the area a lot, removing a point mid-edge changes it barely.
    """
    polygon = list(hull)
    while len(polygon) > 8:
        losses = []
        for i in range(len(polygon)):
            trial = polygon[:i] + polygon[i + 1:]
            losses.append((polygon_area(polygon) - polygon_area(trial), i))
        losses.sort()
        polygon.pop(losses[0][1])
    return polygon


def main(path):
    image = Image.open(path).convert("L")
    width, height = image.size
    threshold = otsu_threshold(image)
    region = largest_bright_region(image, threshold)
    if not region:
        raise SystemExit("no bright region found — is this a hall image?")
    hull = convex_hull(region)
    corners = reduce_to_eight(hull)

    cx = sum(p[0] for p in corners) / 8.0
    cy = sum(p[1] for p in corners) / 8.0
    corners.sort(key=lambda p: math.atan2(p[1] - cy, p[0] - cx))

    print("threshold %d | hull %d -> 8 | centre %.4f %.4f"
          % (threshold, len(hull), cx / width, cy / height))
    for i, (x, y) in enumerate(corners, 1):
        print("CORNER %d  %.4f  %.4f" % (i, x / float(width), y / float(height)))

    # Edge lengths say whether the drawn shape is a regular octagon at all.
    # A regular one has every edge at 0.414 of its width, from any viewpoint.
    # Report all eight: frame 3 averages 0.409, which looks like a hit, while
    # its shortest and longest edges are 23% apart.
    span_x = (max(p[0] for p in corners) - min(p[0] for p in corners)) / width
    span_y = (max(p[1] for p in corners) - min(p[1] for p in corners)) / height
    edges = []
    for i in range(8):
        x1, y1 = corners[i]
        x2, y2 = corners[(i + 1) % 8]
        edges.append(math.hypot((x2 - x1) / width, (y2 - y1) / height))
    print("width %.4f height %.4f h/w %.4f" % (span_x, span_y, span_y / span_x))
    print("edge/width " + " ".join("%.3f" % (e / span_x) for e in edges))
    print("edge spread %.1f%% (regular octagon: every edge 0.414, spread 0)"
          % (100.0 * (max(edges) - min(edges)) / max(edges)))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
