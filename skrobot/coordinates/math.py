from __future__ import absolute_import

from math import acos
from math import asin
from math import atan2
from math import cos
from math import pi
from math import sin

import numpy as np


# epsilon for testing whether a number is close to zero
_EPS = np.finfo(float).eps * 4.0


def _wrap_axis(axis):
    """Convert axis to float vector.

    Parameters
    ----------
    axis : list or np.ndarray or str or bool or None
        rotation axis indicated by number or string.

    Returns
    -------
    axis : np.ndarray
        conveted axis

    Examples
    --------
    >>> from skrobot.coordinates.math import _wrap_axis
    >>> _wrap_axis('x')
    array([1, 0, 0])
    >>> _wrap_axis('y')
    array([0, 1, 0])
    >>> _wrap_axis('z')
    array([0, 0, 1])
    >>> _wrap_axis('xy')
    array([1, 1, 0])
    >>> _wrap_axis([1, 1, 1])
    array([1, 1, 1])
    >>> _wrap_axis(True)
    array([0, 0, 0])
    >>> _wrap_axis(False)
    array([1, 1, 1])
    """
    if isinstance(axis, str):
        if axis in ['x', 'xx']:
            axis = np.array([1, 0, 0])
        elif axis in ['y', 'yy']:
            axis = np.array([0, 1, 0])
        elif axis in ['z', 'zz']:
            axis = np.array([0, 0, 1])
        elif axis == '-x':
            axis = np.array([-1, 0, 0])
        elif axis == '-y':
            axis = np.array([0, -1, 0])
        elif axis == '-z':
            axis = np.array([0, 0, -1])
        elif axis in ['xy', 'yx']:
            axis = np.array([1, 1, 0])
        elif axis in ['yz', 'zy']:
            axis = np.array([0, 1, 1])
        elif axis in ['zx', 'xz']:
            axis = np.array([1, 0, 1])
        else:
            raise NotImplementedError
    elif isinstance(axis, list):
        if not len(axis) == 3:
            raise ValueError
        axis = np.array(axis)
    elif isinstance(axis, np.ndarray):
        if not axis.shape == (3,):
            raise ValueError
    elif isinstance(axis, bool):
        if axis is True:
            return np.array([0, 0, 0])
        else:
            return np.array([1, 1, 1])
    elif axis is None:
        return np.array([1, 1, 1])
    else:
        raise ValueError
    return axis


def _check_valid_rotation(rotation):
    """Checks that the given rotation matrix is valid."""
    rotation = np.array(rotation)
    if not isinstance(
            rotation,
            np.ndarray) or not np.issubdtype(
            rotation.dtype,
            np.number):
        raise ValueError('Rotation must be specified as numeric numpy array')

    if len(rotation.shape) != 2 or \
       rotation.shape[0] != 3 or rotation.shape[1] != 3:
        raise ValueError('Rotation must be specified as a 3x3 ndarray')

    if np.abs(np.linalg.det(rotation) - 1.0) > 1e-3:
        raise ValueError('Illegal rotation. Must have determinant == 1.0, '
                         'get {}'.format(np.linalg.deg(rotation)))
    return rotation


def _check_valid_translation(translation):
    """Checks that the translation vector is valid."""
    if not isinstance(
            translation,
            np.ndarray) or not np.issubdtype(
            translation.dtype,
            np.number):
        raise ValueError(
            'Translation must be specified as numeric numpy array')

    t = translation.squeeze()
    if len(t.shape) != 1 or t.shape[0] != 3:
        raise ValueError(
            'Translation must be specified as a 3-vector, '
            '3x1 ndarray, or 1x3 ndarray')


def wxyz2xyzw(quat):
    """Convert quaternion [w, x, y, z] to [x, y, z, w] order.

    Parameters
    ----------
    quat : list or np.ndarray
        quaternion [w, x, y, z]
    Returns
    -------
    quaternion : np.ndarray
        quaternion [x, y, z, w]

    Examples
    --------
    >>> from skrobot.coordinates.math import wxyz2xyzw
    >>> wxyz2xyzw([1, 2, 3, 4])
    array([2, 3, 4, 1])
    """
    if isinstance(quat, list):
        quat = np.array(quat)
    return np.roll(quat, -1)


def xyzw2wxyz(quat):
    """Convert quaternion [x, y, z, w] to [w, x, y, z] order.

    Parameters
    ----------
    quat : list or np.ndarray
        quaternion [x, y, z, w]

    Returns
    -------
    quaternion : np.ndarray
        quaternion [w, x, y, z]

    Examples
    --------
    >>> from skrobot.coordinates.math import xyzw2wxyz
    >>> xyzw2wxyz([1, 2, 3, 4])
    array([4, 1, 2, 3])
    """
    if isinstance(quat, list):
        quat = np.array(quat)
    return np.roll(quat, 1)


def triple_product(a, b, c):
    """Returns Triple Product https://en.wikipedia.org/wiki/Triple_product.

    Parameters
    ----------
    a : numpy.ndarray
    b : numpy.ndarray
    c : numpy.ndarray

    Returns
    -------
    triple product : np.ndarray

    Examples
    --------
    >>> from skrobot.coordinates.math import triple_product
    >>> triple_product([1, 1, 1], [1, 1, 1], [1, 1, 1])
    0
    >>> triple_product([1, 0, 0], [0, 1, 0], [0, 0, 1])
    1
    """
    return np.dot(a, np.cross(b, c))


