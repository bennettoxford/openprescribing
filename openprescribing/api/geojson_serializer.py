"""
Django's built-in GeoJSON serializer (django.core.serializers.geojson) will
only serialize fields defined on the model, so if you want to include results
calculated on a QuerySet using e.g. `annotate` or `aggregate` then you're out
of luck.

Below is a dirt-simple implementation of a GeoJSON serializer which accepts
dictionaries with arbitrary keys.
"""

import json

from django.contrib.gis.gdal import CoordTransform, SpatialReference


def as_geojson_stream(dicts, geometry_field="geometry", srid=4326):
    """
    Convert an iterable of dictionaries into an iterable of strings giving
    their GeoJSON representation

    The slightly awkward hand-crafting of JSON is done because we only have
    access to the geometries as already serialized JSON strings and parsing
    these into a big data structure only so we can serialize them again seems a
    bit ridiculous.
    """
    to_geojson = GeoJSONConvertor(srid)
    header = {
        "type": "FeatureCollection",
    }
    # Output header omitting closing brace
    yield json.dumps(header)[:-1]
    # Open "features" array
    yield ', "features": ['
    for n, dictionary in enumerate(dicts):
        # Output separator
        yield ",\n" if n > 0 else "\n"
        geometry = dictionary.pop(geometry_field, None)
        feature = {"type": "Feature", "properties": dictionary}
        # Output feature omitting closing brace and newline
        yield json.dumps(feature, indent=2)[:-2]
        # Output geometry field, which is already a JSON string
        yield ',\n  "geometry": '
        yield to_geojson(geometry)
        # Close feature
        yield "\n}"
    # Close features array and header object
    yield "\n]}"


class GeoJSONConvertor(object):
    """
    Convert geometry object to GeoJSON string in the required SRID
    """

    def __init__(self, srid):
        self.srid = srid
        self._transforms = {}

    def __call__(self, geometry):
        if geometry is None:
            return "null"
        if geometry.srid != self.srid:
            if geometry.srid not in self._transforms:
                srs = SpatialReference(self.srid)
                self._transforms[geometry.srid] = CoordTransform(geometry.srs, srs)
            geometry.transform(self._transforms[geometry.srid])
        return geometry.geojson
