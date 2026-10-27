var system = require('system');
var page = new WebPage();
page.onConsoleMessage = function(msg) {
  system.stderr.writeLine('console: ' + msg);
};
page.viewportSize = {
  width: 1024,
  height: 1024
};
var address;

if (system.args.length < 7) {
  console.log('Usage: phantomjs grab_chart.js <url> <filename> <selector> <width>x<height> timeout <host-header>');
  phantom.exit(1);
} else {
  address = system.args[1];
  var path = system.args[2];
  var selector = system.args[3];
  var parts = system.args[4].split('x');
  page.viewportSize = {
    width: parseInt(parts[0], 10),
    height: parseInt(parts[1], 10)
  };
  var wait = parseInt(system.args[5]);
  var hostHeader = system.args[6];
  // Only override Host for requests to the server we're grabbing from, not
  // third-party ones
  var origin = address.match(/^https?:\/\/[^\/]+/)[0];
  page.onResourceRequested = function(requestData, networkRequest) {
    if (requestData.url.indexOf(origin) === 0) {
      networkRequest.setHeader('Host', hostHeader);
    }
  };
  page.open(address, function(status) {
    if (!status === 'success') {
      console.log('Unable to load the address!');
    } else {
      waitFor({
        debug: true,
        extraWait: wait,
        interval: 500,  // The time series chart is actually
                        // visible some time after the element is
                        // visible (there's a jerky refresh thing
                        // going on). We should fix the jerky thing,
                        // then we can make the timeout shorter
        timeout: 60000,
        check: function() {
          return page.evaluate(function(s) {
            // trigger scroll-related events in measures pages.
            // without this, we'd be screenshotting undrawn charts
            $('body').scrollTop(1);
            return $(s).is(':visible');
          }, selector);
        },
        success: function() {
          captureSelector(path, selector);
          phantom.exit();
        },
        error: function() {
          console.log("Error waiting for element " + selector);
          phantom.exit(1);
        }
      });
    }
  });
}

function waitFor($config) {
  $config._start = $config._start || new Date();
  if ($config.timeout && new Date() - $config._start > $config.timeout) {
    if ($config.error) {
      $config.error();
    }
    if ($config.debug) {
      console.log('timedout ' + (new Date() - $config._start) + 'ms');
    }
    return;
  }

  if ($config.check()) {
    if ($config.debug) {
      console.log('success ' + (new Date() - $config._start) + 'ms');
    }
    return setTimeout(function() {
      return $config.success();
    }, $config.extraWait); // the extra wait is for the graph to paint
  }

  setTimeout(waitFor, $config.interval || 0, $config);
}

var capture = function(targetFile, clipRect) {
  // save specified clip rectangle on current page to targetFile
  var previousClipRect;
  previousClipRect = page.clipRect;
  page.clipRect = clipRect;
  try {
    page.render(targetFile);
  } catch (e) {
    console.log(
      'Failed to capture screenshot as ' + targetFile + ': ' + e, "error");
  }
  if (previousClipRect) {
    page.clipRect = previousClipRect;
  }
  return this;
};

var captureSelector = function(targetFile, selector) {
  return capture(targetFile, page.evaluate(function(selector) {
    // work out how to clip the screen shot around the selected element
    try {
      var clipRect = document.querySelector(selector).getBoundingClientRect();
      return {
        top: clipRect.top,
        left: clipRect.left,
        width: clipRect.width,
        height: clipRect.height
      };
    } catch (e) {
      console.log("Unable to fetch bounds for element " + selector, "warning");
    }
  }, selector));
};
