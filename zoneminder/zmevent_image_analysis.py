#!/usr/bin/env python3

import os
import time
import logging
from textwrap import dedent
import requests
from shapely.geometry.polygon import LinearRing, Polygon
from zmevent_config import IGNORED_OBJECTS
import pymysql
import json

from zmevent_config import CONFIG, ANALYSIS_TABLE_NAME, DateSafeJsonEncoder

try:
    import cv2
except ImportError:
    raise SystemExit(
        'could not import cv2 - please "pip install opencv-python"'
    )
try:
    from pydarknet import Detector, Image
except ImportError:
    raise SystemExit(
        'could not import pydarknet - please "pip install yolo34py" or '
        '"pip install yolo34py-gpu"'
    )


logger = logging.getLogger(__name__)

#: Path on disk where darknet yolo configs/weights will be stored
YOLO_CFG_PATH = '/var/cache/zoneminder/yolo'
YOLO_ALT_CFG_PATH = '/var/cache/zoneminder/yolo-alt'


class suppress_stdout_stderr(object):
    """
    Context manager to do "deep suppression" of stdout and stderr.

    from: https://stackoverflow.com/q/11130156/211734

    A context manager for doing a "deep suppression" of stdout and stderr in
    Python, i.e. will suppress all print, even if the print originates in a
    compiled C/Fortran sub-function.
       This will not suppress raised exceptions, since exceptions are printed
    to stderr just before a script exits, and after the context manager has
    exited (at least, I think that is why it lets exceptions through).
    """

    def __init__(self):
        # Open a pair of null files
        self.null_fds = [os.open(os.devnull, os.O_RDWR) for x in range(2)]
        # Save the actual stdout (1) and stderr (2) file descriptors.
        self.save_fds = [os.dup(1), os.dup(2)]

    def __enter__(self):
        # Assign the null pointers to stdout and stderr.
        os.dup2(self.null_fds[0],1)
        os.dup2(self.null_fds[1],2)

    def __exit__(self, *_):
        # Re-assign the real stdout/stderr back to (1) and (2)
        os.dup2(self.save_fds[0],1)
        os.dup2(self.save_fds[1],2)
        # Close all file descriptors
        for fd in self.null_fds + self.save_fds:
            os.close(fd)


class ImageAnalysisWrapper(object):
    """Wraps calling the ``ANALYZER`` classes and storing their results."""

    def __init__(self, event, analyzers):
        self._event = event
        logger.debug('Connecting to MySQL')
        self._conn = pymysql.connect(
            host='localhost', user=CONFIG['MYSQL_USER'],
            password=CONFIG['MYSQL_PASS'], db=CONFIG['MYSQL_DB'],
            charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor
        )
        self._analyzers = analyzers

    def _result_to_db(self, result, frame):
        """Write an ObjectDetectionResult instance to DB"""
        sql = 'INSERT INTO `' + ANALYSIS_TABLE_NAME + \
              '` (`MonitorId`, `ZoneId`, `EventId`, `FrameId`, ' \
              '`AnalyzerName`, `RuntimeSec`, `Results`, `IgnoredResults`) ' \
              'VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ' \
              'ON DUPLICATE KEY UPDATE `RuntimeSec`=%s, `Results`=%s,' \
              '`IgnoredResults`=%s'
        with self._conn.cursor() as cursor:
            res_json = json.dumps(result.detections, cls=DateSafeJsonEncoder)
            ign_json = json.dumps(
                result.ignored_detections, cls=DateSafeJsonEncoder
            )
            args = [
                self._event.MonitorId,
                0,  # ZoneId
                self._event.EventId,
                frame.FrameId,
                result.analyzer_name,
                '%.2f' % result.runtime,
                res_json,
                ign_json,
                '%.2f' % result.runtime,
                res_json,
                ign_json
            ]
            try:
                logger.debug('EXECUTING: %s; ARGS: %s', sql, args)
                cursor.execute(sql, args)
                self._conn.commit()
            except Exception:
                logger.error(
                    'ERROR executing %s; for %s',
                    sql, self._event, exc_info=True
                )

    def analyze_event(self):
        """returns a list of ObjectDetectionResult instances"""
        results = []
        for a in self._analyzers:
            logger.debug('Running object detection with: %s', a)
            cls = a(self._event)
            for frame in self._event.FramesForAnalysis.values():
                res = cls.analyze(frame)
                results.append(res)
                try:
                    self._result_to_db(res, frame)
                except Exception:
                    logger.critical(
                        'Exception writing analysis result to DB for %s %s',
                        self._event, a.__name__, exc_info=True
                    )
        return results


class DetectedObject(object):

    def __init__(self, label, zones, score, x, y, w, h, ignore_reason=None):
        self._label = label
        self._zones = zones
        self._score = score
        self._x = x
        self._y = y
        self._w = w
        self._h = h
        self._ignore_reason = None

    @property
    def as_dict(self):
        return {
            'label': self._label,
            'zones': self._zones,
            'score': self._score,
            'x': self._x,
            'y': self._y,
            'w': self._w,
            'h': self._h,
            'ignore_reason': self._ignore_reason
        }


