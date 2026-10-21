bl_info = {
    "name": "Topographic Art Generator",
    "author": "Aporrhia",
    "version": (1, 0, 0),
    "blender": (5, 2, 0),
    "location": "View3D > Sidebar > Topo",
    "description": "Generate topographic terrain artwork in several styles",
    "category": "Add Mesh",
}

import bmesh
import bpy
import math
import random
from mathutils import Vector
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
)
from bpy.types import (
    Operator,
    Panel,
    PropertyGroup,
)


# ============================================================
# CONSTANTS
# ============================================================

COLLECTION_NAME = "Topographic Art"
ROOT_NAME = "Topo Root"
TERRAIN_NAME = "Topo Terrain"
BASE_NAME = "Topo Base"
GRID_NAME = "Topo Grid"
CONTOUR_PREFIX = "Topo Contour"
CAMERA_NAME = "Topo Camera"

MATERIAL_SURFACE = "Topo Surface"
MATERIAL_CONTOUR = "Topo Contour Material"
MATERIAL_GRID = "Topo Grid Material"
MATERIAL_BASE = "Topo Base Material"
MATERIAL_SIDES = "Topo Side Material"

LAYER_MATERIAL_PREFIX = "Topo Layer"
LINE_MATERIAL_PREFIX = "Topo Line"

STYLE_SMOOTH = "SMOOTH"
STYLE_STEPS = "STEPS"
STYLE_COLORED = "COLORED"
STYLE_ISLANDS = "ISLANDS"
STYLE_WIREFRAME = "WIREFRAME"
STYLE_HOLLOW = "HOLLOW"

STEPPED_STYLES = {STYLE_STEPS, STYLE_COLORED, STYLE_ISLANDS}

DEFAULT_GRADIENT = [
    (0.02, 0.10, 0.35),
    (0.00, 0.45, 0.60),
    (0.15, 0.65, 0.30),
    (0.95, 0.90, 0.15),
]

STYLE_ITEMS = [
    (STYLE_SMOOTH, "Smooth Surface",
     "Smooth terrain with contour lines on top"),
    (STYLE_STEPS, "Steps",
     "Stacked terraces, like a layered paper model"),
    (STYLE_COLORED, "Colored Steps",
     "Terraces coloured by height with your own gradient"),
    (STYLE_ISLANDS, "Islands (Hills Only)",
     "Terraced hills that fade out before the block edges, "
     "so no hill is cut off"),
    (STYLE_WIREFRAME, "Wireframe",
     "Dark surface with glowing contour and grid lines"),
    (STYLE_HOLLOW, "Hollow",
     "Only lines, no surface"),
]

LINE_COLOR_ITEMS = [
    ("SOLID", "Solid", "One colour for all lines"),
    ("GRADIENT", "By Height", "Colour each contour line from the gradient"),
]

_LIGHT_BG = (0.55, 0.55, 0.56)
_DARK_BG = (0.004, 0.012, 0.016)

STYLE_PRESETS = {
    STYLE_SMOOTH: dict(
        surface_color=(0.80, 0.78, 0.68),
        side_color=(0.25, 0.25, 0.24),
        base_color=(0.12, 0.12, 0.13),
        contour_color=(0.08, 0.08, 0.07),
        show_contours=True,
        show_base_plate=True,
        line_glow=False,
        line_color_mode="SOLID",
        grid_line_count=0,
        step_bevel=0.0,
        set_background=False,
        background_color=_LIGHT_BG,
    ),
    STYLE_STEPS: dict(
        surface_color=(0.92, 0.92, 0.90),
        side_color=(0.88, 0.88, 0.86),
        base_color=(0.80, 0.80, 0.80),
        contour_color=(0.30, 0.30, 0.30),
        show_contours=False,
        show_base_plate=True,
        line_glow=False,
        line_color_mode="SOLID",
        grid_line_count=0,
        step_bevel=0.03,
        set_background=True,
        background_color=_LIGHT_BG,
    ),
    STYLE_COLORED: dict(
        surface_color=(0.92, 0.92, 0.90),
        side_color=(0.05, 0.05, 0.06),
        base_color=(0.05, 0.05, 0.06),
        contour_color=(0.05, 0.05, 0.05),
        show_contours=False,
        show_base_plate=True,
        line_glow=False,
        line_color_mode="SOLID",
        grid_line_count=0,
        step_bevel=0.03,
        set_background=True,
        background_color=_LIGHT_BG,
    ),
    STYLE_ISLANDS: dict(
        surface_color=(0.93, 0.93, 0.92),
        side_color=(0.90, 0.90, 0.88),
        base_color=(0.85, 0.85, 0.84),
        contour_color=(0.30, 0.30, 0.30),
        show_contours=False,
        show_base_plate=True,
        line_glow=False,
        line_color_mode="SOLID",
        grid_line_count=0,
        step_bevel=0.03,
        set_background=True,
        background_color=_LIGHT_BG,
    ),
    STYLE_WIREFRAME: dict(
        surface_color=(0.008, 0.03, 0.035),
        side_color=(0.008, 0.025, 0.03),
        base_color=(0.01, 0.02, 0.025),
        contour_color=(0.0, 0.9, 0.8),
        grid_color=(0.05, 0.45, 0.5),
        show_contours=True,
        show_base_plate=True,
        line_glow=True,
        glow_strength=6.0,
        line_color_mode="SOLID",
        grid_line_count=24,
        step_bevel=0.0,
        set_background=True,
        background_color=_DARK_BG,
    ),
    STYLE_HOLLOW: dict(
        surface_color=(0.008, 0.03, 0.035),
        side_color=(0.008, 0.025, 0.03),
        base_color=(0.01, 0.02, 0.025),
        contour_color=(0.0, 0.9, 0.8),
        grid_color=(0.05, 0.45, 0.5),
        show_contours=True,
        show_base_plate=False,
        line_glow=True,
        glow_strength=6.0,
        line_color_mode="SOLID",
        grid_line_count=24,
        step_bevel=0.0,
        set_background=True,
        background_color=_DARK_BG,
    ),
}


# ============================================================
# MATERIALS
# ============================================================