def sr_inverse(J, k=1.0, weight_vector=None):
    """Returns sr-inverse of given Jacobian.

    Calculate Singularity-Robust Inverse
    See: `Inverse Kinematic Solutions With Singularity Robustness \
          for Robot Manipulator Control`

    """
    r, _ = J.shape

    # without weight
    if weight_vector is None:
        return sr_inverse_org(J, k)

    # k=0 => sr-inverse = pseudo-inverse
    if k == 0.0:
        return np.linalg.pinv(J)

    # with weight
    weight_matrix = np.diag(weight_vector)

    # umat = J W J^T + kI
    # ret = W J^T (J W J^T + kI)^(-1)
    weight_J = np.matmul(weight_matrix, J.T)
    umat = np.matmul(J, weight_J) + k * np.eye(r)
    ret = np.matmul(weight_J, np.linalg.inv(umat))
    return ret


def sr_inverse_org(J, k=1.0):
    """J^T (JJ^T + kI_m)^(-1)"""
    r, _ = J.shape
    return np.matmul(J.T,
                     np.linalg.inv(np.matmul(J, J.T) + k * np.eye(r)))


def manipulability(J):
    """Return manipulability of given matrix.

    https://www.jstage.jst.go.jp/article/jrsj1983/2/1/2_1_63/_article/-char/ja/
    """
    return np.sqrt(max(0.0, np.linalg.det(np.matmul(J, J.T))))


def midpoint(p, a, b):
    """Return midpoint

    Parameters
    ----------
    p : float
        ratio of a:b
    a : np.ndarray
        vector
    b : np.ndarray
        vector

    Returns
    -------
    midpoint : np.ndarray
        midpoint

    Examples
    --------
    >>> import numpy as np
    >>> from skrobot.coordinates.math import midpoint
    >>> midpoint(0.5, np.ones(3), np.zeros(3))
    >>> array([0.5, 0.5, 0.5])
    """
    return a + (b - a) * p


def midrot(p, r1, r2):
    """Returns mid (or p) rotation matrix of given two matrix r1 and r2.

    Parameters
    ----------
    p : float
        ratio of r1:r2
    r1 : np.ndarray
        3x3 rotation matrix
    r2 : np.ndarray
        3x3 rotation matrix

    Returns
    -------
    r : np.ndarray
        3x3 rotation matrix

    Examples
    --------
    >>> import numpy as np
    >>> from skrobot.coordinates.math import midrot
    >>> midrot(0.5,
            np.eye(3),
            np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]]))
    array([[ 0.70710678,  0.        ,  0.70710678],
           [ 0.        ,  1.        ,  0.        ],
           [-0.70710678,  0.        ,  0.70710678]])
    >>> from skrobot.coordinates.math import rpy_angle
    >>> np.rad2deg(rpy_angle(midrot(0.5,
                   np.eye(3),
                   np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]])))[0])
    array([ 0., 45.,  0.])
    """
    r1 = _check_valid_rotation(r1)
    r2 = _check_valid_rotation(r2)
    r = np.matmul(r1.T, r2)
    omega = matrix_log(r)
    r = matrix_exponent(omega, p)
    return np.matmul(r1, r)


def transform(m, v):
    """Return transform m v

    Args:
        m (np.array): 3 x 3 matrix
        v (np.array or list): vector

    Returns:
        numpy.array vector
    """
    m = np.array(m)
    v = np.array(v)
    return np.matmul(m, v)


def rotation_matrix(theta, axis):
    """Return the rotation matrix.

    Return the rotation matrix associated with counterclockwise rotation
    about the given axis by theta radians.

    Parameters
    ----------
    theta : float
        radian
    axis : string or list or np.ndarray
        rotation axis such that 'x', 'y', 'z'
        [0, 0, 1], [0, 1, 0], [1, 0, 0]

    Returns
    -------
    rot : np.ndarray
        rotation matrix about the given axis by theta radians.

    Examples
    --------
    >>> import numpy as np
    >>> from skrobot.coordinates.math import rotation_matrix
    >>> rotation_matrix(np.pi / 2.0, [1, 0, 0])
    array([[ 1.00000000e+00,  0.00000000e+00,  0.00000000e+00],
           [ 0.00000000e+00,  2.22044605e-16, -1.00000000e+00],
           [ 0.00000000e+00,  1.00000000e+00,  2.22044605e-16]])
    >>> rotation_matrix(np.pi / 2.0, 'y')
    array([[ 2.22044605e-16,  0.00000000e+00,  1.00000000e+00],
           [ 0.00000000e+00,  1.00000000e+00,  0.00000000e+00],
           [-1.00000000e+00,  0.00000000e+00,  2.22044605e-16]])
    """
    axis = _wrap_axis(axis)
    axis = axis / np.sqrt(np.dot(axis, axis))
    a = np.cos(theta / 2.0)
    b, c, d = -axis * np.sin(theta / 2.0)
    aa, bb, cc, dd = a * a, b * b, c * c, d * d
    bc, ad, ac, ab, bd, cd = b * c, a * d, a * c, a * b, b * d, c * d
    return np.array([[aa + bb - cc - dd, 2 * (bc + ad), 2 * (bd - ac)],
                     [2 * (bc - ad), aa + cc - bb - dd, 2 * (cd + ab)],
                     [2 * (bd + ac), 2 * (cd - ab), aa + dd - bb - cc]])


