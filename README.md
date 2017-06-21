## collectd-postfix plugin

This plugin collects mail metrics from the postfix mail log. I have only tested this on CentOS 6 with Python 2.6.6

Example data in Grafana
![collectd-postfix-grafana](http://imgur.com/TrQJmzg)

## Supported Platforms

### Tested on
- CentOS 6 (Python 2.6)

## Usage

Follows standard collectd-python plugin configuration. You need to make sure your collectd binary was compiled with python support first.

- Drop `collectd-postfix.py` into `<COLLECTD_ROOT>/share/collectd/` - or wherever you store plugins
- Configure the plugin in your collectd config `<COLLECTD_ROOT>/etc/conf.d/postfix.conf` or however you include plugins


There are only two module config options at the moment - an example config:
```
<LoadPlugin python>
    Globals true
</LoadPlugin>

<Plugin python>
    # postfix.py is at /opt/collectd/share/collectd/postfix.py
    ModulePath "/opt/collectd/share/collectd/"
    Import "postfix"
    <Module postfix>
      Verbose false
      Maillog "/var/log/maillog"
    </Module>
</Plugin>
```


## Contribute

Create a feature branch and PR with changes if anything feels dirty or you would like to see additional functionality. 

### License
collectd-postfix is licensed under version 2.0 of the Apache License. See the LICENSE file for details.