def ensure_nodes(mat):
    """Make sure a material has a node tree; return its Principled BSDF."""

    try:
        if not mat.use_nodes:
            mat.use_nodes = True
    except Exception:
        pass

    if mat.node_tree is None:
        return None

    return mat.node_tree.nodes.get("Principled BSDF")


def set_socket(node, names, value):
    for name in names:
        socket = node.inputs.get(name)

        if socket is not None:
            socket.default_value = value
            return


def get_or_create_material(name, color, roughness=0.8, emission=0.0):
    """Create a material or update an existing one."""

    mat = bpy.data.materials.get(name)

    if mat is None:
        mat = bpy.data.materials.new(name=name)

    rgba = (color[0], color[1], color[2], 1.0)
    mat.diffuse_color = rgba

    bsdf = ensure_nodes(mat)

    if bsdf:
        set_socket(bsdf, ("Base Color",), rgba)
        set_socket(bsdf, ("Roughness",), roughness)
        set_socket(bsdf, ("Emission Color", "Emission"), rgba)
        set_socket(
            bsdf,
            ("Emission Strength",),
            emission if emission > 0.0 else 0.0,
        )

    return mat


def line_emission(settings, scale=1.0):
    if settings.line_glow:
        return settings.glow_strength * scale

    return 0.0


def update_materials(settings):
    """Update the shared materials from the UI settings."""

    get_or_create_material(
        MATERIAL_SURFACE, settings.surface_color, settings.surface_roughness
    )
    get_or_create_material(
        MATERIAL_CONTOUR, settings.contour_color, 0.5,
        line_emission(settings),
    )
    get_or_create_material(
        MATERIAL_GRID, settings.grid_color, 0.5,
        line_emission(settings, 0.5),
    )
    get_or_create_material(MATERIAL_BASE, settings.base_color, 0.7)
    get_or_create_material(MATERIAL_SIDES, settings.side_color, 0.85)


def update_world(settings, scene):
    if not settings.set_background:
        return

    world = scene.world

    if world is None:
        world = bpy.data.worlds.new("Topo World")
        scene.world = world

    try:
        if not world.use_nodes:
            world.use_nodes = True
    except Exception:
        pass

    if world.node_tree is None:
        return

    background = world.node_tree.nodes.get("Background")

    if background:
        color = settings.background_color
        background.inputs["Color"].default_value = (
            color[0], color[1], color[2], 1.0
        )
        background.inputs["Strength"].default_value = 1.0


# ============================================================
# GRADIENT
# ============================================================

def gradient_colors(settings):
    colors = [tuple(stop.color) for stop in settings.gradient]

    if len(colors) < 2:
        colors = list(DEFAULT_GRADIENT)

    return colors


def sample_gradient(colors, t):
    t = max(0.0, min(1.0, t))
    scaled = t * (len(colors) - 1)
    index = min(int(scaled), len(colors) - 2)
    fraction = scaled - index

    a = colors[index]
    b = colors[index + 1]

    return tuple(a[c] + (b[c] - a[c]) * fraction for c in range(3))


def reset_gradient(settings):
    settings.gradient.clear()

    for color in DEFAULT_GRADIENT:
        item = settings.gradient.add()
        item.color = color


def use_layer_colors(settings):
    return settings.style == STYLE_COLORED or (
        settings.style == STYLE_ISLANDS and settings.color_by_height
    )


def layer_material(settings, colors, k, n):
    t = k / n if n > 0 else 0.0
    return get_or_create_material(
        f"{LAYER_MATERIAL_PREFIX} {k:03d}",
        sample_gradient(colors, t),
        0.75,
    )


def contour_material(settings, colors, k, n):
    """Material for contour line k (1..n)."""

    if settings.line_color_mode == "GRADIENT":
        t = (k - 1) / (n - 1) if n > 1 else 0.5

        return get_or_create_material(
            f"{LINE_MATERIAL_PREFIX} {k:03d}",
            sample_gradient(colors, t),
            0.5,
            line_emission(settings),
        )

    return bpy.data.materials.get(MATERIAL_CONTOUR)


# ============================================================
# STYLE PRESETS
# ============================================================

def apply_style_preset(settings):
    preset = STYLE_PRESETS.get(settings.style)

    if preset:
        for key, value in preset.items():
            setattr(settings, key, value)

    if len(settings.gradient) < 2:
        reset_gradient(settings)


def on_style_update(self, context):
    apply_style_preset(self)


# ============================================================
# COLLECTION / OBJECT MANAGEMENT
# ============================================================

def get_or_create_collection(scene):
    collection = bpy.data.collections.get(COLLECTION_NAME)

    if collection is None:
        collection = bpy.data.collections.new(COLLECTION_NAME)
        scene.collection.children.link(collection)

    elif collection.name not in [
        child.name for child in scene.collection.children
    ]:
        scene.collection.children.link(collection)

    return collection


def get_saved_topo_transform():
    """Return the previous artwork transform before regeneration."""

    root = bpy.data.objects.get(ROOT_NAME)

    if root is not None:
        return (
            root.location.copy(),
            root.rotation_euler.copy(),
            root.scale.copy(),
        )

    terrain = bpy.data.objects.get(TERRAIN_NAME)

    if terrain is not None:
        return (
            terrain.location.copy(),
            terrain.rotation_euler.copy(),
            terrain.scale.copy(),
        )

    return (
        Vector((0.0, 0.0, 0.0)),
        Vector((0.0, 0.0, 0.0)),
        Vector((1.0, 1.0, 1.0)),
    )


def remove_object_and_data(obj):
    data = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)

    if data is None or data.users != 0:
        return

    if isinstance(data, bpy.types.Mesh):
        bpy.data.meshes.remove(data)
    elif isinstance(data, bpy.types.Curve):
        bpy.data.curves.remove(data)
    elif isinstance(data, bpy.types.Camera):
        bpy.data.cameras.remove(data)
    elif isinstance(data, bpy.types.Light):
        bpy.data.lights.remove(data)


def clear_generated_collection(scene):
    """Remove previously generated objects and their leftover data."""

    collection = bpy.data.collections.get(COLLECTION_NAME)

    if collection is None:
        return

    if scene.camera and scene.camera.name in collection.objects:
        scene.camera = None

    for obj in list(collection.objects):
        remove_object_and_data(obj)

    for mat in list(bpy.data.materials):
        if mat.users == 0 and mat.name.startswith(
            (LAYER_MATERIAL_PREFIX, LINE_MATERIAL_PREFIX)
        ):
            bpy.data.materials.remove(mat)