def rotate_vector(vec, theta, axis):
    """Rotate vector.

    Rotate vec with respect to axis.

    Parameters
    ----------
    vec : list or numpy.ndarray
        target vector
    theta : float
        rotation angle
    axis : list or numpy.ndarray or string.
        axis of rotation.

    Returns
    -------
    rotated_vec : numpy.ndarray
        rotated vector.

    Examples
    --------
    >>> from numpy import pi
    >>> from skrobot.coordinates.math import rotate_vector
    >>> rotate_vector([1, 0, 0], pi / 6.0, [1, 0, 0])
    array([1., 0., 0.])
    >>> rotate_vector([1, 0, 0], pi / 6.0, [0, 1, 0])
    array([ 0.8660254,  0.       , -0.5      ])
    >>> rotate_vector([1, 0, 0], pi / 6.0, [0, 0, 1])
    array([0.8660254, 0.5      , 0.       ])
    """
    rot = rotation_matrix(theta, axis)
    rotated_vec = transform(rot, vec)
    return rotated_vec


def rotate_matrix(matrix, theta, axis, world=None):
    if world is False or world is None:
        return np.dot(matrix, rotation_matrix(theta, axis))
    return np.dot(rotation_matrix(theta, axis), matrix)


def rpy_matrix(az, ay, ax):
    """Return rotation matrix from yaw-pitch-roll

    This function creates a new rotation matrix which has been
    rotated ax radian around x-axis in WORLD, ay radian around y-axis in WORLD,
    and az radian around z axis in WORLD, in this order. These angles can be
    extracted by the rpy function.

    Parameters
    ----------
    az : float
        rotated around z-axis(yaw) in radian.
    ay : float
        rotated around y-axis(pitch) in radian.
    ax : float
        rotated around x-axis(roll) in radian.

    Returns
    -------
    r : np.ndarray
        rotation matrix

    Examples
    --------
    >>> import numpy as np
    >>> from skrobot.coordinates.math import rpy_matrix
    >>> yaw = np.pi / 2.0
    >>> pitch = np.pi / 3.0
    >>> roll = np.pi / 6.0
    >>> rpy_matrix(yaw, pitch, roll)
    array([[ 1.11022302e-16, -8.66025404e-01,  5.00000000e-01],
           [ 5.00000000e-01,  4.33012702e-01,  7.50000000e-01],
           [-8.66025404e-01,  2.50000000e-01,  4.33012702e-01]])
    """
    r = rotation_matrix(ax, 'x')
    r = rotate_matrix(r, ay, 'y', world=True)
    r = rotate_matrix(r, az, 'z', world=True)
    return r


def rpy_angle(matrix):
    """Decomposing a rotation matrix to yaw-pitch-roll.

    Parameters
    ----------
    matrix : list or np.ndarray
        3x3 rotation matrix

    Returns
    -------
    rpy : np.ndarray
        pair of rpy in yaw-pitch-roll order.

    Examples
    --------
    >>> import numpy as np
    >>> from skrobot.coordinates.math import rpy_matrix
    >>> from skrobot.coordinates.math import rpy_angle
    >>> yaw = np.pi / 2.0
    >>> pitch = np.pi / 3.0
    >>> roll = np.pi / 6.0
    >>> rot = rpy_matrix(yaw, pitch, roll)
    >>> rpy_angle(rot)
    (array([1.57079633, 1.04719755, 0.52359878]),
     array([ 4.71238898,  2.0943951 , -2.61799388]))
    """
    a = np.arctan2(matrix[1, 0], matrix[0, 0])
    sa = np.sin(a)
    ca = np.cos(a)
    b = np.arctan2(-matrix[2, 0], ca * matrix[0, 0] + sa * matrix[1, 0])
    c = np.arctan2(sa * matrix[0, 2] - ca * matrix[1, 2],
                   -sa * matrix[0, 1] + ca * matrix[1, 1])
    rpy = np.array([a, b, c])

    a = a + np.pi
    sa = np.sin(a)
    ca = np.cos(a)
    b = np.arctan2(-matrix[2, 0], ca * matrix[0, 0] + sa * matrix[1, 0])
    c = np.arctan2(sa * matrix[0, 2] - ca * matrix[1, 2],
                   -sa * matrix[0, 1] + ca * matrix[1, 1])
    return rpy, np.array([a, b, c])


def normalize_vector(v, ord=2):
    """Return normalized vector

    Parameters
    ----------
    v : list or np.ndarray
        vector
    ord : int (optional)
        ord of np.linalg.norm

    Returns
    -------
    v : np.ndarray
        normalized vector

    Examples
    --------
    >>> from skrobot.coordinates.math import normalize_vector
    >>> normalize_vector([1, 1, 1])
    array([0.57735027, 0.57735027, 0.57735027])
    >>> normalize_vector([0, 0, 0])
    array([0., 0., 0.])
    """
    v = np.array(v, dtype=np.float64)
    if np.allclose(v, 0) is True:
        return v
    return v / np.linalg.norm(v, ord=ord)


