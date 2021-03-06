#!/usr/bin/env python3
"""
Script to backfill database information on ZoneMinder Events.

<https://github.com/jantman/home-automation-configs/blob/master/zoneminder/zmevent_backfiller.py>

Configuration is in ``zmevent_config.py``.

Program flow:

- Searches all Events in ZM database since ``FIRST_EVENT_ID`` for ones that do
  not exist in ``ANALYSIS_TABLE_NAME`` and runs analysis/handling on them.

The functionality of this script relies on the other ``zmevent_*.py`` modules
in this git repo.
"""

import sys
import os
import logging
import argparse
from time import sleep

try:
    import pymysql
except ImportError:
    raise SystemExit(
        'could not import pymysql - please "pip install PyMySQL"'
    )

# This is running from a git clone, not really installed
sys.path.append(os.path.dirname(os.path.realpath(__file__)))

# Imports from this directory
from zmevent_config import (
    ANALYSIS_TABLE_NAME, CONFIG
)
from zmevent_handler import (
    handle_event, populate_secrets, setup_library_logging
)
from zm_videoizer import set_log_debug, set_log_info

FORMAT = "[%(asctime)s %(levelname)s] %(message)s"
logging.basicConfig(level=logging.WARNING, format=FORMAT)
logger = logging.getLogger()
setup_library_logging()

for lname in ['urllib3']:
    l = logging.getLogger(lname)
    l.setLevel(logging.WARNING)
    l.propagate = True


class ZmEventBackfiller(object):

    def __init__(self):
        logger.debug('Connecting to MySQL')
        self._conn = pymysql.connect(
            host='localhost', user=CONFIG['MYSQL_USER'],
            password=CONFIG['MYSQL_PASS'], db=CONFIG['MYSQL_DB'],
            charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor
        )

    def run(self, min_event_id, sleep_time=0):
        events = self._find_events(min_event_id)
        logger.info('Found %d events needing analysis', len(events))
        count = 0
        for evt in events:
            count += 1
            print('Handling event: %s' % evt)
            handle_event(evt['Id'], evt['MonitorId'], evt['Cause'])
            print('Finished event %d of %d' % (count, len(events)))
            if sleep_time > 0:
                logger.debug('Sleeping for %s', sleep_time)
                sleep(sleep_time)
        print('Done.')

    def _find_events(self, min_event_id):
        logger.info(
            'Looking for events after %d needing analysis...', min_event_id
        )
        sql = 'SELECT Id,MonitorId,Cause FROM Events WHERE Id ' \
              'NOT IN ( ' \
              'SELECT EventId FROM %s' \
              ') AND Id > %d;' % (ANALYSIS_TABLE_NAME, min_event_id)
        with self._conn.cursor() as cursor:
            logger.debug('EXECUTE: %s', sql)
            cursor.execute(sql)
            result = cursor.fetchall()
        logger.debug('Got %d results', len(result))
        return result


def parse_args(argv):
    """Parse command line arguments with ArgumentParser."""
    p = argparse.ArgumentParser(description='handler for Motion events')
    p.add_argument('-v', '--verbose', dest='verbose', action='count', default=0,
                   help='verbose output. specify twice for debug-level output.')
    p.add_argument('-s', '--sleep', dest='sleep', action='store', default=0.0,
                   type=float, help='Time to sleep between each event')
    p.add_argument('FIRST_EVENT_ID', action='store', type=int,
                   help='first Event ID to check')
    args = p.parse_args(argv)
    return args


def main():
    # populate secrets from environment variables
    populate_secrets()
    # parse command line arguments
    args = parse_args(sys.argv[1:])
    # set logging level
    if args.verbose > 1:
        set_log_debug()
    else:
        set_log_info()
    ZmEventBackfiller().run(args.FIRST_EVENT_ID, sleep_time=args.sleep)


if __name__ == "__main__":
    main()
