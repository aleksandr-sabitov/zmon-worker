import logging
import urllib
import json

import requests

from urllib2 import urlparse

from opentracing_utils import trace, extract_span_from_kwargs

from notification import BaseNotification

logger = logging.getLogger(__name__)


class NotifyHipchat(BaseNotification):
    @classmethod
    @trace(operation_name='notification_hipchat', pass_span=True, tags={'notification': 'hipchat'})
    def notify(cls, alert, *args, **kwargs):

        current_span = extract_span_from_kwargs(**kwargs)

        url = cls._config.get('notifications.hipchat.url')
        token = kwargs.get('token', cls._config.get('notifications.hipchat.token'))
        repeat = kwargs.get('repeat', 0)
        notify = kwargs.get('notify', False)
        alert_def = alert['alert_def']
        message_format = kwargs.get('message_format', 'html')

        current_span.set_tag('alert_id', alert_def['id'])

        entity = alert.get('entity')
        is_changed = alert.get('alert_changed', False)
        is_alert = alert.get('is_alert', False)

        current_span.set_tag('entity', entity['id'])
        current_span.set_tag('alert_changed', bool(is_changed))
        current_span.set_tag('is_alert', is_alert)

        current_span.log_kv({'room': kwargs.get('room')})

        color = 'green' if alert and not alert.get('is_alert') else kwargs.get('color', 'red')

        message_text = cls._get_subject(alert, custom_message=kwargs.get('message'))

        if kwargs.get('link', False):
            zmon_host = kwargs.get('zmon_host', cls._config.get('zmon.host'))
            alert_id = alert['alert_def']['id']
            alert_url = urlparse.urljoin(zmon_host, '/#/alert-details/{}'.format(alert_id)) if zmon_host else ''
            link_text = kwargs.get('link_text', 'go to alert')
            if message_format == 'html':
                message_text += ' -- <a href="{}" target="_blank">{}</a>'.format(alert_url, link_text)
            else:
                message_text += ' -- {} - {}'.format(link_text, alert_url)

        message = {
            'message': message_text,
            'color': color,
            'notify': notify,
            'message_format': message_format
        }

        try:
            logger.info(
                'Sending to: ' + '{}/v2/room/{}/notification?auth_token={}'.format(url, urllib.quote(kwargs['room']),
                                                                                   token) + ' ' + json.dumps(message))
            r = requests.post(
                '{}/v2/room/{}/notification'.format(url, urllib.quote(kwargs['room'])),
                json=message, params={'auth_token': token}, headers={'Content-type': 'application/json'})
            r.raise_for_status()
        except Exception as e:
            current_span.set_tag('error', True)
            current_span.log_kv({'exception': str(e)})
            logger.exception('Hipchat write failed!')

        return repeat
