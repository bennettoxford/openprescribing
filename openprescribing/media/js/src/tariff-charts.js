var $ = require('jquery');
require('bootstrap');
require('select2');
var Highcharts = require('Highcharts');
require('Highcharts-export')(Highcharts);
var domready = require('domready');
var _ = require('underscore');

var chartOptions = require('./highcharts-options');

var tariffChart = {


  reshapeData: function(data) {
    // Reshape data from API to a format that's easy to pass to
    // Highcharts
    var byVmpp = {};
    _.each(data, function(d) {
      var dates = d.date.split('-');
      var date = Date.UTC(dates[0], dates[1] - 1, dates[2]);
      if (!(d.vmpp in byVmpp)) {
        byVmpp[d.vmpp] = [];
      }
      byVmpp[d.vmpp].push({
        x: date,
        y: parseFloat(d.price_pence) / 100,
        tariff_category: d.tariff_category,
      });
      // Store price concession as a separate series
      var concessionKey = d.vmpp + ' (price concession)';
      if (!(concessionKey in byVmpp)) {
        byVmpp[concessionKey] = [];
      }
      byVmpp[concessionKey].push({
        x: date,
        y: d.concession ? parseFloat(d.concession) / 100: d.concession});
    });
    return byVmpp;
  },

  hasConcession: function(vmppData) {
    return _.some(vmppData, function(d) {
      return d.y > 0;
    });
  },

  getZIndex: function(vmppdata) {
    // Show series with highest values nearest the front
    return _.max(_.pluck(vmppdata, 'y'));
  },

  getMarkerSize: function(vmppdata) {
    // Normally, we don't show markers as they are quite ugly on
    // an area chart. However, if a series is only one item
    // long, you can't see it unless there is a marker.
    var markerSize = 0;
    if (_.filter(vmppdata, function(d) {
      return d.y !== null;
    }).length < 2) {
      markerSize = 3;
    }
    return markerSize;
  },

  anySeriesHasDashStyle: function(data, style) {
    var hasStyle = false;
    try {
      _.each(data, function(series) {
        _.each(series.zones, function(zone) {
          if (zone.dashStyle === style) {
            hasStyle = true;
            throw 'found style';
          }
        });
      });
    } catch (e) {
      // style found
    };
    return hasStyle;
  },

  addDummySeriesForCategoryLabels: function(data) {
    // Given complete data series, return an array of strings
    // indicating any DT Categories that have been used in any of the
    // series. We use this array to decide which extra legend items to
    // display (e.g. to indicate that a dotted line means "Category
    // C")
    var _this = this;
    if (_this.anySeriesHasDashStyle(data, 'line')) {
      data.push({name: 'Category A', data: [], color: '#fff'});
    }
    if (_this.anySeriesHasDashStyle(data, 'dot')) {
      data.push({name: 'Category C', data: [], color: '#fff'});
    }
    if (_this.anySeriesHasDashStyle(data, 'long-dash-dot-dot')) {
      data.push({name: 'Category H', data: [], color: '#fff'});
    }
    if (_this.anySeriesHasDashStyle(data, 'dash')) {
      data.push({name: 'Category M', data: [], color: '#fff'});
    }
    return data;
  },

  getCategoryZones: function(vmppdata) {
    // Zone calculations: line styles for highcharts, based on category
    var zones = [];
    var lastCat = null;
    var cat = null;
    var dashStyle;
    var dataWithDummy = vmppdata.concat([{tariff_category: null}]);
    _.each(dataWithDummy, function(d) {
      cat = d.tariff_category;
      if (!lastCat) {
        lastCat = cat;
      }
      if (cat !== lastCat) {
        switch (lastCat) {
        case 'Part VIIIA Category A':
          dashStyle = 'line';
          break;
        case 'Part VIIIA Category C':
          dashStyle = 'dot';
          break;
        case 'Part VIIIA Category H':
          dashStyle = 'long-dash-dot-dot';
          break;
        case 'Part VIIIA Category M':
          dashStyle = 'dash';
          break;
        default:
          // do nothing
        }
        zones.push(
          {value: d.x, dashStyle: dashStyle}
        );
      }
      lastCat = cat;
    });
    return zones;
  },

  initialiseData: function(data) {
    var _this = this;
    var byVmpp = this.reshapeData(data);
    // Decorate each series with extra Highcharts properties that are
    // computed based on all the values in that series; specifically,
    // a z-index which places series with highest values at the front,
    // and a "zoning" that allows us to indicate the Drug Tariff
    // Category of each presentation over time.
    var newData = [];
    var categoriesShown = [];
    for (var vmpp in byVmpp) {
      var isConcessionSeries = vmpp.indexOf('concession') > -1;
      if (byVmpp.hasOwnProperty(vmpp)) {
        if (isConcessionSeries && !_this.hasConcession(byVmpp[vmpp])) {
          continue;
        } else {
          var zIndex = _this.getZIndex(byVmpp[vmpp]);
          var markerSize = _this.getMarkerSize(byVmpp[vmpp]);
          var zones = _this.getCategoryZones(byVmpp[vmpp]);
          newData.push({
            name: vmpp,
            marker: {radius: markerSize},
            data: byVmpp[vmpp],
            zones: zones,
            zoneAxis: 'x',
            zIndex: zIndex});
        }
      }
    }
    // These dummy series are required so we can add dashed-line labels to the
    // legend
    return _this.addDummySeriesForCategoryLabels(newData);
  },

  initialiseChartOptions: function(chartOptions, data) {
    var options = chartOptions.baseOptions;
    options.chart.marginTop = 40;
    options.plotOptions = {
      series: {
        marker: {
          radius: 0,
        },
        fillOpacity: 0.4,
        connectNulls: false,
        pointPadding: 0,
        groupPadding: 0,
      },
    };
    options.chart.spacingTop = 20;
    options.chart.type = 'area';
    options.title.text = chartTitle;
    // The following is a hack to show labels for the line-styling
    // which indicates DT Category (see dummary series above)
    options.legend = {
      useHTML: true,
      floating: false,
      symbolHeight: 0,
      symbolWidth: 0,
      itemMarginTop: 4,
      itemMarginBottom: 4,
      labelFormatter: function() {
        // The values for `stroke-dasharray` are taken from inspecting
        // the SVG generated by Highcharts fors its line, dash, and dot styles.
        var str = '<div><div style="width:30px;display:inline-block;';
        str += 'padding:3px 2px 3px 2px;margin-right: 4px;text-align:center;';
        str += 'color:#FFF;background-color:' + this.color + '">';
        var stroke = '<svg width="30" height="5"><path d="M0 0 H30" stroke="black" ';
        stroke += 'stroke-width="2" stroke-dasharray="';
        if (this.name === 'Category A') {
          str += stroke + 'none" /></svg>';
        } else if (this.name === 'Category C') {
          str += stroke + '2,6" /></svg>';
        } else if (this.name === 'Category H') {
          str += stroke + '8,3,1,3,1,3" /></svg>';
        } else if (this.name === 'Category M') {
          str += stroke + '8,6" /></svg>';
        }
        str += '</div>';
        return str + this.name;
      },
    };
    options.tooltip = {
      pointFormatter: function() {
        var str = '<span style="color:' + this.color + '">\u25CF</span> ';
        str += this.series.name + ': <b>£' + this.y.toFixed(2);
        if (this.tariff_category) {
          str += ' (' + this.tariff_category + ') ';
        }
        str += '</b><br/>';
        return str;
      },
    };
    // A legend is redudant when there is only one series shown
    if (data.length > 1) {
      options.legend.enabled = true;
    } else {
      options.legend.enabled = false;
    }
    options.yAxis.title = {
      text: 'Price (£)',
    };
    return options;
  },

  setUp: function() {
    var _this = this;
    $('.tariff-selector').select2(
      {placeholder: 'Start typing a presentation name'}
    );

    if (bnfCodes == '') {
      return;
    }

    $.ajax({
      type: 'GET',
      url: baseUrl + '?format=json&codes=' + bnfCodes,
      error: function() {
        $('.status').html('<p>Sorry, something went wrong.</p>');
      },
      success: function(response) {
        $('.status').hide();
        var data = _this.initialiseData(response);
        chartOptions = _this.initialiseChartOptions(chartOptions, data);
        if (data.length) {
          $('#tariff').show();
          chartOptions.series = data;
          var chart = new Highcharts.Chart(chartOptions);
        } else {
          $('#tariff').hide();
          $('#no-data').show();
        }
      },
    });
  },
};

domready(function() {
  tariffChart.setUp();
});