class ObjectDetectionResult(object):

    def __init__(
        self, analyzer_name, frame, frame_path, detected_path, detections,
        ignored_detections, runtime
    ):
        """
        Class to represent the results of running object detection on an image.

        :param analyzer_name: name of the analyzer class used
        :type analyzer_name: str
        :param frame: the Frame that was analyzed
        :type frame: Frame
        :param frame_path: path to the raw frame to analyze on disk
        :type frame_path: str
        :param detected_path: path to the output image with labels
        :type detected_path: str
        :param detections: list of DetectedObject instances
        :type detections: list
        """
        self.analyzer_name = analyzer_name
        self.frame_path = frame_path
        self.detected_path = detected_path
        self.detections = detections
        self.ignored_detections = ignored_detections
        self.runtime = runtime
        self._frame = frame

    @property
    def as_dict(self):
        return {
            'analyzer_name': self.analyzer_name,
            'frame_path': self.frame_path,
            'output_path': self.detected_path,
            'detections': self.detections,
            'ignored_detections': self.ignored_detections,
            'runtime': self.runtime,
            'EventId': self._frame.EventId,
            'FrameId': self._frame.FrameId
        }


class ImageAnalyzer(object):
    """
    Base class for specific object detection algorithms/packages.
    """

    def __init__(self, event):
        """
        Initialize an image analyzer.

        :param event: the event to analyze
        :type event: ZMEvent
        """
        self._event = event

    def analyze(self, frame_path):
        """
        Analyze a frame; return an ObjectDetectionResult.
        """
        raise NotImplementedError('Implement in subclass!')


class YoloAnalyzer(ImageAnalyzer):
    """Object detection using yolo34py and yolov3-tiny"""

    def __init__(self, event):
        super(YoloAnalyzer, self).__init__(event)
        self._ensure_configs()
        logger.info('Instantiating YOLO3 Detector...')
        with suppress_stdout_stderr():
            self._net = Detector(
                bytes(self._config_path("yolov3.cfg"), encoding="utf-8"),
                bytes(self._config_path("yolov3.weights"), encoding="utf-8"),
                0,
                bytes(self._config_path("coco.data"), encoding="utf-8")
            )
        logger.debug('Done instantiating YOLO3 Detector.')

    def _ensure_configs(self):
        """Ensure that yolov3-tiny configs and data are in place."""
        # This uses the yolov3-tiny, because I only have a 1GB GPU
        if not os.path.exists(YOLO_CFG_PATH):
            logger.warning('Creating directory: %s', YOLO_CFG_PATH)
            os.mkdir(YOLO_CFG_PATH)
        configs = {
            'yolov3.cfg': 'https://raw.githubusercontent.com/pjreddie/darknet/'
                          'master/cfg/yolov3-tiny.cfg',
            'coco.names': 'https://raw.githubusercontent.com/pjreddie/darknet/'
                          'master/data/coco.names',
            'yolov3.weights': 'https://pjreddie.com/media/files/'
                              'yolov3-tiny.weights'
        }
        for fname, url in configs.items():
            path = self._config_path(fname)
            if os.path.exists(path):
                continue
            logger.warning('%s does not exist; downloading', path)
            logger.info('Download %s to %s', url, path)
            r = requests.get(url)
            logger.info('Writing %d bytes to %s', len(r.content), path)
            with open(path, 'wb') as fh:
                fh.write(r.content)
            logger.debug('Wrote %s', path)
        # coco.data is special because we change it
        path = self._config_path('coco.data')
        if not os.path.exists(path):
            content = dedent("""
            classes= 80
            train  = /home/pjreddie/data/coco/trainvalno5k.txt
            valid = %s
            names = %s
            backup = /home/pjreddie/backup/
            eval=coco
            """)
            logger.warning('%s does not exist; writing', path)
            with open(path, 'w') as fh:
                fh.write(content % (
                    self._config_path('coco_val_5k.list'),
                    self._config_path('coco.names')
                ))
            logger.debug('Wrote %s', path)

    def _config_path(self, f):
        return os.path.join(YOLO_CFG_PATH, f)

    def do_image_yolo(self, frame, fname, detected_fname):
        """
        Analyze a single image using yolo34py.

        :param frame: the Frame being analyzed
        :type frame: Frame
        :param fname: path to input image
        :type fname: str
        :param detected_fname: file path to write object detection image to
        :type detected_fname: str
        :return: yolo3 detection results
        :rtype: list of DetectedObject instances
        """
        logger.debug('Starting: %s', fname)
        img = cv2.imread(fname)
        img2 = Image(img)
        results = self._net.detect(img2, thresh=0.2, hier_thresh=0.3, nms=0.4)
        logger.debug('Raw Results: %s', results)
        retval = {'detections': [], 'ignored_detections': []}
        for cat, score, bounds in results:
            if not isinstance(cat, str):
                cat = cat.decode()
            x, y, w, h = bounds
            zones = self._zones_for_object(frame, x, y, w, h)
            logger.debug('Checking IgnoredObject filters for detections...')
            matched_filters = [
                foo.name for foo in IGNORED_OBJECTS
                if foo.should_ignore(cat, x, y, zones, score)
            ]
            if len(matched_filters) > 0:
                # object should be ignored
                logger.info(
                    '%s: Ignoring %s (%.2f) at %d,%d based on filters: %s',
                    frame, cat, score, x, y, matched_filters
                )
                rect_color = (104, 104, 104)
                text_color = (111, 247, 93)
                retval['ignored_detections'].append(DetectedObject(
                    cat, zones, score, x, y, w, h, ignore_reason=matched_filters
                ))
            else:
                # object should not be ignored; add to result
                rect_color = (255, 0, 0)
                text_color = (255, 255, 0)
                retval['detections'].append(DetectedObject(
                    cat, zones, score, x, y, w, h
                ))
            cv2.rectangle(
                img, (int(x - w / 2), int(y - h / 2)),
                (int(x + w / 2), int(y + h / 2)), rect_color, thickness=2
            )
            cv2.putText(
                img, '%s (%.2f)' % (cat, score),
                (int(x), int(y)),
                cv2.FONT_HERSHEY_COMPLEX, 1, text_color
            )
        logger.info('Writing: %s', detected_fname)
        cv2.imwrite(detected_fname, img)
        logger.info('Done with: %s', fname)
        return retval

    def _xywh_to_ring(self, x, y, width, height):
        points = [
            (x - (width / 2.0), y - (height / 2.0)),
            (x - (width / 2.0), y + (height / 2.0)),
            (x + (width / 2.0), y + (height / 2.0)),
            (x + (width / 2.0), y - (height / 2.0)),
            (x - (width / 2.0), y - (height / 2.0))
        ]
        return Polygon(LinearRing(points))

    def _zones_for_object(self, frame, x, y, w, h):
        res = {}
        obj_polygon = self._xywh_to_ring(x, y, w, h)
        for zone in frame.event.Monitor.Zones.values():
            if obj_polygon.intersects(zone.polygon):
                amt = (
                    obj_polygon.intersection(zone.polygon).area /
                    obj_polygon.area
                ) * 100
                res[zone.Name] = amt
        return res

    def analyze(self, frame):
        _start = time.time()
        # get all the results
        frame_path = frame.path
        output_path = frame_path.replace('.jpg', '.yolo3.jpg')
        res = self.do_image_yolo(frame, frame_path, output_path)
        _end = time.time()
        return ObjectDetectionResult(
            self.__class__.__name__,
            frame,
            frame_path,
            output_path,
            res['detections'],
            res['ignored_detections'],
            _end - _start
        )


