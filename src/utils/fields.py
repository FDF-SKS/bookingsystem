from map_location.fields import LocationField, Position


class SafeLocationField(LocationField):
    """LocationField that tolerates malformed 'lat,lon' values already stored in the database.

    Corrupt/legacy rows (e.g. missing comma, empty-but-non-null string) would otherwise
    raise ValueError when Django reads them, crashing unrelated admin/changelist views.
    Such values are treated as if the field were empty instead of raising.
    """

    def from_db_value(self, value, expression, connection) -> 'Position|None':
        if not value:
            return None
        try:
            lat, lon = value.split(',')
            return Position(float(lat), float(lon))
        except (ValueError, TypeError):
            return None

    def to_python(self, value) -> 'Position|None':
        if isinstance(value, Position):
            return value
        if not value:
            return None
        try:
            lat, lon = value.split(',')
            return Position(float(lat), float(lon))
        except (ValueError, TypeError):
            return None
