FROM python:3.12

LABEL maintainer="Seb Bacon version: 0.2"
ENV PYTHONUNBUFFERED 1
RUN mkdir /code
WORKDIR /code
ADD requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt && rm /tmp/requirements.txt
RUN apt-get update && apt-get install -y binutils libproj-dev gdal-bin libgeoip1 libgeos-c1v5 && apt-get clean && rm -rf /var/lib/apt/lists/*
# Install Node & NPM
RUN \
  cd $(mktemp --directory) && \
  curl --silent --location 'https://nodejs.org/dist/v24.22.3/node-v24.22.3-linux-x64.tar.gz' \
    | tar --no-same-owner --no-same-permissions -xzf - && \
  mv --no-target-directory node-* /usr/local/lib/node && \
  ln --symbolic /usr/local/lib/node/bin/node /usr/local/bin/node && \
  ln --symbolic /usr/local/lib/node/bin/node /usr/local/bin/nodejs && \
  ln --symbolic /usr/local/lib/node/bin/npm /usr/local/bin/npm && \
  rmdir "$PWD"
RUN mkdir /npm
ADD openprescribing/media/js /npm/
RUN ls -l /npm/
# Install npm outside the location where we'll eventually install the
# software, for symlinking back in as part of our docker-compose run
# command. This allows us to do all the install stuff in the image,
# rather than at runtime.
RUN cd /npm && npm install -g browserify@17.0.0 && npm install -g jshint@2.13.6 && npm install
# Install phantomjs
RUN curl -sL https://bitbucket.org/ariya/phantomjs/downloads/phantomjs-2.1.1-linux-x86_64.tar.bz2 > /tmp/phantomjs.tar.bz && tar -jxf /tmp/phantomjs.tar.bz -C /usr/local && ln -s /usr/local/phantomjs-2.1.1-linux-x86_64/bin/phantomjs /usr/local/bin && rm /tmp/phantomjs.tar.bz
