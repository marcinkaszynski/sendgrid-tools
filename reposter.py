#!/usr/bin/python

"""Reposter/splitter service for SendGrid Event API.

Usage:

1. Copy sample_settings.py to settings.py.

2. Customize the REPOSTER_PORT, make sure it's open to the outside
   world, set it up as Event webhook URL in the SendGrid panel.

3. Put the list of your deployments in DEPLOYMENT_URLS.  Example:

@@@
DEPLOYMENT_URLS = {
    'ci-server': 'http://buildbot.marcinkaszynski.com:1234',
    'devel': 'http://devel.marcinkaszynski.com:10001',
}
@@@

4. Modify your mail-sending code to add deployment name to each
   message you send using a unique argument named 'deployment'.  For
   details how to use unique arguments in general see:

   http://sendgrid.com/docs/API_Reference/SMTP_API/unique_arguments.html
   http://sendgrid.com/docs/API_Reference/Web_API/mail.html

   Look for x-smtpapi header/parameter.

5. Start reposter.  It will receive messages from SendGrid and repost
   to your deployments based on each event's unique_args.deployment.

"""

import json
import logging

from twisted.internet import reactor, task
from twisted.web.client import getPage
from twisted.web.server import Site

from twisted.web.resource import Resource

import settings

class Uploader(object):
    def __init__(self, name, url):
        self.name = name
        self.url = url

        self.deferred = None
        self.queue = []

    def append(self, event):
        self.queue.append(event)
        
    def run(self):
        if self.deferred or (len(self.queue) == 0):
            return

        self.events_being_sent = self.queue
        self.queue = []

        self.deferred = getPage(self.url,
                                headers={},
                                method="POST",
                                postdata=json.dumps(self.events_being_sent))
        self.deferred.addCallback(self.deferred_callback)
        self.deferred.addErrback(self.deferred_errback)
        
    def deferred_callback(self, response):
        logging.info("Uploaded %d events to %s", len(self.events_being_sent), self.name)
        self.events_being_sent = []
        self.deferred = None

    def deferred_errback(self, error):
        logging.error("Could not upload events for %s: %s", self.name, repr(error))
        # Throw the events back into queue
        self.queue = self.events_being_sent + self.queue
        self.deferred = None


class EventDispatcher(object):
    def __init__(self):
        self.uploaders = {}
        for name, url in settings.DEPLOYMENT_URLS.items():
            self.uploaders[name] = Uploader(name, url)
        logging.info("%d uploaders: %r", len(self.uploaders.keys()), self.uploaders.keys())

    def add_event(self, event):
        name = self.get_uploader_name(event)
        logging.info("ADD_EVENT: %s %s -> uploader %s", event['event'], event['email'], name)
        self.uploaders[name].append(event)
    
    def dispatch(self):
        logging.info("DISPATCH: %s", [(name, len(uploader.queue))
                                      for (name, uploader) in self.uploaders.items()])
        for uploader in self.uploaders.values():
            uploader.run()

    def get_uploader_name(self, event):
        return event.get('unique_args', {}).get('deployment', 'DEFAULT')


class EventHandler(Resource):
    isLeaf = True

    def __init__(self, dispatcher, *args, **kwargs):
        Resource.__init__(self, *args, **kwargs)
        self.dispatcher = dispatcher
    
    def render_POST(self, request):
        for event in json.loads(request.content.read()):
            self.dispatcher.add_event(event)
        self.dispatcher.dispatch()
        return "OK"


def main():
    dispatcher = EventDispatcher()
    task.LoopingCall(dispatcher.dispatch).start(5.0)
    
    resource = EventHandler(dispatcher)
    factory = Site(resource)
    logging.info("Starting server on port %r" % settings.REPOSTER_PORT)
    reactor.listenTCP(settings.REPOSTER_PORT, factory)
    reactor.run()

logging.basicConfig(format='%(asctime)s %(levelname)s:%(message)s', level=logging.DEBUG)
main()
