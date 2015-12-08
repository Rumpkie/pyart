"""
pyart.core.grid
===============

An class for holding gridded Radar data.

.. autosummary::
    :toctree: generated/
    :template: dev_template.rst

    Grid

.. autosummary::
    :toctree: generated/

    _point_data_factory
    _point_lon_lat_data_factory
    _point_altitude_data_factory

"""

import warnings

import numpy as np

from ..config import get_metadata
from ..lazydict import LazyLoadDict
from .transforms import cartesian_to_geographic


class Grid(object):
    """
    A class for storing rectilinear gridded radar data in Cartesian coordinate.

    Refer to the attribute section for information on the parameters.

    To create a Grid object using legacy parameters present in Py-ART version
    1.5 and before, use :py:func:`from_legacy_parameters`,
    grid = Grid.from_legacy_parameters(fields, axes, metadata).

    Attributes
    ----------
    fields: dict of dicts
        Moments from radars or other variables.
    metadata: dict
        Metadata describing the grid.
    time : dict
        Time of the grid.
    origin_longitude, origin_latitude, origin_altitude : dict
        Geographic coordinate of the origin of the grid.
    regular_x, regular_y, regular_z : dict
        Regular locations of grid points from the origin in the three
        Cartesian coordinates.
    point_x, point_y, point_z : LazyLoadDict
        The Cartesian locations of all grid points from the origin in the
        three Cartesian coordinates.  The three dimensional data arrays
        contained these attributes are calculated from the regular_x,
        regular_y, and regular_z attributes.  If these attributes are changed
        use :py:func:`init_point_x_y_z` to reset the attributes.
    point_longitude, point_latitude : LazyLoadDict
        Geographic location of each grid point. The projection parameter(s)
        defined in the `projection` attribute are used to perform an inverse
        map projection from the Cartesian grid point locations relative to
        the grid origin. If these attributes are changed use
        :py:func:`init_point_longitude_latitude` to reset the attributes.
    point_altitude : LazyLoadDict
        The altitude of each grid point as calculated from the altitude of the
        grid origin and the Cartesian z location of each grid point.  If this
        attribute is changed use :py:func:`init_point_altitude` to reset the
        attribute.
    projection : dic or str
        Projection parameters defining the map projection used to transform
        from Cartesian to geographic coordinates.  None will use the default
        dictionary with the 'proj' key set to 'pyart_aeqd' indicating that
        the native Py-ART azimuthal equidistant projection is used. Other
        values should specify a valid pyproj.Proj projparams dictionary or
        string.  The special key '_include_lon_0_lat_0' is removed when
        interpreting this dictionary. If this key is present and set to True,
        which is required when proj='pyart_aeqd', then the radar longitude and
        latitude will be added to the dictionary as 'lon_0' and 'lat_0'.
    nx, ny, nz : int
        Number of grid points along the given Cartesian dimension.
    axes : dict
        Dictionary of axes dictionaries.  This attribute is depreciated,
        it will be removed in future versions of Py-ART.
    radar_longitude, radar_latitude, radar_altitude : dict or None, optional
        Geographic location of the radars which make up the grid.
    radar_time : dict or None, optional
        Start of collection for the radar which make up the grid.
    radar_name : dict or None, optional
        Names of the radars which make up the grid.

    """
    def __init__(self, time, fields, metadata,
                 origin_latitude, origin_longitude, origin_altitude,
                 regular_x, regular_y, regular_z,
                 projection=None, radar_latitude=None, radar_longitude=None,
                 radar_altitude=None, radar_time=None, radar_name=None):
        """ Initalize object. """

        self.time = time
        self.fields = fields
        self.metadata = metadata
        self.origin_latitude = origin_latitude
        self.origin_longitude = origin_longitude
        self.origin_altitude = origin_altitude
        self.regular_x = regular_x
        self.regular_y = regular_y
        self.regular_z = regular_z
        self.nx = len(regular_x['data'])
        self.ny = len(regular_y['data'])
        self.nz = len(regular_z['data'])
        if projection is None:
            self.projection = {
                'proj': 'pyart_aeqd', '_include_lon_0_lat_0': True}
        else:
            self.projection = projection

        self.radar_latitude = radar_latitude
        self.radar_longitude = radar_longitude
        self.radar_altitude = radar_altitude
        self.radar_time = radar_time
        self.radar_name = radar_name
        self.nradar = self._find_and_check_nradar()

        # initialize attributes with Lazy load dictionaries
        self.init_point_x_y_z()
        self.init_point_longitude_latitude()
        self.init_point_altitude()

        # Depreciated axes attribute
        axes = {'time': time,
                'time_start': time,  # incorrect metadata
                'time_end': time,    # incorrect metadata
                'z_disp': regular_z,
                'y_disp': regular_y,
                'x_disp': regular_x,
                'alt': origin_altitude,
                'lat': origin_latitude,
                'lon': origin_longitude}
        self.axes = axes

        return

    @classmethod
    def from_legacy_parameters(cls, fields, axes, metadata):
        """
        Return a Grid class using legacy parameters.

        Parameters
        ----------
        fields : dict
            Dictionary of field dictionaries.
        metadata : dict
            Dictionary of metadata.
        axes : dict
            Dictionary of axes dictionaries.

        Returns
        --------
        grid : Grid
            A Grid object.

        """
        warnings.warn(
            "from_legacy_parameters is depreciated and will be removed in a " +
            "future version of Py-ART", DeprecationWarning)
        time = axes['time']
        fields = fields
        metadata = metadata
        origin_latitude = axes['lat']
        origin_longitude = axes['lon']
        origin_altitude = axes['alt']
        regular_x = axes['x_disp']
        regular_y = axes['y_disp']
        regular_z = axes['z_disp']
        grid = cls(time, fields, metadata,
                   origin_latitude, origin_longitude, origin_altitude,
                   regular_x, regular_y, regular_z)
        return grid

    def _find_and_check_nradar(self):
        """
        Return the number of radars which were used to create the grid.

        Examine the radar attributes to determine the number of radars which
        were used to create the grid.  If the size of the radar attributes
        are inconsistent a ValueError is raised by this method.
        """
        nradar_set = False
        nradar = 0

        if self.radar_latitude is not None:
            nradar = len(self.radar_latitude['data'])
            nradar_set = True

        if self.radar_longitude is not None:
            if nradar_set and len(self.radar_longitude['data']) != nradar:
                raise ValueError("Inconsistent length of radar_ arguments.")
            nradar = len(self.radar_longitude['data'])
            nradar_set = True

        if self.radar_altitude is not None:
            if nradar_set and len(self.radar_altitude['data']) != nradar:
                raise ValueError("Inconsistent length of radar_ arguments.")
            nradar = len(self.radar_altitude['data'])
            nradar_set = True

        if self.radar_time is not None:
            if nradar_set and len(self.radar_time['data']) != nradar:
                raise ValueError("Inconsistent length of radar_ arguments.")
            nradar = len(self.radar_time['data'])
            nradar_set = True

        if self.radar_name is not None:
            if nradar_set and len(self.radar_name['data']) != nradar:
                raise ValueError("Inconsistent length of radar_ arguments.")
            nradar = len(self.radar_name['data'])
            nradar_set = True

        return nradar

    # Attribute init/reset methods
    def init_point_x_y_z(self):
        """ Initialize or reset the point_{x, y, z} attributes. """
        self.point_x = LazyLoadDict(get_metadata('point_x'))
        self.point_x.set_lazy('data', _point_data_factory(self, 'x'))

        self.point_y = LazyLoadDict(get_metadata('point_y'))
        self.point_y.set_lazy('data', _point_data_factory(self, 'y'))

        self.point_z = LazyLoadDict(get_metadata('point_z'))
        self.point_z.set_lazy('data', _point_data_factory(self, 'z'))

    def init_point_longitude_latitude(self):
        """
        Initialize or reset the point_{longitude, latitudes} attributes.
        """
        point_longitude = LazyLoadDict(get_metadata('point_longitude'))
        point_longitude.set_lazy('data', _point_lon_lat_data_factory(self, 0))
        self.point_longitude = point_longitude

        point_latitude = LazyLoadDict(get_metadata('point_latitude'))
        point_latitude.set_lazy('data', _point_lon_lat_data_factory(self, 1))
        self.point_latitude = point_latitude

    def init_point_altitude(self):
        """ Initialize the point_altitude attribute. """
        point_altitude = LazyLoadDict(get_metadata('point_altitude'))
        point_altitude.set_lazy('data', _point_altitude_data_factory(self))
        self.point_altitude = point_altitude

    def write(self, filename, format='NETCDF4', arm_time_variables=False):
        """
        Write the the Grid object to a NetCDF file.

        Parameters
        ----------
        filename : str
            Filename to save to.
        format : str, optional
            NetCDF format, one of 'NETCDF4', 'NETCDF4_CLASSIC',
            'NETCDF3_CLASSIC' or 'NETCDF3_64BIT'.
        arm_time_variables : bool
            True to write the ARM standard time variables base_time and
            time_offset. False will not write these variables.

        """
        # delayed import to avoid circular import
        from ..io.grid_io import write_grid

        write_grid(filename, self, format=format,
                   arm_time_variables=arm_time_variables)

    def add_field(self, field_name, field_dict, replace_existing=False):
        """
        Add a field to the object.

        Parameters
        ----------
        field_name : str
            Name of the field to the fields dictionary.
        field_dict : dict
            Dictionary containing field data and metadata.
        replace_existing : bool, optional
            True to replace the existing field with key field_name if it
            exists, overwriting the existing data. If False, a ValueError is
            raised if field_name already exists.

        """
        # checks to make sure input field dictionary is valid
        if 'data' not in field_dict:
            raise KeyError('Field dictionary must contain a "data" key')
        if field_name in self.fields and replace_existing is False:
            raise ValueError('A field named %s already exists' % (field_name))
        if field_dict['data'].shape != (self.nz, self.ny, self.nx):
            raise ValueError('Field has invalid shape')

        self.fields[field_name] = field_dict


