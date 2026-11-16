function getConfig() {
  var config = {};
  if (typeof process.env.API_HOST === 'undefined') {
    config.apiHost = '';
  } else {
    config.apiHost = process.env.API_HOST;
  }
  // URL of the .pmtiles basemap file, baked in at build time. For local
  // development, serve the file with a server that supports HTTP range requests
  // and CORS, and build with e.g.:
  //   npx http-server -p 8081 --cors   (in the directory holding uk.pmtiles)
  //   BASEMAP_URL=http://localhost:8081/uk.pmtiles npm run watch
  if (typeof process.env.BASEMAP_URL === 'undefined') {
    config.basemapUrl = '/tiles/uk.pmtiles';
  } else {
    config.basemapUrl = process.env.BASEMAP_URL;
  }
  return config;
}
module.exports = getConfig();