def matrix2quaternion(m):
    """Returns quaternion of given rotation matrix.

    Parameters
    ----------
    m : list or np.ndarray
        3x3 rotation matrix

    Returns
    -------
    quaternion : np.ndarray
        quaternion [w, x, y, z] order

    Examples
    --------
    >>> import numpy
    >>> from skrobot.coordinates.math import matrix2quaternion
    >>> matrix2quaternion(np.eye(3))
    array([1., 0., 0., 0.])
    """
    m = np.array(m, dtype=np.float64)
    q0_2 = (1 + m[0, 0] + m[1, 1] + m[2, 2]) / 4.0
    q1_2 = (1 + m[0, 0] - m[1, 1] - m[2, 2]) / 4.0
    q2_2 = (1 - m[0, 0] + m[1, 1] - m[2, 2]) / 4.0
    q3_2 = (1 - m[0, 0] - m[1, 1] + m[2, 2]) / 4.0
    mq_2 = max(q0_2, q1_2, q2_2, q3_2)
    if np.isclose(mq_2, q0_2):
        q0 = np.sqrt(q0_2)
        q1 = ((m[2, 1] - m[1, 2]) / (4.0 * q0))
        q2 = ((m[0, 2] - m[2, 0]) / (4.0 * q0))
        q3 = ((m[1, 0] - m[0, 1]) / (4.0 * q0))
    elif np.isclose(mq_2, q1_2):
        q1 = np.sqrt(q1_2)
        q0 = ((m[2, 1] - m[1, 2]) / (4.0 * q1))
        q2 = ((m[1, 0] + m[0, 1]) / (4.0 * q1))
        q3 = ((m[0, 2] + m[2, 0]) / (4.0 * q1))
    elif np.isclose(mq_2, q2_2):
        q2 = np.sqrt(q2_2)
        q0 = ((m[0, 2] - m[2, 0]) / (4.0 * q2))
        q1 = ((m[1, 0] + m[0, 1]) / (4.0 * q2))
        q3 = ((m[1, 2] + m[2, 1]) / (4.0 * q2))
    elif np.isclose(mq_2, q3_2):
        q3 = np.sqrt(q3_2)
        q0 = ((m[1, 0] - m[0, 1]) / (4.0 * q3))
        q1 = ((m[0, 2] + m[2, 0]) / (4.0 * q3))
        q2 = ((m[1, 2] + m[2, 1]) / (4.0 * q3))
    else:
        raise ValueError('matrix {} is invalid'.format(m))
    return np.array([q0, q1, q2, q3])


def quaternion2matrix(q):
    """Returns matrix of given quaternion.

    Parameters
    ----------
    quaternion : list or np.ndarray
        quaternion [w, x, y, z] order

    Returns
    -------
    rot : np.ndarray
        3x3 rotation matrix

    Examples
    --------
    >>> import numpy
    >>> from skrobot.coordinates.math import quaternion2matrix
    >>> quaternion2matrix([1, 0, 0, 0])
    array([[1., 0., 0.],
           [0., 1., 0.],
           [0., 0., 1.]])
    """
    q0 = q[0]
    q1 = q[1]
    q2 = q[2]
    q3 = q[3]
    norm = np.linalg.norm(q)
    if not np.isclose(norm, 1.0):
        raise ValueError("quaternion q's norm is not 1")
    m = np.zeros((3, 3))
    m[0, 0] = q0 * q0 + q1 * q1 - q2 * q2 - q3 * q3
    m[0, 1] = 2 * (q1 * q2 - q0 * q3)
    m[0, 2] = 2 * (q1 * q3 + q0 * q2)

    m[1, 0] = 2 * (q1 * q2 + q0 * q3)
    m[1, 1] = q0 * q0 - q1 * q1 + q2 * q2 - q3 * q3
    m[1, 2] = 2 * (q2 * q3 - q0 * q1)

    m[2, 0] = 2 * (q1 * q3 - q0 * q2)
    m[2, 1] = 2 * (q2 * q3 + q0 * q1)
    m[2, 2] = q0 * q0 - q1 * q1 - q2 * q2 + q3 * q3
    return m


def matrix_log(m):
    """Returns matrix log of given rotation matrix, it returns [-pi, pi]

    Parameters
    ----------
    m : list or np.ndarray
        3x3 rotation matrix

    Returns
    -------
    matrixlog : np.ndarray
        vector of shape (3, )

    Examples
    --------
    >>> import numpy as np
    >>> from skrobot.coordinates.math import matrix_log
    >>> matrix_log(np.eye(3))
    array([0., 0., 0.])
    """
    # calc logarithm of quaternion
    q = matrix2quaternion(m)
    q_w = q[0]
    q_xyz = q[1:]
    theta = 2.0 * np.arctan(np.linalg.norm(q_xyz) / q_w)
    if theta > np.pi:
        theta = theta - 2.0 * np.pi
    elif theta < - np.pi:
        theta = theta + 2.0 * np.pi
    return theta * normalize_vector(q_xyz)


def matrix_exponent(omega, p=1.0):
    """Returns exponent of given omega.

    Parameters
    ----------
    omega : list or np.ndarray
        vector of shape (3,)

    Returns
    -------
    rot : np.ndarray
        exponential matrix of given omega

    Examples
    --------
    >>> import numpy as np
    >>> from skrobot.coordinates.math import matrix_exponent
    >>> matrix_exponent([1, 1, 1])
    array([[ 0.22629564, -0.18300792,  0.95671228],
           [ 0.95671228,  0.22629564, -0.18300792],
           [-0.18300792,  0.95671228,  0.22629564]])
    >>> matrix_exponent([1, 0, 0])
    array([[ 1.        ,  0.        ,  0.        ],
           [ 0.        ,  0.54030231, -0.84147098],
           [ 0.        ,  0.84147098,  0.54030231]])
    """
    w = np.linalg.norm(omega)
    amat = outer_product_matrix(normalize_vector(omega))
    return np.eye(3) + np.sin(w * p) * amat + \
        (1.0 - np.cos(w * p)) * np.matmul(amat, amat)