def _point_data_factory(grid, coordinate):
    """ Return a function which returns the locations of all points.  """
    def _point_data():
        """ The function which returns the locations of all points. """
        reg_x = grid.regular_x['data']
        reg_y = grid.regular_y['data']
        reg_z = grid.regular_z['data']
        if coordinate == 'x':
            return np.tile(reg_x, (len(reg_z), len(reg_y), 1)).swapaxes(2, 2)
        elif coordinate == 'y':
            return np.tile(reg_y, (len(reg_z), len(reg_x), 1)).swapaxes(1, 2)
        else:
            assert coordinate == 'z'
            return np.tile(reg_z, (len(reg_x), len(reg_y), 1)).swapaxes(0, 2)
    return _point_data


def _point_lon_lat_data_factory(grid, coordinate):
    """ Return a function which returns the geographic locations of points. """
    def _point_lon_lat_data():
        """ The function which returns the geographic point locations. """
        x = grid.point_x['data']
        y = grid.point_y['data']
        projparams = grid.projection.copy()
        if projparams.pop('_include_lon_0_lat_0', False):
            projparams['lon_0'] = grid.origin_longitude['data'][0]
            projparams['lat_0'] = grid.origin_latitude['data'][0]
        geographic_coords = cartesian_to_geographic(x, y, projparams)
        # Set point_latitude['data'] when point_longitude['data'] is evaluated
        # and vice-versa.  This ensures that both attributes contain data from
        # the same map projection and that the map projection only needs to be
        # evaluated once.
        if coordinate == 0:
            grid.point_latitude['data'] = geographic_coords[1]
        else:
            grid.point_longitude['data'] = geographic_coords[0]
        return geographic_coords[coordinate]
    return _point_lon_lat_data


def _point_altitude_data_factory(grid):
    """ Return a function which returns the point altitudes. """
    def _point_altitude_data():
        """ The function which returns the point altitudes. """
        return grid.origin_altitude['data'][0] + grid.point_z['data']
    return _point_altitude_data