def parent_generated_objects(collection, location, rotation, scale):
    """Parent generated objects to a common root."""

    root = bpy.data.objects.new(ROOT_NAME, None)
    collection.objects.link(root)

    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 1.0

    root.location = location
    root.rotation_euler = rotation
    root.scale = scale

    for obj in list(collection.objects):
        if obj == root:
            continue

        obj.parent = root
        obj.matrix_parent_inverse.identity()

    return root


# ============================================================
# SEEDED NATURAL TERRAIN NOISE
# ============================================================

def smooth_noise_fade(t):
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def hash_lattice(ix, iy, seed):
    """Deterministic pseudo-random value for an integer grid point."""

    value = (
        ix * 374761393
        + iy * 668265263
        + seed * 1442695041
    ) & 0xFFFFFFFF

    value = ((value ^ (value >> 13)) * 1274126177) & 0xFFFFFFFF
    value ^= value >> 16

    return (value / 4294967295.0) * 2.0 - 1.0


def value_noise_2d(x, y, seed):
    x0 = math.floor(x)
    y0 = math.floor(y)

    tx = smooth_noise_fade(x - x0)
    ty = smooth_noise_fade(y - y0)

    a = hash_lattice(x0, y0, seed)
    b = hash_lattice(x0 + 1, y0, seed)
    c = hash_lattice(x0, y0 + 1, seed)
    d = hash_lattice(x0 + 1, y0 + 1, seed)

    lower = a + (b - a) * tx
    upper = c + (d - c) * tx

    return lower + (upper - lower) * ty


def terrain_raw_height(nx, ny, seed, octaves, offset_x, offset_y):
    """Multi-scale terrain value for normalized coordinates 0..1."""

    x = nx * 3.0 + offset_x
    y = ny * 3.0 + offset_y

    total = 0.0
    amplitude = 1.0
    amplitude_sum = 0.0

    for octave in range(octaves):
        frequency = 2.0 ** octave

        total += value_noise_2d(
            x * frequency,
            y * frequency,
            seed + octave * 7919,
        ) * amplitude

        amplitude_sum += amplitude
        amplitude *= 0.45

    return total / amplitude_sum if amplitude_sum > 0 else 0.0


def smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def generate_height_grid(settings):
    """Create the terrain height grid (rows are Y, columns are X)."""

    resolution = settings.resolution
    height = settings.height
    seed = settings.seed
    octaves = max(1, min(settings.complexity, 8))

    rng = random.Random(seed)
    offset_x = rng.uniform(-1000.0, 1000.0)
    offset_y = rng.uniform(-1000.0, 1000.0)

    raw = []

    for j in range(resolution + 1):
        row = []

        for i in range(resolution + 1):
            row.append(
                terrain_raw_height(
                    i / resolution,
                    j / resolution,
                    seed,
                    octaves,
                    offset_x,
                    offset_y,
                )
            )

        raw.append(row)

    low = min(min(row) for row in raw)
    high = max(max(row) for row in raw)
    span = high - low

    values = [
        [
            (v - low) / span if span > 1e-8 else 0.5
            for v in row
        ]
        for row in raw
    ]

    if settings.style == STYLE_ISLANDS:
        values = apply_island_shape(settings, values)

    return [[v * height for v in row] for row in values]


def apply_island_shape(settings, values):
    """
    Fade the terrain to zero near the block edges and cut off the
    low ground, so only closed hills remain.
    """

    resolution = settings.resolution
    falloff = max(0.01, settings.island_edge_falloff)
    sea = settings.island_sea_level

    shaped = []
    peak = 0.0

    for j in range(resolution + 1):
        row = []
        ny = j / resolution

        for i in range(resolution + 1):
            nx = i / resolution

            edge_distance = min(nx, 1.0 - nx, ny, 1.0 - ny)
            mask = smoothstep(edge_distance / falloff)

            value = max(0.0, values[j][i] * mask - sea)
            peak = max(peak, value)
            row.append(value)

        shaped.append(row)

    if peak > 1e-8:
        shaped = [[v / peak for v in row] for row in shaped]

    return shaped


# ============================================================
# GRID HELPER
# ============================================================

class Grid:
    """Plain-Python snapshot of the terrain grid for fast loops."""

    def __init__(self, settings, heights):
        self.res = settings.resolution
        self.width = settings.width
        self.depth = settings.depth
        self.heights = heights

    def xy(self, i, j):
        return (
            (i / self.res - 0.5) * self.width,
            (j / self.res - 0.5) * self.depth,
        )

    def point(self, pid, level):
        """
        XY position of a grid point id.

        ("c", i, j): grid corner
        ("h", i, j): crossing on the edge (i, j) -> (i + 1, j)
        ("v", i, j): crossing on the edge (i, j) -> (i, j + 1)
        """

        kind, i, j = pid

        if kind == "c":
            return self.xy(i, j)

        if kind == "h":
            bi, bj = i + 1, j
        else:
            bi, bj = i, j + 1

        ha = self.heights[j][i]
        hb = self.heights[bj][bi]
        difference = hb - ha

        if abs(difference) < 1e-12:
            t = 0.5
        else:
            t = max(0.0, min(1.0, (level - ha) / difference))

        ax, ay = self.xy(i, j)
        bx, by = self.xy(bi, bj)

        return (ax + (bx - ax) * t, ay + (by - ay) * t)


# ============================================================
# REGION / CONTOUR GEOMETRY (MARCHING SQUARES)
# ============================================================