def outer_product_matrix(v):
    """Returns outer product matrix of given v.

    Returns outer product matrix of given v

    Parameters
    ----------
    v : np.ndarray or list
        [x, y, z]

    Returns
    -------
    matrix : np.ndarray
        3x3 rotation matrix
        [[  0 -w2  w1]
         [ w2   0 -w0]
         [-w1  w0   0]]

    Examples
    --------
    >>> from skrobot.coordinates.math import outer_product_matrix
    >>> outer_product_matrix([1, 2, 3])
    array([[ 0, -3,  2],
           [ 3,  0, -1],
           [-2,  1,  0]])
    """
    return np.array([[0, -v[2], v[1]],
                     [v[2], 0, -v[0]],
                     [-v[1], v[0], 0]])


def quaternion2rpy(q):
    """Returns Roll-pitch-yaw angles of a given quaternion.

    Parameters
    ----------
    q : np.ndarray or list
        Quaternion in [w x y z] format.

    Returns
    -------
    rpy : np.ndarray
        Array of yaw-pitch-roll angles, in radian.

    Examples
    --------
    >>> from skrobot.coordinates.math import quaternion2rpy
    >>> quaternion2rpy([1, 0, 0, 0])
    (array([ 0., -0.,  0.]), array([3.14159265, 3.14159265, 3.14159265]))
    >>> quaternion2rpy([0, 1, 0, 0])
    (array([ 0.        , -0.        ,  3.14159265]),
     array([3.14159265, 3.14159265, 0.        ]))
    """
    roll = atan2(
        2 * q[2] * q[3] + 2 * q[0] * q[1],
        q[3] ** 2 - q[2] ** 2 - q[1] ** 2 + q[0] ** 2)
    pitch = -asin(
        2 * q[1] * q[3] - 2 * q[0] * q[2])
    yaw = atan2(
        2 * q[1] * q[2] + 2 * q[0] * q[3],
        q[1] ** 2 + q[0] ** 2 - q[3] ** 2 - q[2] ** 2)
    rpy = np.array([yaw, pitch, roll])
    return rpy, np.pi - rpy


def rpy2quaternion(rpy):
    """Return Quaternion from yaw-pitch-roll angles.

    Parameters
    ----------
    rpy : np.ndarray or list
        Vector of yaw-pitch-roll angles in radian.

    Returns
    -------
    quat : np.ndarray
        Quaternion in [w x y z] format.

    Examples
    --------
    >>> import numpy as np
    >>> from skrobot.coordinates.math import rpy2quaternion
    >>> rpy2quaternion([0, 0, 0])
    array([1., 0., 0., 0.])
    >>> yaw = np.pi / 3.0
    >>> rpy2quaternion([yaw, 0, 0])
    array([0.8660254, 0.       , 0.       , 0.5      ])
    >>> rpy2quaternion([np.pi * 2 - yaw, 0, 0])
    array([-0.8660254, -0.       ,  0.       ,  0.5      ])
    """
    yaw, pitch, roll = rpy
    cr, cp, cy = cos(roll / 2.), cos(pitch / 2.), cos(yaw / 2.)
    sr, sp, sy = sin(roll / 2.), sin(pitch / 2.), sin(yaw / 2.)
    return np.array([
        cr * cp * cy + sr * sp * sy,
        -cr * sp * sy + cp * cy * sr,
        cr * cy * sp + sr * cp * sy,
        cr * cp * sy - sr * cy * sp])


def rotation_matrix_from_rpy(rpy):
    """Returns Rotation matrix from yaw-pitch-roll angles.

    Parameters
    ----------
    rpy : np.ndarray or list
        Vector of yaw-pitch-roll angles in radian.

    Returns
    -------
    rot : np.ndarray
        3x3 rotation matrix

    Examples
    --------
    >>> import numpy as np
    >>> from skrobot.coordinates.math import rotation_matrix_from_rpy
    >>> rotation_matrix_from_rpy([0, np.pi / 3, 0])
    array([[ 0.5      ,  0.       ,  0.8660254],
           [ 0.       ,  1.       ,  0.       ],
           [-0.8660254,  0.       ,  0.5      ]])
    """
    return quaternion2matrix(quat_from_rpy(rpy))


def rodrigues(axis, theta=None):
    """Rodrigues formula.

    Parameters
    ----------
    axis : np.ndarray or list
        [x, y, z]
    theta: float or None (optional)
        radian. If None is given, calculate theta from axis.

    Returns
    -------
    mat : np.ndarray
        3x3 rotation matrix

    Examples
    --------
    >>> import numpy
    >>> from skrobot.coordinates.math import rodrigues
    >>> rodrigues([1, 0, 0], 0)
    array([[1., 0., 0.],
           [0., 1., 0.],
           [0., 0., 1.]])
    >>> rodrigues([1, 1, 1], numpy.pi)
    array([[-0.33333333,  0.66666667,  0.66666667],
           [ 0.66666667, -0.33333333,  0.66666667],
           [ 0.66666667,  0.66666667, -0.33333333]])
    """
    axis = np.array(axis, dtype=np.float64)
    if theta is None:
        theta = np.sqrt(np.sum(axis ** 2))
    a = axis / np.linalg.norm(axis)
    cross_prod = np.array([[0, -a[2], a[1]],
                           [a[2], 0, -a[0]],
                           [-a[1], a[0], 0]])
    ctheta = np.cos(theta)
    stheta = np.sin(theta)
    mat = np.eye(3) + \
        cross_prod * stheta + \
        np.matmul(cross_prod, cross_prod) * (1 - ctheta)
    return mat


