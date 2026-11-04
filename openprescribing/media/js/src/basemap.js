// Creates Leaflet maps with a Protomaps basemap, served from a self-hosted
// .pmtiles file (see config.basemapUrl).
//
// Leaflet and protomaps-leaflet are loaded as separate <script> tags (see
// templates/_map_assets.html) rather than bundled, so we use the globals they
// define (window.L and window.protomapsL).

var _ = require('underscore');
var config = require('./config');

// The basemap extract has bbox -12,49,4.5,56.5 and goes up to zoom 14.
//
// We stop the map being panned beyond MAX_BOUNDS, which lies within the
// extract's bbox. MAX_BOUNDS is centred on England's longitude (about 1.5W),
// because when the view is wider than maxBounds (as it is at low zooms),
// Leaflet centres the view on maxBounds.
//
// At low zooms the view extends beyond MAX_BOUNDS. The extract's bbox extends
// west of 11.25W so that the extract includes the low-zoom tiles needed to
// cover the view. (Tiles to the east already reach 11.25E.)
var MAX_BOUNDS = [[49, -7.5], [56.5, 4.5]];
var BASEMAP_MAX_ZOOM = 14;

module.exports = {
  createMap: function(elementId, options) {
    var L = window.L;
    var mapOptions = _.extend({
      minZoom: 5,
      maxBounds: MAX_BOUNDS,
      scrollWheelZoom: false,
    }, options);
    var map = L.map(elementId, mapOptions);
    window.protomapsL.leafletLayer({
      url: config.basemapUrl,
      flavor: 'light',
      lang: 'en',
      maxDataZoom: BASEMAP_MAX_ZOOM,
      attribution: '<a href="https://protomaps.com">Protomaps</a> ' +
        '&copy; <a href="https://openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);
    return map;
  },
};