def cell_region_polygons(i, j, hs, level):
    """
    Polygons covering the part of a grid cell where height >= level.

    hs = (h00, h10, h11, h01), corners in counter-clockwise order.
    Each polygon is a list of (point_id, kind) in counter-clockwise
    order. kind describes the segment from this point to the next:
        0..3 = it runs along that cell edge
        -1   = it is a contour chord through the cell
    """

    inside = [h >= level for h in hs]
    count = sum(inside)

    if count == 0:
        return []

    corners = [
        ("c", i, j),
        ("c", i + 1, j),
        ("c", i + 1, j + 1),
        ("c", i, j + 1),
    ]

    edges = [
        ("h", i, j),
        ("v", i + 1, j),
        ("h", i, j + 1),
        ("v", i, j),
    ]

    if count == 4:
        return [[(corners[e], e) for e in range(4)]]

    saddle = count == 2 and inside[0] == inside[2]

    if saddle and sum(hs) / 4.0 < level:
        polygons = []

        for c in range(4):
            if inside[c]:
                previous = (c - 1) % 4
                polygons.append([
                    (corners[c], c),
                    (edges[c], -1),
                    (edges[previous], previous),
                ])

        return polygons

    polygon = []

    for c in range(4):
        a = inside[c]
        b = inside[(c + 1) % 4]

        if a:
            polygon.append((corners[c], c))

        if a != b:
            polygon.append((edges[c], -1 if a else c))

    return [polygon]


def trace_chains(segments):
    """
    Join point-id pairs into continuous polylines.

    Returns a list of (path, closed).
    """

    adjacency = {}

    for a, b in segments:
        if a == b:
            continue

        adjacency.setdefault(a, []).append(b)
        adjacency.setdefault(b, []).append(a)

    used = set()

    def edge_key(a, b):
        return (a, b) if a < b else (b, a)

    def walk(start):
        path = [start]
        current = start

        while True:
            following = None

            for candidate in adjacency[current]:
                if edge_key(current, candidate) not in used:
                    following = candidate
                    break

            if following is None:
                break

            used.add(edge_key(current, following))
            path.append(following)
            current = following

        return path

    chains = []

    # Open lines start at nodes with a single neighbour.
    for node, neighbours in adjacency.items():
        if len(neighbours) == 1:
            path = walk(node)

            if len(path) > 1:
                chains.append((path, False))

    # Whatever is left forms closed loops.
    for node in adjacency:
        path = walk(node)

        if len(path) < 2:
            continue

        if path[0] == path[-1]:
            path = path[:-1]

            if len(path) >= 3:
                chains.append((path, True))
        else:
            chains.append((path, False))

    return chains


def smooth_polyline(points, closed, passes):
    """Light smoothing that removes the faceted look of grid contours."""

    for _ in range(passes):
        count = len(points)

        if count < 3:
            break

        result = []

        for index in range(count):
            if not closed and (index == 0 or index == count - 1):
                result.append(points[index])
                continue

            p = points[index - 1]
            q = points[index]
            r = points[(index + 1) % count]

            result.append((
                (p[0] + 2.0 * q[0] + r[0]) * 0.25,
                (p[1] + 2.0 * q[1] + r[1]) * 0.25,
            ))

        points = result

    return points


def build_contour_chains(grid, level, z, smoothing):
    """Continuous contour polylines for one level."""

    heights = grid.heights
    segments = []

    for j in range(grid.res):
        row0 = heights[j]
        row1 = heights[j + 1]

        for i in range(grid.res):
            hs = (row0[i], row0[i + 1], row1[i + 1], row1[i])

            if max(hs) < level or min(hs) >= level:
                continue

            for polygon in cell_region_polygons(i, j, hs, level):
                count = len(polygon)

                for index, (pid, kind) in enumerate(polygon):
                    if kind == -1:
                        segments.append(
                            (pid, polygon[(index + 1) % count][0])
                        )

    result = []

    for path, closed in trace_chains(segments):
        points = [grid.point(pid, level) for pid in path]
        points = smooth_polyline(points, closed, smoothing)
        result.append(([(x, y, z) for x, y in points], closed))

    return result


# ============================================================
# TERRAIN MESHES
# ============================================================

def finish_materials(mesh, materials):
    for mat in materials:
        mesh.materials.append(mat)