def rotation_angle(mat):
    """Inverse Rodrigues formula Convert Rotation-Matirx to Axis-Angle.

    Return theta and axis.
    If given unit matrix, return None.

    Parameters
    ----------
    mat : np.ndarray
        rotation matrix, shape (3, 3)

    Returns
    -------
    theta : float
        rotation angle in radian
    axis : np.ndarray
        rotation axis

    Examples
    --------
    >>> import numpy
    >>> from skrobot.coordinates.math import rotation_angle
    >>> rotation_angle(numpy.eye(3)) is None
    True
    >>> rotation_angle(numpy.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]]))
    (1.5707963267948966, array([0., 1., 0.]))
    """
    mat = _check_valid_rotation(mat)
    if np.array_equal(mat, np.eye(3)):
        return None
    theta = np.arccos((np.trace(mat) - 1) / 2)
    if abs(theta) < _EPS:
        raise ValueError('Rotation Angle is too small. \nvalue : {}'.
                         format(theta))
    axis = 1.0 / (2 * np.sin(theta)) * \
        np.array([mat[2, 1] - mat[1, 2], mat[0, 2] -
                  mat[2, 0], mat[1, 0] - mat[0, 1]])
    return theta, axis


def rotation_distance(mat1, mat2):
    """Return the distance of rotation matrixes.

    Parameters
    ----------
    mat1 : list or np.ndarray
    mat2 : list or np.ndarray
        3x3 matrix

    Returns
    -------
    diff_theta : float
        distance of rotation matrixes in radian.

    Examples
    --------
    >>> import numpy
    >>> from skrobot.coordinates.math import rotation_distance
    >>> rotation_distance(numpy.eye(3), numpy.eye(3))
    0.0
    >>> rotation_distance(
            numpy.eye(3),
            numpy.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]]))
    1.5707963267948966
    """
    mat1 = _check_valid_rotation(mat1)
    mat2 = _check_valid_rotation(mat2)
    q1 = matrix2quaternion(mat1)
    q2 = matrix2quaternion(mat2)
    diff_theta = quaternion_distance(q1, q2)
    return diff_theta


def quaternion_multiply(quaternion1, quaternion0):
    """Return multiplication of two quaternions.

    Parameters
    ----------
    quaternion0 : list or np.ndarray
        [w, x, y, z]
    quaternion1 : list or np.ndarray
        [w, x, y, z]

    Returns
    -------
    quaternion : np.ndarray
        [w, x, y, z]

    Examples
    --------
    >>> q = quaternion_multiply([4, 1, -2, 3], [8, -5, 6, 7])
    >>> numpy.allclose(q, [28, -44, -14, 48])
    True
    """
    w0, x0, y0, z0 = quaternion0
    w1, x1, y1, z1 = quaternion1
    return np.array((
        -x1 * x0 - y1 * y0 - z1 * z0 + w1 * w0,
        x1 * w0 + y1 * z0 - z1 * y0 + w1 * x0,
        -x1 * z0 + y1 * w0 + z1 * x0 + w1 * y0,
        x1 * y0 - y1 * x0 + z1 * w0 + w1 * z0), dtype=np.float64)


def quaternion_conjugate(quaternion):
    """Return conjugate of quaternion.

    Parameters
    ----------
    quaternion : list or np.ndarray
        quaternion [w, x, y, z]

    Returns
    -------
    conjugate of quaternion : np.ndarray
        [w, x, y, z]

    Examples
    --------
    >>> q0 = random_quaternion()
    >>> q1 = quaternion_conjugate(q0)
    >>> np.allclose(quaternion_multiply(q0, q1), [1.0, 0, 0, 0])
    True
    """
    return np.array((quaternion[0], -quaternion[1],
                     -quaternion[2], -quaternion[3]),
                    dtype=np.float64)


def quaternion_inverse(quaternion):
    """Return inverse of quaternion.

    Parameters
    ----------
    quaternion : list or np.ndarray
        [w, x, y, z]

    Returns
    -------
    inverse of quaternion : np.ndarray
        [w, x, y, z]

    Examples
    --------
    >>> q0 = random_quaternion()
    >>> q1 = quaternion_inverse(q0)
    >>> np.allclose(quaternion_multiply(q0, q1), [1, 0, 0, 0])
    True
    """
    q = np.array(quaternion, dtype=np.float64)
    return quaternion_conjugate(q) / np.dot(q, q)