class AlternateYoloAnalyzer(YoloAnalyzer):
    """
    This is used when I run from a script in a separate venv to compare CPU and
    GPU results.
    """

    def _config_path(self, f):
        return os.path.join(YOLO_ALT_CFG_PATH, f)

    def _ensure_configs(self):
        """Ensure that yolov3-tiny configs and data are in place."""
        # This uses the yolov3-tiny, because I only have a 1GB GPU
        if not os.path.exists(YOLO_ALT_CFG_PATH):
            logger.warning('Creating directory: %s', YOLO_ALT_CFG_PATH)
            os.mkdir(YOLO_ALT_CFG_PATH)
        configs = {
            'yolov3.cfg': 'https://raw.githubusercontent.com/pjreddie/darknet/'
                          'master/cfg/yolov3.cfg',
            'coco.names': 'https://raw.githubusercontent.com/pjreddie/darknet/'
                          'master/data/coco.names',
            'yolov3.weights': 'https://pjreddie.com/media/files/'
                              'yolov3.weights'
        }
        for fname, url in configs.items():
            path = self._config_path(fname)
            if os.path.exists(path):
                continue
            logger.warning('%s does not exist; downloading', path)
            logger.info('Download %s to %s', url, path)
            r = requests.get(url)
            logger.info('Writing %d bytes to %s', len(r.content), path)
            with open(path, 'wb') as fh:
                fh.write(r.content)
            logger.debug('Wrote %s', path)
        # coco.data is special because we change it
        path = self._config_path('coco.data')
        if not os.path.exists(path):
            content = dedent("""
            classes= 80
            train  = /home/pjreddie/data/coco/trainvalno5k.txt
            valid = %s
            names = %s
            backup = /home/pjreddie/backup/
            eval=coco
            """)
            logger.warning('%s does not exist; writing', path)
            with open(path, 'w') as fh:
                fh.write(content % (
                    self._config_path('coco_val_5k.list'),
                    self._config_path('coco.names')
                ))
            logger.debug('Wrote %s', path)

    def analyze(self, frame):
        _start = time.time()
        # get all the results
        frame_path = frame.path
        output_path = frame_path.replace('.jpg', '.yolo3alt.jpg')
        res = self.do_image_yolo(frame, frame_path, output_path)
        _end = time.time()
        return ObjectDetectionResult(
            self.__class__.__name__,
            frame,
            frame_path,
            output_path,
            res['detections'],
            res['ignored_detections'],
            _end - _start
        )
