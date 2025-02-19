#!/usr/bin/env python
import logging.config
import signal

from aodncore.pipeline.log import get_pipeline_logger
from aodncore.pipeline.serviceconfig import CONFIG
from aodncore.pipeline.watch import WatchServiceContext, WatchServiceManager

logging.config.dictConfig(CONFIG.watchservice_logging_config)
LOGGER = get_pipeline_logger(CONFIG.pipeline_config['watch']['logger_name'])


def main():
    LOGGER.info("creating WatchServiceContext")
    context = WatchServiceContext(CONFIG)

    LOGGER.info("initialising WatchServiceManager")
    with WatchServiceManager(CONFIG, context.event_handler, context.watch_manager, context.notifier) as watch_manager:
        LOGGER.info("active watches: {watch_manager.watches}".format(watch_manager=watch_manager))

        # handle SIGTERM gracefully (e.g. from supervisord)
        signal.signal(signal.SIGTERM, watch_manager.handle_signal)

        LOGGER.info("starting Notifier event loop")
        watch_manager.notifier.loop()


if __name__ == '__main__':
    main()
