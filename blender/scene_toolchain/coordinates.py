"""Pure-Python conversion between Three.js XYZ Euler/y-up and Blender z-up."""

import math


def _mul(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3))
                       for j in range(3)) for i in range(3))


def _transpose(m):
    return tuple(zip(*m))


# A maps web vectors to Blender vectors: (x, y, z) -> (x, -z, y).
_A = ((1, 0, 0), (0, 0, -1), (0, 1, 0))


def web_to_blender(v):
    return (v[0], -v[2], v[1])


def blender_to_web(v):
    return (v[0], v[2], -v[1])


def web_size_to_blender(v):
    return (v[0], v[2], v[1])


def blender_size_to_web(v):
    return (v[0], v[2], v[1])


def web_euler_matrix(euler):
    """Three.js Euler order XYZ: rotation matrix Rx * Ry * Rz."""
    x, y, z = euler
    cx, sx = math.cos(x), math.sin(x)
    cy, sy = math.cos(y), math.sin(y)
    cz, sz = math.cos(z), math.sin(z)
    return _mul(_mul(((1, 0, 0), (0, cx, -sx), (0, sx, cx)),
                     ((cy, 0, sy), (0, 1, 0), (-sy, 0, cy))),
                ((cz, -sz, 0), (sz, cz, 0), (0, 0, 1)))


def web_matrix_to_euler(m):
    """Extract a Three.js XYZ Euler; gimbal-lock solutions are not unique."""
    y = math.asin(max(-1.0, min(1.0, m[0][2])))
    if abs(m[0][2]) < 1.0 - 1e-12:
        x = math.atan2(-m[1][2], m[2][2])
        z = math.atan2(-m[0][1], m[0][0])
    else:
        x = math.atan2(m[2][1], m[1][1])
        z = 0.0
    return (x, y, z)


def web_rotation_to_blender(m):
    return _mul(_mul(_A, m), _transpose(_A))


def blender_rotation_to_web(m):
    return _mul(_mul(_transpose(_A), m), _A)
