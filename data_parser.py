#!/usr/bin/env python3
"""
MAVLink Router Prometheus Exporter

Conversion of MAVLink Router routing statistics output to Prometheus metrics

Author:   Oemer Yilmaz <yilmaz@consider-it.de>
Copyright: (c) consider it GmbH, 2022
"""

from enum import Enum
import os
import re
import time
import sys
import argparse
import logging


# PROMETHEUS METRIC NAMES
METRIC_REC_CRCERR_CNT = "mavlinkrouter_receive_crcerror_count"
METRIC_REC_CRCERR_PCT = "mavlinkrouter_receive_crcerror_percent"
METRIC_REC_CRCERR_KB = "mavlinkrouter_receive_crcerror_kilo_byte"
METRIC_REC_SEQLOST_CNT = "mavlinkrouter_receive_seqlost_count"
METRIC_REC_SEQLOST_PCT = "mavlinkrouter_receive_seqlost_percent"
METRIC_REC_HANDLED_CNT = "mavlinkrouter_receive_handled_count"
METRIC_REC_HANDLED_KB = "mavlinkrouter_receive_handled_kilo_byte"
METRIC_REC_TOTAL_CNT = "mavlinkrouter_receive_total_count"
METRIC_TRANSM_TOTAL_CNT = "mavlinkrouter_transmit_total_count"
METRIC_TRANSM_TOTAL_KB = "mavlinkrouter_transmit_total_kilo_byte"


# USER SETTINGS
DEFAULT_OUTPUT_DIR = "/var/local/"
PROM_FILE_NAME = "mavrouter_export.prom"
CACHE_FILE_NAME = "mavrouter_export.cache"


# CUSTOM DATA TYPES
class State(Enum):
    """ This enum declares the different states of the state machine used """
    IDLE = 0
    READ_RX_START = 1
    READ_RX_CRCERROR = 2
    READ_RX_SEQLOST = 3
    READ_RX_HANDLED = 4
    READ_RX_TOTAL = 5
    READ_TX_START = 6
    READ_TX_TOTAL = 7
    SEND_INFO = 8


# HELPERS
def write_output_file(output_file_path, cache_file_path):
    """
    Copy cache file contents to output file.

    As the output file should always contain a complete dataset, the data is first written to the
    cache file and then copied over in one (hopefully fast-enough) step.
    """
    input_file = open(cache_file_path, 'r', encoding="utf8")  # reopen to (only) read
    output_file = open(output_file_path, 'w+', encoding="utf8")

    # transfer all data from cache to output file
    for single_line in input_file.readlines():
        output_file.write(single_line)

    output_file.close()
    input_file.close()

    # clear cache file
    open(cache_file_path, 'w', encoding="utf8").close()


def write_metric_to_file(file, metric_name, endpoint_name, endpoint_conntype, endpoint_id, value):
    """ Writes a metric to the cache file with the according device name, conn type and so on """

    metric_str = '%s{conn_type="%s",endpoint_id="%s",endpoint_name="%s"} %s\n' % (
        metric_name, endpoint_conntype, endpoint_id, endpoint_name, value)

    file.write(metric_str)


