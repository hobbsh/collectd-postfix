#!/usr/bin/env python
# Author: Wylie Hobbs - 2017
#

import collectd
import socket
import datetime
import re

NAME = 'postfix'
VERBOSE_LOGGING = False
MAILLOG = '/var/log/maillog'
MAILLOG_CHUNK = -300000
CHECK_MAILQUEUE = False
METRICS = {
  "connection-in-open": "postfix/smtpd[[0-9]+]: connect from",
  "connection-in-close": "postfix/smtpd[[0-9]+]: disconnect from",
  "connection-in-lost": "postfix/smtpd[[0-9]+]: lost connection after .* from",
  "connection-in-timeout": "postfix/smtpd[[0-9]+]: timeout after .* from",
  "connection-in-TLS-setup": "postfix/smtpd[[0-9]+]: setting up TLS connection from",
  "connection-in-TLS-established": "postfix/smtpd[[0-9]+]: [A-Za-z]+ TLS connection established from",
  "connection-out-TLS-setup": "postfix/smtpd[[0-9]+]: setting up TLS connection to",
  "connection-out-TLS-established": "postfix/smtpd[[0-9]+]: [A-Za-z]+ TLS connection established to",
  "ipt_bytes": "size=([0-9]*)",
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

  if CHECK_MAILQUEUE:
    code_counts, q_size = process_mailqueue()
    metric_counts['total-queue-size'] = q_size
    for code, value in code_counts.items():
      index = 'queue-reason-%s' % code
      metric_counts[index] = value

  if VERBOSE_LOGGING:
    logger('info', metric_counts)
    
  return metric_counts

def process_mailqueue():
  messages = parse_mailqueue()
  code_counts = dict()
  total_queue_size = 0
  for msg in messages:
    code = re.search('.*said:\s+(\d+)\s.*', msg['reason'])
    total_queue_size += int(msg['size'])
    if code:
      response_code = code.group(1)
      try:
        code_counts[response_code] += 1
      except KeyError, e:
        code_counts[response_code] = 1

  return code_counts, total_queue_size

def parse_mailqueue():
  from subprocess import Popen, PIPE, STDOUT
  messages = []
  cmd = 'mailq'
  p = Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
  output = p.stdout
  hre = '.*Queue ID.*'
  idre = '^(?P<id>[0-9A-Z]+)\s+(?P<size>[0-9]+)\s+(?P<dow>\S+)\s+(?P<mon>\S+)\s+(?P<day>[0-9]+)\s+(?P<time>\S+)\s+(?P<sender>\S+)(?:\n|\r)(?P<reason>\(.*\w+.*\S+)(?:\n|\r)\s+(?P<recipient>[\w\@\w\.\w]+)'

  lines = re.split('\n\n', output.read())
  for line in lines:
    line = line.rstrip()
    if re.search(hre,line): continue
    id_match = re.finditer(idre, line)
    for m in re.finditer(idre, line):
      messages.append(m.groupdict())

  return messages

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
    #In smaller than 60 second collection intervals, there are issues with null data
    try:
      delay = (sum(float(i) for i in matches) / len(matches))
    except ZeroDivisionError:
      delay = 0
    return delay
  elif metric_name == 'ipt_bytes':
    ipt_bytes = (sum(int(i) for i in matches))
    return ipt_bytes
  else:
    return len(matches)

def configure_callback(conf):
  global MAILLOG, VERBOSE_LOGGING, CHECK_MAILQUEUE
  MAILLOG = ""
  VERBOSE_LOGGING = False
  CHECK_MAILQUEUE = False
  for node in conf.children:
    if node.key == "Verbose":
      VERBOSE_LOGGING = bool(node.values[0])
    elif node.key == "Maillog":
      MAILLOG = node.values[0]
    elif node.key == "CheckMailQ":
      CHECK_MAILQUEUE = bool(node.values[0])
    else:
      logger('warn', 'Unknown config key: %s' % node.key)

def read_callback():
  logger('verb', "beginning read_callback")
  info = get_stats()

  if not info or all(metric == 0 for metric in info.values()):
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
