var $ = require('jquery');
var chroma = require('chroma-js');
var utils = require('./chart_utils');
var formatters = require('./chart_formatters');
var _ = require('underscore');
var config = require('./config');
var basemap = require('./basemap');

// Leaflet is loaded via a <script> tag (see templates/_map_assets.html).
var L = window.L;

var LegendControl = L.Control.extend({
  options: {position: 'bottomright'},

  onAdd: function() {
    this._div = L.DomUtil.create('div', 'map-legend');
    this._div.style.display = 'none';
    return this._div;
  },

  setContent: function(html) {
    this._div.innerHTML = html;
    this._div.style.display = html ? '' : 'none';
  },
});

var analyseMap = {

  setup: function(options) {
    this.options = options;
        // TODO: Deal with no data
        //         $('#map-wrapper').show();
        //     } else {
        //         $('.chart-title').html("No known locations");
        //         $('.chart-sub-title').html('');
        //         $('#map-wrapper').hide();
        //     }
        // });

    var _this = this;
    _this.activeNames = _.pluck(options.orgIds, 'name');
    if (typeof _this.map === 'undefined') {
      _this.map = basemap.createMap('map', {});
      _this.legend = new LegendControl().addTo(_this.map);
    } else {
      if (typeof _this.orgLayer !== 'undefined') {
        _this.map.removeLayer(_this.orgLayer);
      }
      _this.legend.setContent('');
    }
    var completed = $.Deferred();

    _this.popup = new L.Popup({autoPan: false});
    var boundsUrl = this.getBoundsUrl(options);

    $.getJSON(boundsUrl).done(joinDataAndSetupMap);

    function joinDataAndSetupMap(geojson) {
      var dataByName = utils.indexDataByRowNameAndMonth(options.data.combinedData);
      _this.minMaxByDate = utils.calculateMinMaxByDate(options.data.combinedData);
      _this.features = joinFeaturesWithData(geojson, dataByName);
      _this.orgLayer = L.geoJSON(_this.features, {
        pointToLayer: function(feature, latlng) {
          return L.circleMarker(latlng, {
            radius: 8,
            color: '#000',
            weight: 1,
            opacity: 1,
            fillOpacity: 0.97,
          });
        },
      }).addTo(_this.map);
      if ('_northEast' in _this.orgLayer.getBounds()) {
        _this.map.fitBounds(_this.orgLayer.getBounds(), {
          minZoom: 7,
          paddingBottomRight: [$(_this.legendContainer).width(), 0],
        });
      }
      _this.addLayerEvents();
      _this.updateMap('items',
                      options);
      $('#play-slider').show();
      completed.resolve();
    }

    function joinFeaturesWithData(currentJson, data) {
      var joinedFeatures = [],
        byName = {};
      _.each(currentJson.features, function(d, i) {
        if ('setting' in d.properties) {
          if (d.properties.setting === 4) {
            byName[d.properties.name] = d;
          }
        } else {
          byName[d.properties.name] = d;
        }
      });
      for (var name in byName) {
        byName[name].properties.data = data[name];
        joinedFeatures.push(byName[name]);
      }
      return joinedFeatures;
    }

    return completed;
  },

  addLayerEvents: function(ratio, month) {
    var _this = this;
    var closeTooltip;
    _this.orgLayer.eachLayer(function(layer) {
      layer.on('mousemove', function(e) {
        var layerData = e.target.feature.properties.data;
                // console.log('chartValues', _this.options.chartValues);
        var y = _this.options.chartValues.y;
        var x = _this.options.chartValues.x_val;
        var month = _this.options.activeMonth;
        var ratio = _this.options.chartValues.ratio;
        var monthData;
        var k = month.replace(/\//g, '-');
        if ((typeof layerData !== 'undefined') && (k in layerData)) {
          monthData = layerData[k];
        } else {
          monthData = {};
          monthData[y] = null;
          monthData[x] = null;
          monthData[ratio] = null;
        }
        var layer = e.target;
        var html = formatters.constructTooltip(_this.options,
                    layer.feature.properties.name,
                    month,
                    monthData[y],
                    monthData[x],
                    monthData[ratio]);
        this.popup.setLatLng(e.latlng);
        this.popup.setContent(html);
        if (!this.map.hasLayer(this.popup)) {
          this.popup.openOn(this.map);
        }
        window.clearTimeout(closeTooltip);
        if (!L.Browser.ie && !L.Browser.opera) {
          layer.bringToFront();
        }
      }, _this);
      layer.on('mouseout', function(e) {
        var _this = this;
        closeTooltip = window.setTimeout(function() {
          _this.map.closePopup();
        }, 100);
      }, _this);
      layer.on('click', function(e) {
        // Polygons have bounds; circle markers (points) don't in Leaflet 1.x.
        if (typeof e.target.getBounds === 'function') {
          this.map.fitBounds(e.target.getBounds());
        } else {
          this.map.panTo(e.latlng);
        }
        e.target.fireEvent('mousemove', e);
      }, _this);
    });
  },

  updateMap: function(ratio, options) {
    var _this = this;
    var minMax;
    ratio = 'ratio_' + ratio;
    var month = options.activeMonth.replace(/\//g, '-');
    if (options.playing) {
      // For animation-over-time, keep the min/max values constant
      var allMinMax = _.pluck(_.values(_this.minMaxByDate), ratio);
      minMax = [_.min(_.map(allMinMax, function(x) {
return x[0];
})),
                _.max(_.map(allMinMax, function(x) {
return x[1];
}))];
    } else {
      minMax = (month in _this.minMaxByDate) ? _this.minMaxByDate[month][ratio] : null;
    }
    _this.legend.setContent(_this.getLegend(minMax, options));
    _this.orgLayer.eachLayer(function(layer) {
      var layerData = layer.feature.properties.data;
      var val = ((typeof layerData !== 'undefined') && (month in layerData)) ? layerData[month][ratio] : null;
      var style = _this.getStyle(val,
                                 minMax[1],
                                 layer.feature.properties.name,
                                 _this.activeNames);
      layer.setStyle(style);
    });
  },

  getStyle: function(val, maxVal, name, activeNames) {
    var style = {
      color: 'black',
      fillOpacity: 0.7,
      radius: 8,
      weight: 2,
      opacity: 0.3,
      fillColor: this.getColour(maxVal, val),
    };
    if (_.contains(activeNames, name)) {
      style.weight = 3;
      style.opacity = 0.9;
    }
    return style;
  },

  resize: function() {
    var _this = this;
    if ((_this.features) && (_this.features.length) && (_this.orgLayer.getBounds().isValid())) {
      _this.map.invalidateSize();
      _this.map.fitBounds(_this.orgLayer.getBounds(), {
        minZoom: 7,
        paddingBottomRight: [$(_this.legendContainer).width(), 0],
      });
    } else {
      _this.map.invalidateSize();
      _this.map.setView([52, 0], 6);
    }
  },

  getBoundsUrl: function(options) {
    var boundsUrl = config.apiHost + '/api/1.0/org_location/?format=json&';
    if ( ! utils.shouldCompareWithAllOrgs(options)) {
      boundsUrl += 'org_type=' + options.org + '&q=';
      _.each(options.orgIds, function(d) {
        if (('ccg' in d) && (d.ccg)) {
          boundsUrl += d.ccg + ',';
        } else {
          boundsUrl += d.id + ',';
        }
      });
    } else {
      boundsUrl += 'org_type=' + options.org.toLowerCase();
    }
    return boundsUrl;
  },

  getColour: function(topVal, d) {
    var scale = chroma.scale('RdBu');
    return scale(1 - (d / topVal)).hex();
  },

  getLegend: function(minMax, options) {
    // console.log('getLegend', quintiles);
    var legend = '<span class="legend-header">' + options.friendly.yAxisTitle.replace('<br/>', '');
    legend += ' ' + options.friendly.chartSubTitle + '</span>';
    legend += '<div class="gradient">';
    for (var i = 1; i <= 100; i++) {
      var j = minMax[0] + i * (minMax[1] - minMax[0]) / 100;
      legend += '<span class="grad-step" style="background-color:' + this.getColour(minMax[1], j) + '"></span>';
    }
    legend += '<span class="domain-min">' + Highcharts.numberFormat(minMax[0]) + '</span>';
    legend += '<span class="domain-max">' + Highcharts.numberFormat(minMax[1]) + '</span>';
    legend += '</div>';
    legend += 'by ' + options.friendly.friendlyOrgs;
    return legend;
  },

    // hasKnownLocations: function(boundaries) {
    //     var has_locations = false;
    //     $.each(boundaries.features, function(i, d) {
    //         if (d.geometry !== null) {
    //             has_locations = true;
    //             return false;
    //         }
    //     });
    //     return has_locations;
    // }

};
module.exports = analyseMap;