def main():
    """ MAVLink Router Prometheus Exporter application setup and run-loop """
    log_format = '%(asctime)s %(levelname)s:%(name)s: %(message)s'
    log_datefmt = '%Y-%m-%dT%H:%M:%S%z'
    logging.basicConfig(format=log_format, datefmt=log_datefmt, level=logging.INFO)
    logger = logging.getLogger()

    parser = argparse.ArgumentParser(description='Mavrouter Prometheus Expoerter')
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT_DIR,
                        help="output directory")
    parser.add_argument("-v", "--verbosity", action="count",
                        help="increase output and logging verbosity")
    args = parser.parse_args()

    if args.verbosity == 2:
        logger.setLevel(logging.DEBUG)
    elif args.verbosity == 1:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.WARNING)

    # SETUP
    output_file_path = os.path.join(args.output, PROM_FILE_NAME)
    cache_file_path = os.path.join(args.output, CACHE_FILE_NAME)

    logger.info("Mavrouter Prometheus Expoerter")
    logger.info("- Writing to %s", args.output)

    # our state
    endpoint_conn_type = "DEFAULT"
    endpoint_id = "DEFAULT"
    endpoint_name = "DEFAULT"
    current_state = State.IDLE
    next_state = State.IDLE
    last_readline_time = sys.float_info.max  # float max, so it's not considered old in first run

    # RUN
    cache_file = open(cache_file_path, 'w+', encoding="utf8")

    while True:
        for line in sys.stdin:
            logger.debug("New line: %s", line[:-1])

            # Always reset to start state, if statistics start was found
            start_line_match = re.match(r"(\w+) Endpoint \[(\d+)\](\w*)", line)
            if start_line_match:
                endpoint_conn_type = start_line_match.group(1)
                endpoint_id = start_line_match.group(2)
                endpoint_name = start_line_match.group(3)

                logger.info("-> Start of %s %s (%s)", endpoint_conn_type,
                            endpoint_id, endpoint_name)

                # write output, if we haven't received data for nearly a second (since output is every two seconds)
                if last_readline_time < (time.time()-0.9):
                    logger.info("-> Writing cache to output file")
                    cache_file.close()
                    write_output_file(output_file_path, cache_file_path)
                    cache_file = open(cache_file_path, 'w+', encoding="utf8")

                next_state = State.READ_RX_START

            # Remaining state machine to parse the input data
            if current_state == State.IDLE:
                pass
            elif current_state == State.READ_RX_START:
                if line.find("Received messages") != -1:
                    next_state = State.READ_RX_CRCERROR
                else:
                    pass

            elif current_state == State.READ_RX_CRCERROR:
                if line.find("CRC error") != -1:
                    # regex to find the numbers within the line
                    digits = re.findall(r"\d+", line)
                    write_metric_to_file(cache_file, METRIC_REC_CRCERR_CNT,
                                         endpoint_name, endpoint_conn_type, endpoint_id, digits[0])
                    write_metric_to_file(cache_file, METRIC_REC_CRCERR_PCT,
                                         endpoint_name, endpoint_conn_type, endpoint_id, digits[1])
                    write_metric_to_file(cache_file, METRIC_REC_CRCERR_KB,
                                         endpoint_name, endpoint_conn_type, endpoint_id, digits[2])
                    next_state = State.READ_RX_SEQLOST
                else:
                    logger.warning("Expecting RX 'CRC error' line, but got: %s", line[:-1])

            elif current_state == State.READ_RX_SEQLOST:
                if line.find("Sequence lost") != -1:
                    digits = re.findall(r"\d+", line)
                    write_metric_to_file(cache_file, METRIC_REC_SEQLOST_CNT,
                                         endpoint_name, endpoint_conn_type, endpoint_id, digits[0])
                    write_metric_to_file(cache_file, METRIC_REC_SEQLOST_PCT,
                                         endpoint_name, endpoint_conn_type, endpoint_id, digits[1])
                    next_state = State.READ_RX_HANDLED
                else:
                    logger.warning("Expecting RX 'Sequence lost' line, but ot: %s", line[:-1])

            elif current_state == State.READ_RX_HANDLED:
                if line.find("Handled") != -1:
                    digits = re.findall(r"\d+", line)
                    write_metric_to_file(cache_file, METRIC_REC_HANDLED_CNT,
                                         endpoint_name, endpoint_conn_type, endpoint_id, digits[0])
                    write_metric_to_file(cache_file, METRIC_REC_HANDLED_KB,
                                         endpoint_name, endpoint_conn_type, endpoint_id, digits[1])
                    next_state = State.READ_RX_TOTAL
                else:
                    logger.warning("Expecting RX 'Handled' line, but got: %s", line[:-1])

            elif current_state == State.READ_RX_TOTAL:
                if line.find("Total") != -1:
                    digits = re.findall(r"\d+", line)
                    write_metric_to_file(cache_file, METRIC_REC_TOTAL_CNT,
                                         endpoint_name, endpoint_conn_type, endpoint_id, digits[0])
                    next_state = State.READ_TX_START
                else:
                    logger.warning("Expecting RX 'Total' line, but got: %s", line[:-1])

            elif current_state == State.READ_TX_START:
                if line.find("Transmitted messages") != -1:
                    next_state = State.READ_TX_TOTAL
                else:
                    pass

            elif current_state == State.READ_TX_TOTAL:
                if line.find("Total") != -1:
                    digits = re.findall(r"\d+", line)
                    write_metric_to_file(cache_file, METRIC_TRANSM_TOTAL_CNT,
                                         endpoint_name, endpoint_conn_type, endpoint_id, digits[0])
                    write_metric_to_file(cache_file, METRIC_TRANSM_TOTAL_KB,
                                         endpoint_name, endpoint_conn_type, endpoint_id, digits[1])
                    next_state = State.SEND_INFO
                else:
                    logger.warning("Expecting TX 'Total' line, but got: %s", line[:-1])

            elif current_state == State.SEND_INFO:
                logger.info("   Got all data")
                next_state = State.IDLE

            else:
                next_state = State.IDLE

            current_state = next_state
            last_readline_time = time.time()


if __name__ == "__main__":
    main()
