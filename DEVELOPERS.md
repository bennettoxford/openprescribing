# Development

If you're planning to work on OpenPrescribing,
then start by running `just`.
Never heard of [Just][]?
Then start by [installing it][1].

## System dependencies

Just aside,
OpenPrescribing has a small number of system dependencies:

* [Docker][], or a Docker alternative
* [GDAL][], the Geospatial Data Abstraction Library[^1]
* [GEOS][], the Geometry Engine Open Source
* [Node.js][]
* [PhantomJS][]

**Docker**, or a Docker alternative, is required to run several services
and for building the base and test images.
On macOS, the container runtime should support Linux-like host mode networking.
See [TESTING.md][] for more information.

**GDAL and GEOS** are required by [GeoDjango][].
The "[Installing geospatial libraries][2]" page in the GeoDjango docs has instructions for installing them.
Note that you need not install the other geospatial libraries mentioned on that page.
If you install GDAL and GEOS with Homebrew on macOS,
then you will need to add simlinks from the Homebrew library directory to the default library directory:

```sh
ln -s /opt/homebrew/lib/libgdal.dylib /usr/local/lib/libgdal.dylib

ln -s /opt/homebrew/lib/libgeos_c.dylib /usr/local/lib/libgeos_c.dylib
```

See "[Django: fuss-free use of Homebrew GDAL/GEOS libraries on macOS][]" for more information.

**Node.js** is required to install/build the front end dependencies/assets.
As with other Bennett Institute projects,
[Fast Node Manager][] (`fnm`) is recommended.

**PhantomJS** is required to generate, and test the generation of, alert emails.
Download a suitable binary from the "[Download PhantomJS][3]" page in the docs
and ensure `phantomjs` is in the search path (`PATH`).

## Testing

See [TESTING.md][].

## A note on environment variables

`justfile` will load environment variables from a `.env` file (a "dot env" file),
which is ignored by Git.
If you want to set environment variables,
then set them in a `.env` file.
There are a small number of environment variables you may want to set in [TESTING.md][].

Various modules will also attempt to load environment variables from an `environment` file,
which is also ignored by Git.
Don't set environment variables in an `environment` file;
doing so makes working on OpenPrescribing much harder,
as you have to maintain separate versions of this file for development and testing.

[1]: https://just.systems/man/en/installation.html
[2]: https://docs.djangoproject.com/en/5.0/ref/contrib/gis/install/geolibs/
[3]: https://phantomjs.org/download.html
[Django: fuss-free use of Homebrew GDAL/GEOS libraries on macOS]: https://adamj.eu/tech/2024/03/20/django-homebrew-gdal-geos/
[Docker]: https://www.docker.com/
[Fast Node Manager]: https://github.com/Schniz/fnm
[GDAL]: https://gdal.org/en/stable/
[GEOS]: https://libgeos.org/
[GeoDjango]: https://docs.djangoproject.com/en/5.0/ref/contrib/gis/
[Just]: https://just.systems/
[Node.js]: https://nodejs.org/en
[PhantomJS]: http://phantomjs.org/
[TESTING.md]: TESTING.md

[^1]: I've seen GDAL described as the "Swiss Army knife" of geospatial data.
  Like all Swiss Army knives,
  it has one well-used feature (the corkscrew),
  many seldom-used features (the fish scaler, the reamer),
  and you accidentally cut yourself when you first try to open one.