def quaternion_slerp(q0, q1, fraction, spin=0, shortestpath=True):
    """Return spherical linear interpolation between two quaternions.

    Parameters
    ----------
    q0 : list or np.ndarray
        start quaternion
    q1 : list or np.ndarray
        end quaternion
    fraction : float
        ratio
    spin : int
        TODO
    shortestpath : bool
        TODO

    Returns
    -------
    quaternion : np.ndarray
        spherical linear interpolated quaternion

    Examples
    --------
    >>> q0 = random_quaternion()
    >>> q1 = random_quaternion()
    >>> q = quaternion_slerp(q0, q1, 0.0)
    >>> numpy.allclose(q, q0)
    True
    >>> q = quaternion_slerp(q0, q1, 1.0, 1)
    >>> numpy.allclose(q, q1)
    True
    >>> q = quaternion_slerp(q0, q1, 0.5)
    >>> angle = math.acos(numpy.dot(q0, q))
    >>> numpy.allclose(2.0, math.acos(numpy.dot(q0, q1)) / angle) or \
        numpy.allclose(2.0, math.acos(-numpy.dot(q0, q1)) / angle)
    True
    """
    q0 = normalize_vector(q0)
    q1 = normalize_vector(q1)
    if fraction == 0.0:
        return q0
    elif fraction == 1.0:
        return q1
    d = np.dot(q0, q1)
    if abs(abs(d) - 1.0) < 0.0:
        return q0
    if shortestpath and d < 0.0:
        # invert rotation
        d = -d
        q1 *= -1.0
    theta = acos(d)
    angle = theta + spin * pi
    if abs(angle) < _EPS:
        return q0
    isin = 1.0 / sin(angle)
    q = (sin((1.0 - fraction) * angle) * q0 +
         sin(fraction * angle) * q1) * isin
    return q


def quaternion_distance(q1, q2, absolute=False):
    """Return the distance of quaternion.

    Parameters
    ----------
    q1 : list or np.ndarray
    q2 : list or np.ndarray
        [w, x, y, z] order
    absolute : bool
        if True, return distance accounting for the sign ambiguity.

    Returns
    -------
    diff_theta : float
        distance of q1 and q2 in radian.

    Examples
    --------
    >>> from skrobot.coordinates.math import quaternion_distance
    >>> quaternion_distance([1, 0, 0, 0], [1, 0, 0, 0])
    0.0
    >>> quaternion_distance([1, 0, 0, 0], [0, 1, 0, 0])
    3.141592653589793
    >>> distance = quaternion_distance(
            [1, 0, 0, 0],
            [0.8660254, 0, 0.5, 0])
    >>> np.rad2deg(distance)
    60.00000021683236
    """
    q = quaternion_multiply(
        quaternion_inverse(q1), q2)
    w = q[0]
    if absolute is True:
        w = abs(q[0])
    diff_theta = 2.0 * np.arctan2(
        np.linalg.norm(q[1:]), w)
    return diff_theta


def quaternion_absolute_distance(q1, q2):
    """Return the absolute distance of quaternion.

    Parameters
    ----------
    q1 : list or np.ndarray
    q2 : list or np.ndarray
        [w, x, y, z] order

    Returns
    -------
    diff_theta : float
        absolute distance of q1 and q2 in radian.

    Examples
    --------
    >>> from skrobot.coordinates.math import quaternion_absolute_distance
    >>> quaternion_absolute_distance([1, 0, 0, 0], [1, 0, 0, 0])
    0.0
    >>> quaternion_absolute_distance(
            [1, 0, 0, 0],
            [0, 0.7071067811865476, 0, 0.7071067811865476])
    3.141592653589793
    >>> quaternion_absolute_distance(
            [-1, 0, 0, 0],
            [0, 0.7071067811865476, 0, 0.7071067811865476])
    """
    return quaternion_distance(q1, q2, True)


def quaternion_norm(q):
    """Return the norm of quaternion.

    Parameters
    ----------
    q : list or np.ndarray
        [w, x, y, z] order

    Returns
    -------
    norm_q : float
        quaternion norm of q

    Examples
    --------
    >>> from skrobot.coordinates.math import quaternion_norm
    >>> q = [1, 1, 1, 1]
    >>> quaternion_norm(q)
    2.0
    >>> q = [0, 0.7071067811865476, 0, 0.7071067811865476]
    >>> quaternion_norm(q)
    1.0
    """
    q = np.array(q)
    norm_q = np.sqrt(np.dot(q.T, q))
    return norm_q


def quaternion_normalize(q):
    """Return the normalized quaternion.

    Parameters
    ----------
    q : list or np.ndarray
        [w, x, y, z] order

    Returns
    -------
    normalized_q : np.ndarray
        normalized quaternion

    Examples
    --------
    >>> from skrobot.coordinates.math import quaternion_normalize
    >>> from skrobot.coordinates.math import quaternion_norm
    >>> q = quaternion_normalize([1, 1, 1, 1])
    >>> quaternion_norm(q)
    1.0
    """
    q = np.array(q)
    normalized_q = q / quaternion_norm(q)
    return normalized_q


