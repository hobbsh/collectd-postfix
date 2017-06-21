#!/usr/bin/env python
# Author: Wylie Hobbs - 2017
#

import collectd
import socket
import datetime
import subprocess
import re

NAME = 'postfix'
VERBOSE_LOGGING = False
MAILLOG = '/var/log/maillog'
MAILLOG_CHUNK = -300000
METRICS = {
  "connection-in-open": "postfix/smtpd[[0-9]+]: connect from",
  "connection-in-close": "postfix/smtpd[[0-9]+]: disconnect from",
  "connection-in-lost": "postfix/smtpd[[0-9]+]: lost connection after .* from",
  "connection-in-timeout": "postfix/smtpd[[0-9]+]: timeout after .* from",
  "connection-in-TLS-setup": "postfix/smtpd[[0-9]+]: setting up TLS connection from",
  "connection-in-TLS-established": "postfix/smtpd[[0-9]+]: [A-Za-z]+ TLS connection established from",
  "connection-out-TLS-setup": "postfix/smtpd[[0-9]+]: setting up TLS connection to",
  "connection-out-TLS-established": "postfix/smtpd[[0-9]+]: [A-Za-z]+ TLS connection established to",
  "status-deferred": "status=deferred",
  "status-forwarded": "status=forwarded",
  "status-reject": "status=reject",
  "status-sent": "status=sent",
  "status-bounced": "status=bounced",
  "status-softbounce": "status=SOFTBOUNCE",
  "rejected": "554\ 5\.7\.1",
  "rejected-host_not_found": "450\ 4\.7\.1.*Helo command rejected: Host not found",
  "rejected-spam_or_forged": "450\ 4\.7\.1.*Client host rejected: Mail appeared to be SPAM or forged",
  "rejected-no_dns_entry": "450\ 4\.7\.1.*Client host rejected: No DNS entries for your MTA, HELO and Domain",
  "delay": "delay=([\.0-9]*)",
  "delay-before_queue_mgr": "delays=([\.0-9]*)/[\.0-9]*/[\.0-9]*/[\.0-9]*",
  "delay-in_queue_mgr": "delays=[\.0-9]*/([\.0-9]*)/[\.0-9]*/[\.0-9]*",
  "delay-setup_time": "delays=[\.0-9]*/[\.0-9]*/([\.0-9]*)/[\.0-9]*",
  "delay-trans_time": "delays=[\.0-9]*/[\.0-9]*/[\.0-9]*/([\.0-9]*)"
}

def get_stats():
  now = datetime.datetime.now()
  last_minute = (now - datetime.timedelta(minutes=1)).strftime("%b %d %H:%M")
  metric_counts = {}
  log_chunk = read_log()
  for metric_name, metric_regex in METRICS.iteritems():
    metric_regex = "%s.*%s" % (last_minute, metric_regex)
    count = parse_log(log_chunk, metric_name, metric_regex)
    metric_counts[metric_name] = count

  if VERBOSE_LOGGING:
    logger('info', metric_counts)

  return metric_counts

""" 
Read last ~300KB of data to make sure we get at least the whole last minute
NOTE: If your metrics are getting truncated because you have a lot of maillog volume, increase MAILLOG_CHUNK
  MAILLOG_CHUNK should always be negative - for more reading look at the python seek() docs
"""
def read_log():
  f = open(MAILLOG, 'r')
  f.seek(MAILLOG_CHUNK, 2)
  lines = f.read()
  return lines

# Return average delay or count of matched lines for each metric_name/regex pair
def parse_log(lines, metric_name, metric_regex):
  matches = re.findall(metric_regex, lines)
  if VERBOSE_LOGGING:
    logger('info',  matches)
  if 'delay' in metric_name:
    try:
      delay = (sum(float(i) for i in matches) / len(matches))
    except ZeroDivisionError:
      delay = 0
    return delay
  else:
    return len(matches)

def configure_callback(conf):
  global MAILLOG, VERBOSE_LOGGING
  MAILLOG = ""
  VERBOSE_LOGGING = False
  for node in conf.children:
    if node.key == "Verbose":
      VERBOSE_LOGGING = bool(node.values[0])
    elif node.key == "Maillog":
      MAILLOG = node.values[0]
    else:
      logger('warn', 'Unknown config key: %s' % node.key)

def read_callback():
  logger('verb', "beginning read_callback")
  info = get_stats()

  if not info:
    logger('warn', "%s: No data received" % NAME)
    return

  for key,value in info.items():
    key_name = key
    val = collectd.Values(plugin=NAME, type='gauge')
    val.type_instance = key_name
    val.values = [ value ]
    val.dispatch()

def logger(t, msg):
    if t == 'err':
      collectd.error('%s: %s' % (NAME, msg))
    elif t == 'warn':
      collectd.warning('%s: %s' % (NAME, msg))
    elif t == 'verb':
      if VERBOSE_LOGGING:
        collectd.info('%s: %s' % (NAME, msg))
    else:
      collectd.notice('%s: %s' % (NAME, msg))

collectd.register_config(configure_callback)
collectd.register_read(read_callback)
