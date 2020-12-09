import contextlib
import copy
import warnings

import numpy as np

from skrobot.coordinates.dual_quaternion import DualQuaternion
from skrobot.coordinates.math import _check_valid_rotation
from skrobot.coordinates.math import _check_valid_translation
from skrobot.coordinates.math import _wrap_axis
from skrobot.coordinates.math import angle_between_vectors
from skrobot.coordinates.math import cross_product
from skrobot.coordinates.math import matrix2quaternion
from skrobot.coordinates.math import matrix_log
from skrobot.coordinates.math import normalize_vector
from skrobot.coordinates.math import quaternion2matrix
from skrobot.coordinates.math import quaternion_multiply
from skrobot.coordinates.math import quaternion_normalize
from skrobot.coordinates.math import random_rotation
from skrobot.coordinates.math import random_translation
from skrobot.coordinates.math import rotate_matrix
from skrobot.coordinates.math import rotation_angle
from skrobot.coordinates.math import rotation_matrix
from skrobot.coordinates.math import rpy2quaternion
from skrobot.coordinates.math import rpy_angle


def transform_coords(c1, c2, out=None):
    """Return Coordinates by applying c1 to c2 from the left

    Parameters
    ----------
    c1 : skrobot.coordinates.Coordinates
    c2 : skrobot.coordinates.Coordinates
        Coordinates
    c3 : skrobot.coordinates.Coordinates or None
        Output argument. If this value is specified, the results will be
        in-placed.

    Returns
    -------
    Coordinates(pos=translation, rot=q) : skrobot.coordinates.Coordinates
        new coordinates

    Examples
    --------
    >>> from skrobot.coordinates import Coordinates
    >>> from skrobot.coordinates import transform_coords
    >>> from numpy import pi
    >>> c1 = Coordinates()
    >>> c2 = Coordinates()
    >>> c3 = transform_coords(c1, c2)
    >>> c3.translation
    array([0., 0., 0.])
    >>> c3.rotation
    array([[1., 0., 0.],
           [0., 1., 0.],
           [0., 0., 1.]])
    >>> c1 = Coordinates().translate([0.1, 0.2, 0.3]).rotate(pi / 3.0, 'x')
    >>> c2 = Coordinates().translate([0.3, -0.3, 0.1]).rotate(pi / 2.0, 'y')
    >>> c3 = transform_coords(c1, c2)
    >>> c3.translation
    array([ 0.4       , -0.03660254,  0.09019238])
    >>> c3.rotation
    >>> c3.rotation
    array([[ 1.94289029e-16,  0.00000000e+00,  1.00000000e+00],
           [ 8.66025404e-01,  5.00000000e-01, -1.66533454e-16],
           [-5.00000000e-01,  8.66025404e-01,  2.77555756e-17]])
    """
    if out is None:
        out = Coordinates(check_valid=False)
    elif not isinstance(out, Coordinates):
        raise TypeError("Input type should be skrobot.coordinates.Coordinates")
    out._translation = c1.translation + np.dot(c1.rotation, c2.translation)
    out._rotation = np.dot(c1.rotation, c2.rotation)
    # out.rotation = quaternion_normalize(
    #     quaternion_multiply(c1.quaternion, c2.quaternion))
    return out