def quaternion_from_axis_angle(theta, axis):
    """Return the quaternion from axis angle

    This function returns quaternion associated with counterclockwise
    rotation about the given axis by theta radians.

    Parameters
    ----------
    theta : float
        radian
    axis : list or np.ndarray
        length is 3. Automatically normalize in this function

    Returns
    -------
    quaternion : np.ndarray
        [w, x, y, z] order

    Examples
    --------
    >>> import numpy
    >>> from skrobot.coordinates.math import quaternion_from_axis_angle
    >>> quaternion_from_axis_angle(0.1, [1, 0, 0])
    array([0.99875026, 0.04997917, 0.        , 0.        ])
    >>> quaternion_from_axis_angle(numpy.pi, [1, 0, 0])
    array([6.123234e-17, 1.000000e+00, 0.000000e+00, 0.000000e+00])
    >>> quaternion_from_axis_angle(0, [1, 0, 0])
    array([1., 0., 0., 0.])
    >>> quaternion_from_axis_angle(numpy.pi, [1, 0, 1])
    array([6.12323400e-17, 7.07106781e-01, 0.00000000e+00, 7.07106781e-01])
    """
    axis = normalize_vector(axis)
    s = sin(theta / 2)
    x = axis[0] * s
    y = axis[1] * s
    z = axis[2] * s
    w = cos(theta / 2)
    return np.array([w, x, y, z], dtype=np.float64)


def axis_angle_from_quaternion(quat):
    """Converts a quaternion into the axis-angle representation.

    Parameters
    ----------
    quat : np.ndarray
        quaternion [w, x, y, z]

    Returns
    -------
    axis_angle : np.ndarray
        axis-angle representation of vector

    Examples
    --------
    >>> from skrobot.coordinates.math import axis_angle_from_quaternion
    >>> axis_angle_from_quaternion([1, 0, 0, 0])
    array([0, 0, 0])
    >>> axis_angle_from_quaternion([0, 7.07106781e-01, 0, 7.07106781e-01])
    array([2.22144147, 0.        , 2.22144147])
    """
    quat = np.array(quat, dtype=np.float64)
    x, y, z, w = quat
    sinang = y ** 2 + z ** 2 + w ** 2
    if sinang == 0:
        return np.array([0, 0, 0])
    if x < 0:
        _quat = - quat
    else:
        _quat = quat
    sinang = np.sqrt(sinang)
    f = 2.0 * np.arctan2(sinang, _quat[0]) / sinang
    return f * np.array([_quat[1], _quat[2], _quat[3]])


def axis_angle_from_matrix(rotation):
    """Converts the rotation of a matrix into axis-angle representation.

    Parameters
    ----------
    rotation : np.ndarray
        3x3 rotation matrix

    Returns
    -------
    axis_angle : np.ndarray
        axis-angle representation of vector

    Examples
    --------
    >>> import numpy
    >>> from skrobot.coordinates.math import axis_angle_from_matrix
    >>> axis_angle_from_matrix(numpy.eye(3))
    array([0, 0, 0])
    >>> axis_angle_from_matrix(
        numpy.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]]))
    array([0.        , 1.57079633, 0.        ])
    """
    return axis_angle_from_quaternion(quat_from_rotation_matrix(rotation))


def random_rotation():
    """Generates a random 3x3 rotation matrix.

    Returns
    -------
    rot : numpy.ndarray
        randomly generated 3x3 rotation matrix

    Examples
    --------
    >>> from skrobot.coordinates.math import random_rotation
    >>> random_rotation()
    array([[-0.00933428, -0.90465681, -0.42603865],
          [-0.50305571, -0.36396787,  0.78387648],
          [-0.86420358,  0.2216381 , -0.4516954 ]])
    >>> random_rotation()
    array([[-0.6549113 ,  0.09499001, -0.749712  ],
          [-0.47962794, -0.81889635,  0.31522342],
          [-0.58399334,  0.5660262 ,  0.58186434]])
    """
    rot = quaternion2matrix(random_quaternion())
    return rot


def random_translation():
    """Generates a random translation vector.

    Returns
    -------
    translation : numpy.ndarray
        A 3-entry random translation vector.

    Examples
    --------
    >>> from skrobot.coordinates.math import random_translation
    >>> random_translation()
    array([0.03299473, 0.81481471, 0.57782565])
    >>> random_translation()
    array([0.10835455, 0.46549158, 0.73277675])
    """
    return np.random.rand(3)


def random_quaternion():
    """Generate uniform random unit quaternion.

    Returns
    -------
    quaternion : np.ndarray
        generated random unit quaternion [w, x, y, z]

    Examples
    --------
    >>> from skrobot.coordinates.math import random_quaternion
    >>> random_quaternion()
    array([-0.02156994,  0.5404561 , -0.72781116, -0.42158374])
    >>> random_quaternion()
    array([-0.47302116,  0.020306  , -0.37539238,  0.79681818])
    >>> from skrobot.coordinates.math import quaternion_norm
    >>> q = random_quaternion()
    >>> numpy.allclose(1.0, quaternion_norm(q))
    True
    >>> q.shape
    (4,)
    """
    rand = np.random.rand(3)
    r1 = np.sqrt(1.0 - rand[0])
    r2 = np.sqrt(rand[0])
    pi2 = np.pi * 2.0
    t1 = pi2 * rand[1]
    t2 = pi2 * rand[2]
    return np.array((cos(t2) * r2,
                     sin(t1) * r1,
                     cos(t1) * r1,
                     sin(t2) * r2),
                    dtype=np.float64)


def make_matrix(r, c):
    """Wrapper of numpy array."""
    return np.zeros((r, c), 'f')


inverse_rodrigues = rotation_angle
quat_from_rotation_matrix = matrix2quaternion
quat_from_rpy = rpy2quaternion
rotation_matrix_from_quat = quaternion2matrix
rpy_from_quat = quaternion2rpy