def create_smooth_terrain_mesh(settings, collection, grid):
    """Closed terrain mesh: smooth top, flat side walls."""

    res = grid.res
    heights = grid.heights
    row_size = res + 1

    verts = []
    faces = []
    face_materials = []

    for j in range(row_size):
        for i in range(row_size):
            x, y = grid.xy(i, j)
            verts.append((x, y, heights[j][i]))

    for j in range(res):
        for i in range(res):
            a = j * row_size + i
            faces.append((a, a + 1, a + row_size + 1, a + row_size))
            face_materials.append(0)

    perimeter = []

    for i in range(row_size):
        perimeter.append(i)

    for j in range(1, row_size):
        perimeter.append(j * row_size + res)

    for i in range(res - 1, -1, -1):
        perimeter.append(res * row_size + i)

    for j in range(res - 1, 0, -1):
        perimeter.append(j * row_size)

    bottom_z = -settings.base_thickness
    count = len(perimeter)

    wall_top = []
    wall_bottom = []

    for top_index in perimeter:
        x, y, z = verts[top_index]

        wall_top.append(len(verts))
        verts.append((x, y, z))

        wall_bottom.append(len(verts))
        verts.append((x, y, bottom_z))

    for k in range(count):
        n = (k + 1) % count

        faces.append((
            wall_top[k], wall_bottom[k], wall_bottom[n], wall_top[n]
        ))
        face_materials.append(1)

    bottom_face = []

    for top_index in perimeter:
        x, y, _z = verts[top_index]
        bottom_face.append(len(verts))
        verts.append((x, y, bottom_z))

    faces.append(tuple(reversed(bottom_face)))
    face_materials.append(1)

    mesh = bpy.data.meshes.new("Topo Terrain Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()

    finish_materials(mesh, [
        bpy.data.materials.get(MATERIAL_SURFACE),
        bpy.data.materials.get(MATERIAL_SIDES),
    ])

    for polygon, index in zip(mesh.polygons, face_materials):
        polygon.material_index = index
        polygon.use_smooth = index == 0

    obj = bpy.data.objects.new(TERRAIN_NAME, mesh)
    collection.objects.link(obj)

    return obj


def is_perimeter_edge(kind, i, j, res):
    return (
        (kind == 0 and j == 0)
        or (kind == 1 and i == res - 1)
        or (kind == 2 and j == res - 1)
        or (kind == 3 and i == 0)
    )


def create_stepped_mesh(settings, collection, grid, colors):
    """
    Terraced terrain.

    Layer k covers every place where height >= levels[k]; its top face
    sits at levels[k]. Walls follow the exact contour lines, so edges
    are smooth curves rather than grid-aligned blocks.
    """

    res = grid.res
    n = settings.contour_count
    step = settings.height / (n + 1)
    levels = [step * k for k in range(n + 1)]
    bottom = -settings.base_thickness
    layered = use_layer_colors(settings)

    verts = []
    faces = []
    face_materials = []
    cache = {}

    def layer_z(layer):
        return bottom if layer < 0 else levels[layer]

    def vert(pid, k, layer):
        key = (pid, -1 if pid[0] == "c" else k, layer)
        index = cache.get(key)

        if index is None:
            x, y = grid.point(pid, levels[k])
            index = len(verts)
            verts.append((x, y, layer_z(layer)))
            cache[key] = index

        return index

    heights = grid.heights

    for k in range(n + 1):
        level = levels[k]
        next_level = levels[k + 1] if k < n else None

        top_mat = k if layered else 0
        contour_wall_mat = k if layered else 0
        edge_wall_mat = k if layered else 1

        for j in range(res):
            row0 = heights[j]
            row1 = heights[j + 1]

            for i in range(res):
                hs = (row0[i], row0[i + 1], row1[i + 1], row1[i])

                if max(hs) < level:
                    continue

                on_edge = i == 0 or j == 0 or i == res - 1 or j == res - 1
                covered = next_level is not None and min(hs) >= next_level

                # Fully hidden by the layer above and not on the border.
                if covered and not on_edge:
                    continue

                for polygon in cell_region_polygons(i, j, hs, level):
                    if not covered:
                        faces.append(tuple(
                            vert(pid, k, k) for pid, _kind in polygon
                        ))
                        face_materials.append(top_mat)

                    count = len(polygon)

                    for index in range(count):
                        pid_a, kind = polygon[index]

                        if kind == -1:
                            wall_mat = contour_wall_mat
                        elif is_perimeter_edge(kind, i, j, res):
                            wall_mat = edge_wall_mat
                        else:
                            continue

                        pid_b = polygon[(index + 1) % count][0]

                        faces.append((
                            vert(pid_a, k, k),
                            vert(pid_a, k, k - 1),
                            vert(pid_b, k, k - 1),
                            vert(pid_b, k, k),
                        ))
                        face_materials.append(wall_mat)

    bottom_corners = [
        vert(("c", cx, cy), 0, -1)
        for cx, cy in ((0, 0), (res, 0), (res, res), (0, res))
    ]

    faces.append(tuple(reversed(bottom_corners)))
    face_materials.append(n + 1 if layered else 1)

    mesh = bpy.data.meshes.new("Topo Terrain Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()

    if layered:
        materials = [
            layer_material(settings, colors, k, n) for k in range(n + 1)
        ]
        materials.append(bpy.data.materials.get(MATERIAL_SIDES))
    else:
        materials = [
            bpy.data.materials.get(MATERIAL_SURFACE),
            bpy.data.materials.get(MATERIAL_SIDES),
        ]

    finish_materials(mesh, materials)

    for polygon, index in zip(mesh.polygons, face_materials):
        polygon.material_index = index

    # Smooth walls, crisp terrace edges.
    try:
        mesh.shade_smooth()
        mesh.set_sharp_from_angle(angle=math.radians(40.0))
    except Exception:
        pass

    obj = bpy.data.objects.new(TERRAIN_NAME, mesh)
    collection.objects.link(obj)

    bevel_width = min(settings.step_bevel, step * 0.4)

    if bevel_width > 1e-5:
        bevel = obj.modifiers.new("Topo Step Bevel", "BEVEL")
        bevel.width = bevel_width
        bevel.segments = 3
        bevel.limit_method = "ANGLE"
        bevel.angle_limit = math.radians(50.0)

    return obj


# ============================================================
# LINES (CONTINUOUS CURVES)
# ============================================================

def create_curve_object(name, chains, thickness, material, collection):
    """One curve object; every chain is a single continuous spline."""

    chains = [
        (points, closed)
        for points, closed in chains
        if len(points) >= (3 if closed else 2)
    ]

    if not chains:
        return None

    curve = bpy.data.curves.new(f"{name} Curve", type="CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = thickness
    curve.bevel_resolution = 3
    curve.use_fill_caps = True

    for points, closed in chains:
        spline = curve.splines.new("POLY")
        spline.points.add(len(points) - 1)

        for point, (x, y, z) in zip(spline.points, points):
            point.co = (x, y, z, 1.0)

        spline.use_cyclic_u = closed

    obj = bpy.data.objects.new(name, curve)
    collection.objects.link(obj)

    if material:
        curve.materials.append(material)

    return obj


def create_contour_objects(settings, collection, grid, colors):
    n = settings.contour_count
    step = settings.height / (n + 1)
    thickness = settings.contour_thickness

    for k in range(1, n + 1):
        level = step * k

        chains = build_contour_chains(
            grid,
            level,
            level + thickness * 0.3,
            settings.line_smoothing,
        )

        create_curve_object(
            f"{CONTOUR_PREFIX} {k:02d}",
            chains,
            thickness,
            contour_material(settings, colors, k, n),
            collection,
        )


def create_grid_lines(settings, collection, grid):
    """Evenly spaced lines across the terrain (wireframe look)."""

    count = settings.grid_line_count

    if count <= 0:
        return

    res = grid.res
    heights = grid.heights
    step = max(1, res // count)

    indices = list(range(0, res + 1, step))

    if indices[-1] != res:
        indices.append(res)

    lift = settings.contour_thickness * 0.3
    chains = []

    for j in indices:
        points = []

        for i in range(res + 1):
            x, y = grid.xy(i, j)
            points.append((x, y, heights[j][i] + lift))

        chains.append((points, False))

    for i in indices:
        points = []

        for j in range(res + 1):
            x, y = grid.xy(i, j)
            points.append((x, y, heights[j][i] + lift))

        chains.append((points, False))

    create_curve_object(
        GRID_NAME,
        chains,
        settings.contour_thickness * 0.4,
        bpy.data.materials.get(MATERIAL_GRID),
        collection,
    )


# ============================================================
# BASE PLATE
# ============================================================

def create_base_plate(settings, collection):
    """Beveled plate directly under the terrain block."""

    size_x = settings.width + settings.base_margin * 2.0
    size_y = settings.depth + settings.base_margin * 2.0
    size_z = settings.plate_thickness

    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)

    for v in bm.verts:
        v.co.x *= size_x
        v.co.y *= size_y
        v.co.z *= size_z

    mesh = bpy.data.meshes.new("Topo Base Mesh")
    bm.to_mesh(mesh)
    bm.free()

    try:
        mesh.shade_smooth()
    except Exception:
        pass

    obj = bpy.data.objects.new(BASE_NAME, mesh)
    collection.objects.link(obj)

    obj.location = (
        0.0,
        0.0,
        -settings.base_thickness - size_z * 0.5,
    )

    bevel_width = min(settings.base_bevel, size_z * 0.45)

    if bevel_width > 1e-5:
        bevel = obj.modifiers.new("Topo Base Bevel", "BEVEL")
        bevel.width = bevel_width
        bevel.segments = 3

        normals = obj.modifiers.new("Topo Base Normals", "WEIGHTED_NORMAL")
        normals.keep_sharp = True

    base_mat = bpy.data.materials.get(MATERIAL_BASE)

    if base_mat:
        mesh.materials.append(base_mat)

    return obj


# ============================================================
# CAMERA AND LIGHTING
# ============================================================

def point_object_at(obj, target):
    """Rotate an object so its local -Z axis points at target."""

    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def create_camera_and_lighting(settings, collection, scene):
    target_z = settings.height * 0.35
    target = (0.0, 0.0, target_z)
    span = max(settings.width, settings.depth)

    camera_data = bpy.data.cameras.new(CAMERA_NAME)
    camera = bpy.data.objects.new(CAMERA_NAME, camera_data)
    collection.objects.link(camera)

    camera.location = (
        settings.width * 0.95,
        -settings.depth * 1.15,
        settings.height * 1.8 + 2.0,
    )
    point_object_at(camera, target)

    camera_data.type = "ORTHO"
    camera_data.ortho_scale = span * 1.45
    scene.camera = camera

    def add_light(name, location, power, size):
        data = bpy.data.lights.new(name, "AREA")
        data.energy = power
        data.shape = "DISK"
        data.size = size

        light = bpy.data.objects.new(name, data)
        collection.objects.link(light)
        light.location = location
        point_object_at(light, target)

    add_light(
        "Topo Key Light",
        (
            -settings.width * 0.55,
            -settings.depth * 0.7,
            settings.height * 2.0 + 3.0,
        ),
        settings.key_light_power,
        span * 0.8,
    )

    add_light(
        "Topo Fill Light",
        (
            settings.width * 0.8,
            settings.depth * 0.4,
            settings.height * 1.2 + 2.0,
        ),
        settings.fill_light_power,
        span,
    )


# ============================================================
# GENERATION
# ============================================================

def build_topography(context):
    """Generate or regenerate the complete artwork."""

    scene = context.scene
    settings = scene.topo_settings
    style = settings.style

    saved_location, saved_rotation, saved_scale = (
        get_saved_topo_transform()
    )

    clear_generated_collection(scene)
    collection = get_or_create_collection(scene)

    update_materials(settings)
    update_world(settings, scene)

    colors = gradient_colors(settings)
    heights = generate_height_grid(settings)
    grid = Grid(settings, heights)

    if style in STEPPED_STYLES:
        create_stepped_mesh(settings, collection, grid, colors)
    elif style != STYLE_HOLLOW:
        create_smooth_terrain_mesh(settings, collection, grid)

    if settings.show_contours:
        create_contour_objects(settings, collection, grid, colors)

    if style in (STYLE_WIREFRAME, STYLE_HOLLOW):
        create_grid_lines(settings, collection, grid)

    if settings.show_base_plate:
        create_base_plate(settings, collection)

    if settings.create_camera:
        create_camera_and_lighting(settings, collection, scene)

    root = parent_generated_objects(
        collection,
        saved_location,
        saved_rotation,
        saved_scale,
    )

    bpy.ops.object.select_all(action="DESELECT")
    root.select_set(True)
    context.view_layer.objects.active = root

    return root


# ============================================================
# SETTINGS
# ============================================================

class TopoColorStop(PropertyGroup):

    color: FloatVectorProperty(
        name="Color",
        subtype="COLOR",
        size=3,
        min=0.0,
        max=1.0,
        default=(1.0, 1.0, 1.0),
    )


class TopoSettings(PropertyGroup):

    style: EnumProperty(
        name="Style",
        description="Look of the artwork",
        items=STYLE_ITEMS,
        default=STYLE_SMOOTH,
        update=on_style_update,
    )

    # Terrain dimensions.
    width: FloatProperty(
        name="Width", description="Terrain width",
        default=10.0, min=1.0, max=100.0, unit="LENGTH",
    )

    depth: FloatProperty(
        name="Depth", description="Terrain depth",
        default=10.0, min=1.0, max=100.0, unit="LENGTH",
    )

    height: FloatProperty(
        name="Height", description="Maximum terrain elevation",
        default=2.0, min=0.1, max=30.0, unit="LENGTH",
    )

    resolution: IntProperty(
        name="Resolution",
        description="Terrain grid resolution; higher values add detail",
        default=120, min=16, max=300,
    )

    complexity: IntProperty(
        name="Complexity",
        description="Number of noise scales used to shape the terrain",
        default=5, min=1, max=8,
    )

    seed: IntProperty(
        name="Seed", description="Random seed for the terrain shape",
        default=1, min=0, max=999999,
    )

    # Islands.
    island_edge_falloff: FloatProperty(
        name="Edge Falloff",
        description="How far from the block edge the terrain fades to "
                    "flat ground (fraction of the width)",
        default=0.3, min=0.05, max=0.5,
    )

    island_sea_level: FloatProperty(
        name="Sea Level",
        description="Raise to get fewer, smaller hills on flat ground",
        default=0.3, min=0.0, max=0.9,
    )

    # Levels and lines.
    contour_count: IntProperty(
        name="Levels",
        description="Number of contour lines / terrace steps",
        default=12, min=1, max=100,
    )

    show_contours: BoolProperty(
        name="Contour Lines",
        description="Draw contour lines",
        default=True,
    )

    contour_thickness: FloatProperty(
        name="Line Thickness", description="Thickness of contour lines",
        default=0.012, min=0.001, max=0.1, precision=3, subtype="DISTANCE",
    )

    line_smoothing: IntProperty(
        name="Line Smoothing",
        description="Smoothing passes applied to contour lines",
        default=2, min=0, max=8,
    )

    grid_line_count: IntProperty(
        name="Grid Lines",
        description="Grid lines across the terrain in each direction "
                    "(0 = off)",
        default=0, min=0, max=100,
    )

    step_bevel: FloatProperty(
        name="Step Rounding",
        description="Rounded edge width on terraces (0 = sharp)",
        default=0.0, min=0.0, max=0.3, precision=3, subtype="DISTANCE",
    )

    # Base.
    show_base_plate: BoolProperty(
        name="Base Plate", description="Add a plate under the terrain",
        default=True,
    )

    base_thickness: FloatProperty(
        name="Block Thickness",
        description="Thickness of the terrain block below the lowest ground",
        default=0.25, min=0.05, max=3.0, subtype="DISTANCE",
    )

    plate_thickness: FloatProperty(
        name="Plate Thickness",
        description="Thickness of the base plate",
        default=0.2, min=0.02, max=3.0, subtype="DISTANCE",
    )

    base_margin: FloatProperty(
        name="Base Margin",
        description="Extra base plate width around the terrain",
        default=0.25, min=0.0, max=3.0, subtype="DISTANCE",
    )

    base_bevel: FloatProperty(
        name="Base Bevel",
        description="Rounded edge width on the base plate",
        default=0.06, min=0.0, max=0.5, subtype="DISTANCE",
    )

    # Colours.
    surface_color: FloatVectorProperty(
        name="Surface Color", description="Terrain surface color",
        subtype="COLOR", size=3, min=0.0, max=1.0,
        default=(0.8, 0.78, 0.68),
    )

    surface_roughness: FloatProperty(
        name="Surface Roughness",
        description="Roughness of the terrain material",
        default=0.85, min=0.0, max=1.0,
    )

    contour_color: FloatVectorProperty(
        name="Line Color", description="Contour line color",
        subtype="COLOR", size=3, min=0.0, max=1.0,
        default=(0.08, 0.08, 0.07),
    )

    grid_color: FloatVectorProperty(
        name="Grid Color", description="Grid line color",
        subtype="COLOR", size=3, min=0.0, max=1.0,
        default=(0.05, 0.45, 0.5),
    )

    base_color: FloatVectorProperty(
        name="Base Color", description="Base plate color",
        subtype="COLOR", size=3, min=0.0, max=1.0,
        default=(0.12, 0.12, 0.13),
    )

    side_color: FloatVectorProperty(
        name="Side Color", description="Terrain side wall color",
        subtype="COLOR", size=3, min=0.0, max=1.0,
        default=(0.25, 0.25, 0.24),
    )

    line_color_mode: EnumProperty(
        name="Line Colors",
        description="How lines are coloured",
        items=LINE_COLOR_ITEMS,
        default="SOLID",
    )

    color_by_height: BoolProperty(
        name="Color By Height",
        description="Colour the terraces with the height gradient",
        default=False,
    )

    gradient: CollectionProperty(type=TopoColorStop)

    line_glow: BoolProperty(
        name="Glowing Lines",
        description="Make lines emit light",
        default=False,
    )

    glow_strength: FloatProperty(
        name="Glow Strength", description="Emission strength of the lines",
        default=6.0, min=0.0, max=100.0,
    )

    set_background: BoolProperty(
        name="Set World Background",
        description="Change the world background color on generate",
        default=False,
    )

    background_color: FloatVectorProperty(
        name="Background", description="World background color",
        subtype="COLOR", size=3, min=0.0, max=1.0,
        default=(0.55, 0.55, 0.56),
    )

    # Scene setup.
    create_camera: BoolProperty(
        name="Create Camera & Lights",
        description="Generate a camera and studio lighting",
        default=True,
    )

    key_light_power: FloatProperty(
        name="Key Light Power", description="Power of the main area light",
        default=1200.0, min=0.0, max=10000.0,
    )

    fill_light_power: FloatProperty(
        name="Fill Light Power", description="Power of the fill area light",
        default=500.0, min=0.0, max=10000.0,
    )


# ============================================================
# OPERATORS
# ============================================================

class TOPO_OT_generate(Operator):
    bl_idname = "topo.generate"
    bl_label = "Generate Topography"
    bl_description = "Generate or regenerate the topographic artwork"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            build_topography(context)
        except Exception as exc:
            self.report({"ERROR"}, f"Generation failed: {exc}")
            raise

        self.report({"INFO"}, "Topographic artwork generated")
        return {"FINISHED"}


class TOPO_OT_randomize(Operator):
    bl_idname = "topo.randomize_seed"
    bl_label = "Randomize Seed"
    bl_description = "Choose a new seed and regenerate the terrain"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = context.scene.topo_settings

        old_seed = settings.seed
        rng = random.SystemRandom()
        new_seed = old_seed

        while new_seed == old_seed:
            new_seed = rng.randint(0, 999999)

        settings.seed = new_seed

        try:
            build_topography(context)
        except Exception as exc:
            self.report({"ERROR"}, f"Generation failed: {exc}")
            raise

        self.report({"INFO"}, f"New terrain seed: {new_seed}")
        return {"FINISHED"}


class TOPO_OT_update_materials(Operator):
    bl_idname = "topo.update_materials"
    bl_label = "Update Materials"
    bl_description = (
        "Apply the current colors to the shared materials "
        "(gradient colors need Generate)"
    )
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        update_materials(context.scene.topo_settings)
        self.report({"INFO"}, "Materials updated")
        return {"FINISHED"}


class TOPO_OT_apply_style(Operator):
    bl_idname = "topo.apply_style_defaults"
    bl_label = "Reset Style Defaults"
    bl_description = "Reset colors and options to the style's defaults"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        apply_style_preset(context.scene.topo_settings)
        return {"FINISHED"}


class TOPO_OT_gradient_add(Operator):
    bl_idname = "topo.gradient_add"
    bl_label = "Add Color"
    bl_description = "Add a color to the height gradient"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = context.scene.topo_settings

        previous = (
            tuple(settings.gradient[-1].color)
            if len(settings.gradient)
            else (1.0, 1.0, 1.0)
        )

        item = settings.gradient.add()
        item.color = previous
        return {"FINISHED"}


class TOPO_OT_gradient_remove(Operator):
    bl_idname = "topo.gradient_remove"
    bl_label = "Remove Color"
    bl_description = "Remove this color from the height gradient"
    bl_options = {"REGISTER", "UNDO"}

    index: IntProperty()

    def execute(self, context):
        settings = context.scene.topo_settings

        if len(settings.gradient) <= 2:
            self.report({"WARNING"}, "A gradient needs at least 2 colors")
            return {"CANCELLED"}

        settings.gradient.remove(self.index)
        return {"FINISHED"}


class TOPO_OT_gradient_reset(Operator):
    bl_idname = "topo.gradient_reset"
    bl_label = "Reset Gradient"
    bl_description = "Restore the default height gradient"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        reset_gradient(context.scene.topo_settings)
        return {"FINISHED"}


# ============================================================
# N-PANEL UI
# ============================================================

class TOPO_PT_main_panel(Panel):
    bl_label = "Topographic Art"
    bl_idname = "TOPO_PT_main_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Topo"

    def draw(self, context):
        layout = self.layout
        s = context.scene.topo_settings
        style = s.style

        stepped = style in STEPPED_STYLES
        line_style = style in (STYLE_WIREFRAME, STYLE_HOLLOW)

        # Style.
        box = layout.box()
        box.label(text="Style", icon="SHADING_RENDERED")
        box.prop(s, "style", text="")
        box.operator("topo.apply_style_defaults", icon="FILE_REFRESH")

        # Terrain.
        box = layout.box()
        box.label(text="Terrain", icon="MESH_GRID")
        col = box.column(align=True)
        col.prop(s, "width")
        col.prop(s, "depth")
        col.prop(s, "height")
        col.prop(s, "resolution")
        col.prop(s, "complexity")

        if style == STYLE_ISLANDS:
            col = box.column(align=True)
            col.prop(s, "island_edge_falloff")
            col.prop(s, "island_sea_level")

        # Seed.
        box = layout.box()
        box.label(text="Randomization", icon="FILE_REFRESH")
        box.prop(s, "seed")
        box.operator(
            "topo.randomize_seed",
            text="Randomize Seed",
            icon="FILE_REFRESH",
        )

        # Levels and lines.
        box = layout.box()
        box.label(text="Levels & Lines", icon="MOD_BUILD")
        box.prop(s, "contour_count")

        if stepped:
            box.prop(s, "step_bevel")

        box.prop(s, "show_contours")

        if s.show_contours or line_style:
            box.prop(s, "contour_thickness")
            box.prop(s, "line_smoothing")

        if line_style:
            box.prop(s, "grid_line_count")

        # Base.
        box = layout.box()
        box.label(text="Base", icon="CUBE")
        box.prop(s, "base_thickness")
        box.prop(s, "show_base_plate")

        if s.show_base_plate:
            box.prop(s, "plate_thickness")
            box.prop(s, "base_margin")
            box.prop(s, "base_bevel")

        # Colors.
        box = layout.box()
        box.label(text="Colors", icon="MATERIAL")

        if style == STYLE_ISLANDS:
            box.prop(s, "color_by_height")

        if style != STYLE_HOLLOW and not use_layer_colors(s):
            box.prop(s, "surface_color")
            box.prop(s, "surface_roughness")

        if style != STYLE_HOLLOW:
            box.prop(s, "side_color")

        if s.show_base_plate:
            box.prop(s, "base_color")

        lines_visible = s.show_contours or line_style

        if lines_visible:
            box.prop(s, "line_color_mode", text="Lines")

            if s.line_color_mode == "SOLID":
                box.prop(s, "contour_color")

            if line_style:
                box.prop(s, "grid_color")

            box.prop(s, "line_glow")

            if s.line_glow:
                box.prop(s, "glow_strength")

        box.prop(s, "set_background")

        if s.set_background:
            box.prop(s, "background_color")

        box.operator(
            "topo.update_materials",
            text="Update Materials",
            icon="FILE_TICK",
        )

        # Gradient.
        needs_gradient = use_layer_colors(s) or (
            lines_visible and s.line_color_mode == "GRADIENT"
        )

        if needs_gradient:
            box = layout.box()
            box.label(text="Height Gradient (low to high)", icon="COLOR")

            if len(s.gradient) < 2:
                box.label(text="Using default colors", icon="INFO")

            col = box.column(align=True)

            for index, stop in enumerate(s.gradient):
                row = col.row(align=True)
                row.prop(stop, "color", text="")
                op = row.operator(
                    "topo.gradient_remove", text="", icon="X"
                )
                op.index = index

            row = box.row(align=True)
            row.operator("topo.gradient_add", icon="ADD")
            row.operator("topo.gradient_reset", icon="FILE_REFRESH")

        # Scene.
        box = layout.box()
        box.label(text="Scene Setup", icon="LIGHT")
        box.prop(s, "create_camera")

        if s.create_camera:
            box.prop(s, "key_light_power")
            box.prop(s, "fill_light_power")

        layout.separator()
        layout.operator(
            "topo.generate",
            text="Generate / Regenerate",
            icon="PLAY",
        )


# ============================================================
# REGISTER
# ============================================================

classes = (
    TopoColorStop,
    TopoSettings,
    TOPO_OT_generate,
    TOPO_OT_randomize,
    TOPO_OT_update_materials,
    TOPO_OT_apply_style,
    TOPO_OT_gradient_add,
    TOPO_OT_gradient_remove,
    TOPO_OT_gradient_reset,
    TOPO_PT_main_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.topo_settings = PointerProperty(type=TopoSettings)


def unregister():
    if hasattr(bpy.types.Scene, "topo_settings"):
        del bpy.types.Scene.topo_settings

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()