class Coordinates(object):

    """Coordinates class to manipulate rotation and translation.

    Parameters
    ----------
    pos : list or numpy.ndarray
        shape of (3,) translation vector. or
        4x4 homogeneous transformation matrix.
        If the homogeneous transformation matrix is given,
        `rot` will be overwritten.
    rot : list or numpy.ndarray
        we can take 3x3 rotation matrix or
        [yaw, pitch, roll] or
        quaternion [w, x, y, z] order
    name : string or None
        name of this coordinates
    """

    def __init__(self,
                 pos=[0, 0, 0],
                 rot=np.eye(3),
                 name=None,
                 hook=None,
                 check_valid=True):
        if check_valid:
            if (isinstance(pos, list) or isinstance(pos, np.ndarray)):
                T = np.array(pos, dtype=np.float64)
                if T.shape == (4, 4):
                    pos = T[:3, 3]
                    rot = T[:3, :3]
            self.rotation = rot
            self.translation = pos
        else:
            self._rotation = rot
            self._translation = pos
        if name is None:
            name = ''
        self.name = name
        self.parent = None
        self._hook = hook if hook else lambda: None

    @contextlib.contextmanager
    def disable_hook(self):
        hook = self._hook
        self._hook = lambda: None
        try:
            yield
        finally:
            self._hook = hook

    @property
    def rotation(self):
        """Return rotation matrix of this coordinates.

        Returns
        -------
        self._rotation : np.ndarray
            3x3 rotation matrix

        Examples
        --------
        >>> import numpy as np
        >>> from skrobot.coordinates import Coordinates
        >>> c = Coordinates()
        >>> c.rotation
        array([[1., 0., 0.],
               [0., 1., 0.],
               [0., 0., 1.]])
        >>> c.rotate(np.pi / 2.0, 'y')
        >>> c.rotation
        array([[ 2.22044605e-16,  0.00000000e+00,  1.00000000e+00],
               [ 0.00000000e+00,  1.00000000e+00,  0.00000000e+00],
               [-1.00000000e+00,  0.00000000e+00,  2.22044605e-16]])
        """
        self._hook()
        return self._rotation

    @rotation.setter
    def rotation(self, rotation):
        """Set rotation of this coordinate

        This setter checkes the given rotation and set it this coordinate.

        Parameters
        ----------
        rotation : list or np.ndarray
            we can take 3x3 rotation matrix or
            rpy angle [yaw, pitch, roll] or
            quaternion [w, x, y, z] order
        """
        rotation = np.array(rotation)
        # Convert quaternions
        if rotation.shape == (4,):
            self._q = np.array([q for q in rotation])
            if np.abs(np.linalg.norm(self._q) - 1.0) > 1e-3:
                raise ValueError('Invalid quaternion. Must be '
                                 'norm 1.0, get {}'.
                                 format(np.linalg.norm(self._q)))
            rotation = quaternion2matrix(self._q)
        elif rotation.shape == (3,):
            # Convert [yaw-pitch-roll] to rotation matrix
            self._q = rpy2quaternion(rotation)
            rotation = quaternion2matrix(self._q)
        else:
            pass
            # self._q = matrix2quaternion(rotation)

        # Convert lists and tuples
        if type(rotation) in (list, tuple):
            rotation = np.array(rotation).astype(np.float32)

        _check_valid_rotation(rotation)
        self._rotation = rotation * 1.

    @property
    def translation(self):
        """Return translation of this coordinates.

        Returns
        -------
        self._translation : np.ndarray
            vector shape of (3, ). unit is [m]

        Examples
        --------
        >>> from skrobot.coordinates import Coordinates
        >>> c = Coordinates()
        >>> c.translation
        array([0., 0., 0.])
        >>> c.translate([0.1, 0.2, 0.3])
        >>> c.translation
        array([0.1, 0.2, 0.3])
        """
        self._hook()
        return self._translation

    @translation.setter
    def translation(self, translation):
        """Set translation of this coordinate

        This setter checkes the given translation and set it this coordinate.

        Parameters
        ----------
        translation : list or tuple or np.ndarray
            shape of (3,) translation vector
        """
        # Convert lists to translation arrays
        if type(translation) in (list, tuple) and len(translation) == 3:
            translation = np.array([t for t in translation]).astype(np.float64)

        _check_valid_translation(translation)
        self._translation = translation.squeeze() * 1.

    @property
    def name(self):
        """Return this coordinate's name

        Returns
        -------
        self._name : string
            name of this coordinate
        """
        return self._name

    @name.setter
    def name(self, name):
        """Setter of this coordinate's name

        Parameters
        ----------
        name : string
            name of this coordinate
        """
        if not isinstance(name, str):
            raise TypeError('name should be string, get {}'.
                            format(type(name)))
        self._name = name

    @property
    def dimension(self):
        """Return dimension of this coordinate

        Returns
        -------
        len(self.translation) : int
            dimension of this coordinate
        """
        return len(self.translation)

    def changed(self):
        """Return False

        This is used for CascadedCoords compatibility

        Returns
        -------
        False : bool
            always return False
        """
        return False

    def translate(self, vec, wrt='local'):
        """Translate this coordinates.

        Note that this function changes this coordinates self.
        So if you don't want to change this class, use copy_worldcoords()

        Parameters
        ----------
        vec : list or np.ndarray
            shape of (3,) translation vector. unit is [m] order.
        wrt : string or Coordinates (optional)
            translate with respect to wrt.

        Examples
        --------
        >>> import numpy as np
        >>> from skrobot.coordinates import Coordinates
        >>> c = Coordinates()
        >>> c.translation
        array([0., 0., 0.], dtype=float32)
        >>> c.translate([0.1, 0.2, 0.3])
        >>> c.translation
        array([0.1, 0.2, 0.3], dtype=float32)

        >>> c = Coordinates()
        >>> c.copy_worldcoords().translate([0.1, 0.2, 0.3])
        >>> c.translation
        array([0., 0., 0.], dtype=float32)

        >>> c = Coordinates().rotate(np.pi / 2.0, 'y')
        >>> c.translate([0.1, 0.2, 0.3])
        >>> c.translation
        array([ 0.3,  0.2, -0.1])
        >>> c = Coordinates().rotate(np.pi / 2.0, 'y')
        >>> c.translate([0.1, 0.2, 0.3], 'world')
        >>> c.translation
        array([0.1, 0.2, 0.3])
        """
        vec = np.array(vec, dtype=np.float64)
        return self.newcoords(
            self.rotation,
            self.parent_orientation(vec, wrt) + self.translation)

    def transform_vector(self, v):
        """"Return vector represented at world frame.

        Vector v given in the local coords is converted to world
        representation.

        Parameters
        ----------
        v : numpy.ndarray
            3d vector.
            We can take batch of vector like (batch_size, 3)
        Returns
        -------
        transformed_point : numpy.ndarray
            transformed point
        """
        v = np.array(v, dtype=np.float64)
        if v.ndim == 2:
            return (np.matmul(self.rotation, v.T)
                    + self.translation.reshape(3, -1)).T
        return np.matmul(self.rotation, v) + self.translation

    def inverse_transform_vector(self, vec):
        """Transform vector in world coordinates to local coordinates

        Parameters
        ----------
        vec : numpy.ndarray
            3d vector.
            We can take batch of vector like (batch_size, 3)
        Returns
        -------
        transformed_point : numpy.ndarray
            transformed point
        """
        vec = np.array(vec, dtype=np.float64)
        if vec.ndim == 2:
            return (np.matmul(self.rotation.T, vec.T)
                    - np.matmul(
                        self.rotation.T, self.translation).reshape(3, -1)).T
        return np.matmul(self.rotation.T, vec) - \
            np.matmul(self.rotation.T, self.translation)

    def inverse_transformation(self, dest=None):
        """Return a invese transformation of this coordinate system.

        Create a new coordinate with inverse transformation of this
        coordinate system.

        .. math::
            \\left(
                \\begin{array}{ccc}
                  R^{-1} & - R^{-1} p  \\\\
                  0 & 1
                \\end{array}
            \\right)

        Parameters
        ----------
        dest : None or skrobot.coordinates.Coordinates
            If dest is given, the result of transformation
            is in-placed to dest.

        Returns
        -------
        dest : skrobot.coordinates.Coordinates
            result of inverse transformation.
        """
        if dest is None:
            dest = Coordinates()
        dest.rotation = self.rotation.T
        dest.translation = np.matmul(dest.rotation, self.translation)
        dest.translation = -1.0 * dest.translation
        return dest

    def transformation(self, c2, wrt='local'):
        c2 = c2.worldcoords()
        c1 = self.worldcoords()
        inv = c1.inverse_transformation()
        if wrt == 'local' or wrt == self:
            transform_coords(inv, c2, inv)
        elif wrt == 'parent' or \
                wrt == self.parent or \
                wrt == 'world':
            transform_coords(c2, inv, inv)
        elif isinstance(wrt, Coordinates):
            xw = wrt.worldcoords()
            transform_coords(c2, inv, inv)
            transform_coords(xw.inverse_transformation(), inv, inv)
            transform_coords(inv, xw, inv)
        else:
            raise ValueError('wrt {} not supported'.format(wrt))
        return inv

    def T(self):
        """Return 4x4 homogeneous transformation matrix.

        Returns
        -------
        matrix : np.ndarray
            homogeneous transformation matrix shape of (4, 4)

        Examples
        --------
        >>> from numpy import pi
        >>> from skrobot.coordinates import make_coords
        >>> c = make_coords()
        >>> c.T()
        array([[1., 0., 0., 0.],
               [0., 1., 0., 0.],
               [0., 0., 1., 0.],
               [0., 0., 0., 1.]])
        >>> c.translate([0.1, 0.2, 0.3])
        >>> c.rotate(pi / 2.0, 'y')
        array([[ 2.22044605e-16,  0.00000000e+00,  1.00000000e+00,
                 1.00000000e-01],
               [ 0.00000000e+00,  1.00000000e+00,  0.00000000e+00,
                 2.00000000e-01],
               [-1.00000000e+00,  0.00000000e+00,  2.22044605e-16,
                 3.00000000e-01],
               [ 0.00000000e+00,  0.00000000e+00,  0.00000000e+00,
                 1.00000000e+00]])
        """
        matrix = np.zeros((4, 4), dtype=np.float64)
        matrix[3, 3] = 1.0
        matrix[:3, :3] = self.rotation
        matrix[:3, 3] = self.translation
        return matrix

    @property
    def quaternion(self):
        """Property of quaternion

        Returns
        -------
        self._q : np.ndarray
            [w, x, y, z] quaternion

        Examples
        --------
        >>> from numpy import pi
        >>> from skrobot.coordinates import make_coords
        >>> c = make_coords()
        >>> c.quaternion
        array([1., 0., 0., 0.])
        >>> c.rotate(pi / 3, 'y').rotate(pi / 5, 'z')
        >>> c.quaternion
        array([0.8236391 , 0.1545085 , 0.47552826, 0.26761657])
        """
        return matrix2quaternion(self.rotation)
        # return self._q

    @property
    def dual_quaternion(self):
        """Property of DualQuaternion

        Return DualQuaternion representation of this coordinate.

        Returns
        -------
        DualQuaternion : skrobot.coordinates.dual_quaternion.DualQuaternion
            DualQuaternion representation of this coordinate
        """
        qr = normalize_vector(self.quaternion)
        x, y, z = self.translation
        qd = quaternion_multiply(np.array([0, x, y, z]), qr) * 0.5
        return DualQuaternion(qr, qd)

    def parent_orientation(self, v, wrt):
        if wrt == 'local' or wrt == self:
            return np.matmul(self.rotation, v)
        if wrt == 'parent' \
           or wrt == self.parent \
           or wrt == 'world':
            return v
        if coordinates_p(wrt):
            return np.matmul(wrt.worldrot(), v)
        raise ValueError('wrt {} not supported'.format(wrt))

    def rotate_vector(self, v):
        """Rotate 3-dimensional vector using rotation of this coordinate

        Parameters
        ----------
        v : np.ndarray
            vector shape of (3,)

        Returns:
        np.matmul(self.rotation, v) : np.ndarray
            rotated vector

        Examples
        --------
        >>> from skrobot.coordinates import Coordinates
        >>> from numpy import pi
        >>> c = Coordinates().rotate(pi, 'z')
        >>> c.rotate_vector([1, 2, 3])
        array([-1., -2.,  3.])
        """
        return np.matmul(self.rotation, v)

    def inverse_rotate_vector(self, v):
        return np.matmul(v, self.rotation)

    def transform(self, c, wrt='local'):
        """Transform this coordinate by coords based on wrt

        Note that this function changes this coordinate's
        translation and rotation.
        If you would like not to change this coordinate,
        Please use copy_worldcoords()

        Parameters
        ----------
        c : skrobot.coordinates.Coordinates
            coordinate
        wrt : string or skrobot.coordinates.Coordinates
            If wrt is 'local' or self, multiply c from the right.
            If wrt is 'world' or 'parent' or self.parent,
            transform c with respect to worldcoord.
            If wrt is Coordinates, transform c with respect to c.

        Returns
        -------
        self : skrobot.coordinates.Coordinates
            return this coordinate

        Examples
        --------
        """
        if wrt == 'local' or wrt == self:
            # multiply c from the right
            transform_coords(self, c, self)
        elif wrt == 'parent' or wrt == self.parent \
                or wrt == 'world':
            # multiply c from the left
            transform_coords(c, self, self)
        elif isinstance(wrt, Coordinates):
            transform_coords(wrt.inverse_transformation(), self, self)
            transform_coords(c, self, self)
            transform_coords(wrt.worldcoords(), self, self)
        else:
            raise ValueError('transform wrt {} is not supported'.format(wrt))
        return self

    def move_coords(self, target_coords, local_coords):
        """Transform this coordinate so that local_coords to target_coords.

        Parameters
        ----------
        target_coords : skrobot.coordinates.Coordinates
            target coords.
        local_coords : skrobot.coordinates.Coordinates
            local coords to be aligned.

        Returns
        -------
        self.worldcoords() : skrobot.coordinates.Coordinates
            world coordinates.
        """
        self.transform(
            local_coords.transformation(target_coords), local_coords)
        return self.worldcoords()

    def rpy_angle(self):
        """Return a pair of rpy angles of this coordinates.

        Returns
        -------
        rpy_angle(self.rotation) : tuple of np.ndarray
            a pair of rpy angles. See also skrobot.coordinates.math.rpy_angle

        Examples
        --------
        >>> import numpy as np
        >>> from skrobot.coordinates import Coordinates
        >>> c = Coordinates().rotate(np.pi / 2.0, 'x').rotate(np.pi / 3.0, 'z')
        >>> r.rpy_angle()
        (array([ 3.84592537e-16, -1.04719755e+00,  1.57079633e+00]),
        array([ 3.14159265, -2.0943951 , -1.57079633]))
        """
        return rpy_angle(self.rotation)

    def axis(self, ax):
        ax = _wrap_axis(ax)
        return self.rotate_vector(ax)

    def difference_position(self, coords,
                            translation_axis=True):
        """Return differences in positoin of given coords.

        Parameters
        ----------
        coords : skrobot.coordinates.Coordinates
            given coordinates
        translation_axis : str or bool or None (optional)
            we can take 'x', 'y', 'z', 'xy', 'yz', 'zx', 'xx', 'yy', 'zz',
            True or False(None).

        Returns
        -------
        dif_pos : numpy.ndarray
            difference position of self coordinates and coords
            considering translation_axis.

        Examples
        --------
        >>> from skrobot.coordinates import Coordinates
        >>> from skrobot.coordinates import transform_coords
        >>> from numpy import pi
        >>> c1 = Coordinates().translate([0.1, 0.2, 0.3]).rotate(
        ...          pi / 3.0, 'x')
        >>> c2 = Coordinates().translate([0.3, -0.3, 0.1]).rotate(
        ...          pi / 2.0, 'y')
        >>> c1.difference_position(c2)
        array([ 0.2       , -0.42320508,  0.3330127 ])
        >>> c1 = Coordinates().translate([0.1, 0.2, 0.3]).rotate(0, 'x')
        >>> c2 = Coordinates().translate([0.3, -0.3, 0.1]).rotate(
        ...          pi / 3.0, 'x')
        >>> c1.difference_position(c2)
        array([ 0.2, -0.5, -0.2])
        """
        dif_pos = self.inverse_transform_vector(coords.worldpos())
        translation_axis = _wrap_axis(translation_axis)
        dif_pos[translation_axis == 1] = 0.0
        return dif_pos

    def difference_rotation(self, coords,
                            rotation_axis=True):
        """Return differences in rotation of given coords.

        Parameters
        ----------
        coords : skrobot.coordinates.Coordinates
            given coordinates
        rotation_axis : str or bool or None (optional)
            we can take 'x', 'y', 'z', 'xx', 'yy', 'zz', 'xm', 'ym', 'zm',
            'xy', 'yx', 'yz', 'zy', 'zx', 'xz', True or False(None).

        Returns
        -------
        dif_rot : numpy.ndarray
            difference rotation of self coordinates and coords
            considering rotation_axis.

        Examples
        --------
        >>> from numpy import pi
        >>> from skrobot.coordinates import Coordinates
        >>> from skrobot.coordinates.math import rpy_matrix
        >>> coord1 = Coordinates()
        >>> coord2 = Coordinates(rot=rpy_matrix(pi / 2.0, pi / 3.0, pi / 5.0))
        >>> coord1.difference_rotation(coord2)
        array([-0.32855112,  1.17434985,  1.05738936])
        >>> coord1.difference_rotation(coord2, rotation_axis=False)
        array([0, 0, 0])
        >>> coord1.difference_rotation(coord2, rotation_axis='x')
        array([0.        , 1.36034952, 0.78539816])
        >>> coord1.difference_rotation(coord2, rotation_axis='y')
        array([0.35398131, 0.        , 0.97442695])
        >>> coord1.difference_rotation(coord2, rotation_axis='z')
        array([-0.88435715,  0.74192175,  0.        ])

        Using mirror option ['xm', 'ym', 'zm'], you can
        allow differences of mirror direction.

        >>> coord1 = Coordinates()
        >>> coord2 = Coordinates().rotate(pi, 'x')
        >>> coord1.difference_rotation(coord2, 'xm')
        array([-2.99951957e-32,  0.00000000e+00,  0.00000000e+00])
        >>> coord1 = Coordinates()
        >>> coord2 = Coordinates().rotate(pi / 2.0, 'x')
        >>> coord1.difference_rotation(coord2, 'xm')
        array([-1.57079633,  0.        ,  0.        ])
        """
        def need_mirror_for_nearest_axis(coords0, coords1, ax):
            a0 = coords0.axis(ax)
            a1 = coords1.axis(ax)
            a1_mirror = - a1
            dr1 = angle_between_vectors(a0, a1, normalize=False) \
                * normalize_vector(cross_product(a0, a1))
            dr1m = angle_between_vectors(a0, a1_mirror, normalize=False) \
                * normalize_vector(cross_product(a0, a1_mirror))
            return np.linalg.norm(dr1) < np.linalg.norm(dr1m)

        if rotation_axis in ['x', 'y', 'z']:
            a0 = self.axis(rotation_axis)
            a1 = coords.axis(rotation_axis)
            if np.abs(np.linalg.norm(np.array(a0) - np.array(a1))) < 0.001:
                dif_rot = np.array([0, 0, 0], 'f')
            else:
                dif_rot = np.matmul(
                    self.worldrot().T,
                    angle_between_vectors(a0, a1, normalize=False)
                    * normalize_vector(cross_product(a0, a1)))
        elif rotation_axis in ['xx', 'yy', 'zz']:
            ax = rotation_axis[0]
            a0 = self.axis(ax)
            a2 = coords.axis(ax)
            if not need_mirror_for_nearest_axis(self, coords, ax):
                a2 = - a2
            dif_rot = np.matmul(
                self.worldrot().T,
                angle_between_vectors(a0, a2, normalize=False)
                * normalize_vector(cross_product(a0, a2)))
        elif rotation_axis in ['xy', 'yx', 'yz', 'zy', 'zx', 'xz']:
            if rotation_axis in ['xy', 'yx']:
                ax1 = 'z'
                ax2 = 'x'
            elif rotation_axis in ['yz', 'zy']:
                ax1 = 'x'
                ax2 = 'y'
            else:
                ax1 = 'y'
                ax2 = 'z'
            a0 = self.axis(ax1)
            a1 = coords.axis(ax1)
            dif_rot = np.matmul(
                self.worldrot().T,
                angle_between_vectors(a0, a1, normalize=False)
                * normalize_vector(cross_product(a0, a1)))
            norm = np.linalg.norm(dif_rot)
            if np.isclose(norm, 0.0):
                self_coords = self.copy_worldcoords()
            else:
                self_coords = self.copy_worldcoords().rotate(norm, dif_rot)
            a0 = self_coords.axis(ax2)
            a1 = coords.axis(ax2)
            dif_rot = np.matmul(
                self_coords.worldrot().T,
                angle_between_vectors(a0, a1, normalize=False)
                * normalize_vector(cross_product(a0, a1)))
        elif rotation_axis in ['xm', 'ym', 'zm']:
            rot = coords.worldrot()
            ax = rotation_axis[0]
            if not need_mirror_for_nearest_axis(self, coords, ax):
                rot = rotate_matrix(rot, np.pi, ax)
            dif_rot = matrix_log(np.matmul(self.worldrot().T, rot))
        elif rotation_axis is False or rotation_axis is None:
            dif_rot = np.array([0, 0, 0])
        elif rotation_axis is True:
            dif_rotmatrix = np.matmul(self.worldrot().T,
                                      coords.worldrot())
            dif_rot = matrix_log(dif_rotmatrix)
        else:
            raise ValueError
        return dif_rot

    def rotate_with_matrix(self, mat, wrt='local'):
        """Rotate this coordinate by given rotation matrix.

        This is a subroutine of self.rotate function.

        Parameters
        ----------
        mat : np.ndarray
            rotation matrix shape of (3, 3)
        wrt : string or skrobot.coordinates.Coordinates

        Returns
        -------
        self : skrobot.coordinates.Coordinates
        """
        if wrt == 'local' or wrt == self:
            rot = np.matmul(self.rotation, mat)
            self.newcoords(rot, self.translation)
        elif wrt == 'parent' or wrt == self.parent or \
                wrt == 'world' or wrt is None or \
                wrt == worldcoords:
            rot = np.matmul(mat, self.rotation)
            self.newcoords(rot, self.translation)
        elif isinstance(wrt, Coordinates):
            r2 = wrt.worldrot()
            r2t = r2.T
            r2t = np.matmul(mat, r2t)
            r2t = np.matmul(r2, r2t)
            self.rotation = np.matmul(r2t, self.rotation)
        else:
            raise ValueError('wrt {} is not supported'.format(wrt))
        return self

    def rotate(self, theta, axis=None, wrt='local'):
        """Rotate this coordinate by given theta and axis.

        This coordinate system is rotated relative to theta radians
        around the `axis` axis.
        Note that this function does not change a position of this coordinate.
        If you want to rotate this coordinates around with world frame,
        you can use `transform` function.
        Please see examples.

        Parameters
        ----------
        theta : float
            relartive rotation angle in radian.
        axis : str or None or numpy.ndarray
            axis of rotation.
            The value of `axis` is represented as `wrt` frame.
        wrt : string or skrobot.coordinates.Coordinates

        Returns
        -------
        self : skrobot.coordinates.Coordinates

        Examples
        --------
        >>> from skrobot.coordinates import Coordinates
        >>> from numpy import pi
        >>> c = Coordinates()
        >>> c.translate((1.0, 0, 0))
        >>> c.rotate(pi / 2.0, 'z', wrt='local')
        >>> c.translation
        array([1., 0., 0.])

        >>> c.transform(Coordinates().rotate(np.pi / 2.0, 'z'), wrt='world')
        >>> c.translation
        array([0., 1., 0.])
        """
        if isinstance(axis, list) or isinstance(axis, np.ndarray):
            self.rotate_with_matrix(
                rotation_matrix(theta, axis), wrt)
        elif axis is None or axis is False:
            self.rotate_with_matrix(theta, wrt)
        elif wrt == 'local' or wrt == self:
            self.rotation = rotate_matrix(self.rotation, theta, axis)
        elif wrt == 'parent' or wrt == 'world':
            self.rotation = rotate_matrix(self.rotation, theta,
                                          axis, True)
        elif isinstance(wrt, Coordinates):  # C1'=C2*R*C2(-1)*C1
            self.rotate_with_matrix(
                rotation_matrix(theta, axis), wrt)
        else:
            raise ValueError('wrt {} not supported'.format(wrt))
        return self.newcoords(self.rotation, self.translation)

    def copy(self):
        """Return a deep copy of the Coordinates."""
        return self.copy_coords()

    def copy_coords(self):
        """Return a deep copy of the Coordinates."""
        return Coordinates(pos=np.copy(self.worldpos()),
                           rot=np.copy(self.worldrot()),
                           check_valid=False)

    def coords(self):
        """Return a deep copy of the Coordinates."""
        return self.copy_coords()

    def worldcoords(self):
        """Return thisself"""
        self._hook()
        return self

    def copy_worldcoords(self):
        """Return a deep copy of the Coordinates."""
        return self.coords()

    def worldrot(self):
        """Return rotation of this coordinate

        See also skrobot.coordinates.Coordinates.rotation

        Returns
        -------
        self.rotation : np.ndarray
            rotation matrix of this coordinate
        """
        return self.rotation

    def worldpos(self):
        """Return translation of this coordinate

        See also skrobot.coordinates.Coordinates.translation

        Returns
        -------
        self.translation : np.ndarray
            translation of this coordinate
        """
        return self.translation

    def newcoords(self, c, pos=None):
        """Update of coords is always done through newcoords."""
        if pos is not None:
            # print(c.shape)
            self._rotation = np.copy(c)
            self._translation = np.copy(pos)
        else:
            self._rotation = np.copy(c.rotation)
            self._translation = np.copy(c.translation)
        return self

    def __mul__(self, other_c):
        """Return Transformed Coordinates.

        Note that this function creates new Coordinates and
        does not change translation and rotation, unlike transform function.

        Parameters
        ----------
        other_c : skrobot.coordinates.Coordinates
            input coordinates.

        Returns
        -------
        out : skrobot.coordinates.Coordinates
            transformed coordinates multiplied other_c from the right.
            T = T_{self} T_{other_c}.
        """
        return transform_coords(self, other_c)

    def __pow__(self, exponent):
        """Return exponential homogeneous matrix.

        If exponent equals -1, return inverse transformation of this coords.

        Parameters
        ----------
        exponent : numbers.Number
            exponent value.
            If exponent equals -1, return inverse transformation of this
            coords.
            In current, support only -1 case.

        Returns
        -------
        out : skrobot.coordinates.Coordinates
            output.
        """
        if np.isclose(exponent, -1):
            return self.inverse_transformation()
        raise NotImplementedError

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        self.worldrot()
        pos = self.worldpos()
        self.rpy = rpy_angle(self.rotation)[0]
        if self.name:
            prefix = self.__class__.__name__ + ':' + self.name
        else:
            prefix = self.__class__.__name__

        return "#<{0} {1} "\
            "{2:.3f} {3:.3f} {4:.3f} / {5:.1f} {6:.1f} {7:.1f}>".\
            format(prefix,
                   hex(id(self)),
                   pos[0],
                   pos[1],
                   pos[2],
                   self.rpy[0],
                   self.rpy[1],
                   self.rpy[2])


