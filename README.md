sendgrid-tools
==============

WARNING: these are for testing and development ONLY.  Do NOT use them
for production.  Set up a dedicated subuser to let SendGrid talk to
your production server directly.

SendGrid Event API lets you specify only a single webhook for every
user or subuser.  Scripts in this repo make it possible to use a
single URL (a single SG user) for multiple deployments.

Reposter
========

This script acts as a splitter: it publishes an HTTP server that will
accept POST requests from SendGrid Event API and reposts them based on
the value of event['unique_args']['deployment'].  Copy
sample_settings.py to settings.py, customize, start reposter.py.