class CascadedCoords(Coordinates):

    def __init__(self, parent=None, *args, **kwargs):
        super(CascadedCoords, self).__init__(*args, **kwargs)
        self.manager = self
        self._changed = True
        self._descendants = []

        self._worldcoords = Coordinates(pos=self.translation,
                                        rot=self.rotation,
                                        hook=self.update)

        self.parent = parent
        if parent is not None:
            # Because we must self.parent = parent in this case,
            # force=True is required.
            parent.assoc(self, force=True)

    @property
    def descendants(self):
        return self._descendants

    def assoc(self, child, relative_coords=None, force=False,
              **kwargs):
        """Associate child coords to this coordinate.

        If `relative_coords` is `None`, the translation and rotation
        of childcoord in the world coordinate system do not change.
        If `relative_coords` is specified, childcoord is assoced
        at translation and rotation of `relative_coords`.
        By default, if child is already assoced to some other coords,
        raise an exception. But if `force` is `True`, you can overwrite
        the existing assoc relation.

        Parameters
        ----------
        child : CascadedCoords
            child coordinate.
        relative_coords : None or Coordinates
            child coordinate's relative coordinate.
        force : bool
            predicate for overwriting the existing assoc-relation

        Returns
        -------
        child : CascadedCoords
            assoced child.
        """
        if 'c' in kwargs:
            warnings.warn(
                'Argument `c` is deprecated. '
                'Please use `relative_coords` instead',
                DeprecationWarning)
            relative_coords = kwargs['c']

        is_invalid_assoc = (child.parent is not None) and (not force)
        if is_invalid_assoc:
            msg = "child already has an assoc relation with '{0}'."\
                " To overwrite this, please specify force=True."\
                .format(child.parent.name)
            raise RuntimeError(msg)

        if not (child in self.descendants):
            if relative_coords is None:
                relative_coords = self.worldcoords().transformation(
                    child.worldcoords())
            child.parent = self
            child.newcoords(relative_coords)
            self._descendants.append(child)
            return child

    def dissoc(self, child):
        if child in self.descendants:
            c = child.worldcoords().copy_coords()
            self._descendants.remove(child)
            child.parent = None
            child.newcoords(c)

    def newcoords(self, c, pos=None):
        super(CascadedCoords, self).newcoords(c, pos)
        self.changed()
        return self

    def changed(self):
        if self._changed is False:
            self._changed = True
            return [c.changed() for c in self.descendants]
        return [False]

    def parentcoords(self):
        if self.parent:
            return self.parent.worldcoords()
        return worldcoords

    def transform_vector(self, v):
        return self.worldcoords().transform_vector(v)

    def inverse_transform_vector(self, v):
        return self.worldcoords().inverse_transform_vector(v)

    def rotate_with_matrix(self, matrix, wrt):
        if wrt == 'local' or wrt == self:
            self._rotation = np.dot(self.rotation, matrix)
            return self.newcoords(self.rotation, self.translation)
        elif wrt == 'parent' or wrt == self.parent:
            self._rotation = np.matmul(matrix, self.rotation)
            return self.newcoords(self.rotation, self.translation)
        else:
            parent_coords = self.parentcoords()
            parent_rot = parent_coords.rotation
            if isinstance(wrt, Coordinates):
                wrt_rot = wrt.worldrot()
                matrix = np.matmul(wrt_rot, matrix)
                matrix = np.matmul(matrix, wrt_rot.T)
            matrix = np.matmul(matrix, parent_rot)
            matrix = np.matmul(parent_rot.T, matrix)
            self._rotation = np.matmul(matrix, self.rotation)
            return self.newcoords(self.rotation, self.translation)

    def rotate(self, theta, axis, wrt='local'):
        """Rotate this coordinate.

        Rotate this coordinate relative to axis by theta radians
        with respect to wrt.

        Parameters
        ----------
        theta : float
            radian
        axis : string or numpy.ndarray
            'x', 'y', 'z' or vector
        wrt : string or Coordinates

        Returns
        -------
        self
        """
        if isinstance(axis, list) or isinstance(axis, np.ndarray):
            return self.rotate_with_matrix(
                rotation_matrix(theta, axis), wrt)
        if isinstance(axis, np.ndarray) and axis.shape == (3, 3):
            return self.rotate_with_matrix(theta, wrt)

        if wrt == 'local' or wrt == self:
            self.rotation = rotate_matrix(self.rotation, theta, axis)
            return self.newcoords(self.rotation, self.translation)
        elif wrt == 'parent' or wrt == self.parent:
            self.rotation = rotate_matrix(self.rotation, theta, axis)
            return self.newcoords(self.rotation, self.translation)
        else:
            return self.rotate_with_matrix(
                rotation_matrix(theta, axis), wrt)

    def rotate_vector(self, v):
        return self.worldcoords().rotate_vector(v)

    def inverse_rotate_vector(self, v):
        return self.worldcoords().inverse_rotate_vector(v)

    def transform(self, c, wrt='local'):
        """Transform this coordinates

        Parameters
        ----------
        c : skrobot.coordinates.Coordinates
            coordinates
        wrt : str or skrobot.coordinates.Coordinates
            transform this coordinates with respect to wrt.
            If wrt is 'local' or self, multiply c from the right.
            If wrt is 'parent' or self.parent, transform c
            with respect to parentcoords. (multiply c from the left.)
            If wrt is Coordinates, transform c with respect to c.

        Returns
        -------
        self : skrobot.coordinates.CascadedCoords
            return self
        """
        if isinstance(wrt, Coordinates):
            transform_coords(self.parentcoords(), self, self)
            transform_coords(wrt.inverse_transformation(), self, self)
            transform_coords(c, self, self)
            transform_coords(wrt.worldcoords(), self, self)
            transform_coords(self.parentcoords().inverse_transformation(),
                             self, self)
        elif wrt == 'local' or wrt == self:
            # multiply c from the right.
            transform_coords(self, c, self)
        elif wrt == 'parent' or wrt == self.parent:
            # multiply c from the left.
            transform_coords(c, self, self)
        elif wrt == 'world':
            parentcoords = self.parentcoords()
            transform_coords(parentcoords, self, self)
            transform_coords(c, self, self)
            transform_coords(parentcoords.inverse_transformation(),
                             self, self)
        else:
            raise ValueError('transform wrt {} is not supported'.format(wrt))
        return self.newcoords(self.rotation, self.translation)

    def update(self, force=False):
        if not force and not self._changed:
            return
        with self.disable_hook():
            if self.parent:
                transform_coords(
                    self.parent.worldcoords(),
                    self,
                    self._worldcoords)
            else:
                self._worldcoords.rotation = self.rotation
                self._worldcoords.translation = self.translation
        self._changed = False

    def worldcoords(self):
        """Calculate rotation and position in the world."""
        self.update()
        return self._worldcoords

    def worldrot(self):
        return self.worldcoords().rotation

    def worldpos(self):
        return self.worldcoords().translation

    @property
    def parent(self):
        return self._parent

    @parent.setter
    def parent(self, c):
        if not (c is None or coordinates_p(c)):
            raise ValueError('parent should be None or Coordinates. '
                             'get type=={}'.format(type(c)))
        self._parent = c


def coordinates_p(x):
    """Return whether an object is an instance of a class or of a subclass"""
    return isinstance(x, Coordinates)


def make_coords(*args, **kwargs):
    """Return Coordinates

    This is a wrapper of Coordinates class
    """
    return Coordinates(*args, **kwargs)


def make_cascoords(*args, **kwargs):
    """Return CascadedCoords

    This is a wrapper of CascadedCoords
    """
    return CascadedCoords(*args, **kwargs)


def random_coords():
    """Return Coordinates class has random translation and rotation"""
    return Coordinates(pos=random_translation(),
                       rot=random_rotation())


def wrt(coords, vec):
    return coords.transform_vector(vec)


def coordinates_distance(c1, c2, c=None):
    if c is None:
        c = c1.transformation(c2)
    return np.linalg.norm(c.worldpos()), rotation_angle(c.worldrot())[0]


worldcoords = CascadedCoords(name='worldcoords')
