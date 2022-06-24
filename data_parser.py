#!/usr/bin/env python3
"""
MAVLink Router Prometheus Exporter

Conversion of MAVLink Router routing statistics output to Prometheus metrics

Author:   Oemer Yilmaz <yilmaz@consider-it.de>
Copyright: (c) consider it GmbH, 2022
"""

from enum import Enum
import re
import time
import sys
import argparse
import logging


# ============== Metric definitions for grafana ==================
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


# ================== File paths ======================
FOLDER_PATH = "/var/local/"

PROM_FILE_PATH = FOLDER_PATH + "mavrouter_export.prom"
CACHE_FILE_PATH = FOLDER_PATH + "mavrouter_export.cache"


# =============== State machine states ==========================
class State(Enum):
    """
    This enum declares the different states of the state machine used
    """
    IDLE = 0
    EVAL_RECEIVED = 1
    EVAL_RECEIVED_CRC_ERR = 2
    EVAL_RECEIVED_SEQ_LOST = 3
    EVAL_RECEIVED_HANDLED = 4
    EVAL_RECEIVED_TOTAL = 5
    EVAL_TRANSMITTED = 6
    EVAL_TRANSMITTED_TOTAL = 7
    SEND_INFO = 8


def write_data_to_textfile(file, data_as_string):
    """
    Writes a line to the cache textfile
    """
    file.write(data_as_string)


def update_prom_textfile():
    """
    The prom file needs to be complete in order to ensure integrity.
    thats why single lines where written to the cache file successively and
    only once the data is complete, the content is written to the prom file as a whole.
    This happens here, in this function
    """
    cache_file_input = open(CACHE_FILE_PATH, 'r', encoding="utf8")  # reopen to (only) read
    prom_file_output = open(PROM_FILE_PATH, 'w+', encoding="utf8")  # open prom file
    for single_line in cache_file_input.readlines():     # transfer all data from cache to prom file
        prom_file_output.write(single_line)
    prom_file_output.close()                       # save/close prom file
    cache_file_input.close()                      # close cache file
    open(CACHE_FILE_PATH, 'w', encoding="utf8").close()      # clear cache file


def last_update_over_a_second_ago(timestamp):
    """
    Checks, if the last data / update was over 0.9 sec ago
    """
    if timestamp < (time.time()-0.9):
        return True
    return False


def read_endppoint_id(input_string):
    """
    Reads device id out of the string
    """
    start = input_string.find("[") + 1
    end = input_string.find("]", start, len(input_string))
    dev_id = input_string[start:end]
    return dev_id


def read_endppoint_name(input_string):
    """
    Reads device name out of the string
    """
    start = input_string.find("]") + 1
    end = input_string.find("{", start, len(input_string)) - 1
    dev_name = input_string[start:end]
    return dev_name


def write_metric_to_file(inp_file, inp_metric_str, inp_endpoint_name, inp_endpoint_conntype, inp_endpoint_id, inp_value):
    """
    Writes a metric to the cache file with the according device name, conn type and so on
    """
    complete_string = inp_metric_str + "{endpoint_name=\"" + inp_endpoint_name + "\",conn_type=\"" + \
        inp_endpoint_conntype + "\",endpoint_id=\"" + \
        inp_endpoint_id + "\"} " + str(inp_value) + "\n"
    write_data_to_textfile(inp_file, complete_string)


if __name__ == "__main__":
    """
    Main function
    """
    log_format = '%(asctime)s %(levelname)s:%(name)s: %(message)s'
    log_datefmt = '%Y-%m-%dT%H:%M:%S%z'
    logging.basicConfig(format=log_format, datefmt=log_datefmt, level=logging.INFO)
    logger = logging.getLogger()

    parser = argparse.ArgumentParser(description='Mavrouter Prometheus Expoerter')
    parser.add_argument("-v", "--verbosity", action="count",
                        help="increase output and logging verbosity")
    args = parser.parse_args()

    if args.verbosity == 2:
        logger.setLevel(logging.DEBUG)
    elif args.verbosity == 1:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.WARNING)

    endpoint_ID = "DEFAULT"
    endpoint_name = "DEFAULT"
    endpoint_conn_type = "DEFAULT"
    # initialize states
    current_state = State.IDLE
    next_state = State.IDLE
    # timestamp (in seconds.. as float). initially set to float max,
    # because last_update_over_a_second_ago() shouldnt be triggered in the first iterataiton
    last_time_stamp = sys.float_info.max
    # this cache file is a textfile where the single lines (data) are written successively.
    cache_file = open(CACHE_FILE_PATH, 'w+', encoding="utf8")

    # inf. loop
    while True:
        for line in sys.stdin:  # goes through the input line by line in an infinite loop

            sys.stdout.write(line)

            if line.find("TCP Endpoint") != -1:
                endpoint_conn_type = "TCP"
                endpoint_name = read_endppoint_name(line)
                endpoint_ID = read_endppoint_id(line)
                if last_update_over_a_second_ago(last_time_stamp):
                    cache_file.close()
                    update_prom_textfile()
                next_state = State.EVAL_RECEIVED

            elif line.find("UDP Endpoint") != -1:
                endpoint_conn_type = "UDP"
                endpoint_name = read_endppoint_name(line)
                endpoint_ID = read_endppoint_id(line)
                if last_update_over_a_second_ago(last_time_stamp):
                    cache_file.close()
                    update_prom_textfile()
                next_state = State.EVAL_RECEIVED

            elif line.find("UART Endpoint") != -1:
                endpoint_conn_type = "UART"
                endpoint_name = read_endppoint_name(line)
                endpoint_ID = read_endppoint_id(line)
                if last_update_over_a_second_ago(last_time_stamp):
                    cache_file.close()
                    update_prom_textfile()
                next_state = State.EVAL_RECEIVED

        # ========= pseudo Switch case for State machine ==========
            if current_state == State.IDLE:
                pass
            elif current_state == State.EVAL_RECEIVED:
                cache_file = open(CACHE_FILE_PATH, 'w+', encoding="utf8")
                next_state = State.EVAL_RECEIVED_CRC_ERR

            elif current_state == State.EVAL_RECEIVED_CRC_ERR:
                if line.find("CRC error") != -1:
                    # regex to find the numbers within the line
                    digits = re.findall(r"\d+", line)
                    write_metric_to_file(cache_file, METRIC_REC_CRCERR_CNT,
                                         endpoint_name, endpoint_conn_type, endpoint_ID, digits[0])
                    write_metric_to_file(cache_file, METRIC_REC_CRCERR_PCT,
                                         endpoint_name, endpoint_conn_type, endpoint_ID, digits[1])
                    write_metric_to_file(cache_file, METRIC_REC_CRCERR_KB,
                                         endpoint_name, endpoint_conn_type, endpoint_ID, digits[2])
                    next_state = State.EVAL_RECEIVED_SEQ_LOST
                else:
                    pass

            elif current_state == State.EVAL_RECEIVED_SEQ_LOST:
                if line.find("Sequence lost") != -1:
                    digits = re.findall(r"\d+", line)
                    write_metric_to_file(cache_file, METRIC_REC_SEQLOST_CNT,
                                         endpoint_name, endpoint_conn_type, endpoint_ID, digits[0])
                    write_metric_to_file(cache_file, METRIC_REC_SEQLOST_PCT,
                                         endpoint_name, endpoint_conn_type, endpoint_ID, digits[1])
                    next_state = State.EVAL_RECEIVED_HANDLED
                else:
                    pass

            elif current_state == State.EVAL_RECEIVED_HANDLED:
                if line.find("Handled") != -1:
                    digits = re.findall(r"\d+", line)
                    write_metric_to_file(cache_file, METRIC_REC_HANDLED_CNT,
                                         endpoint_name, endpoint_conn_type, endpoint_ID, digits[0])
                    write_metric_to_file(cache_file, METRIC_REC_HANDLED_KB,
                                         endpoint_name, endpoint_conn_type, endpoint_ID, digits[1])
                    next_state = State.EVAL_RECEIVED_TOTAL
                else:
                    pass

            elif current_state == State.EVAL_RECEIVED_TOTAL:
                if line.find("Total") != -1:
                    digits = re.findall(r"\d+", line)
                    write_metric_to_file(cache_file, METRIC_REC_TOTAL_CNT,
                                         endpoint_name, endpoint_conn_type, endpoint_ID, digits[0])
                    next_state = State.EVAL_TRANSMITTED
                else:
                    pass

            elif current_state == State.EVAL_TRANSMITTED:
                next_state = State.EVAL_TRANSMITTED_TOTAL

            elif current_state == State.EVAL_TRANSMITTED_TOTAL:
                if line.find("Total") != -1:
                    digits = re.findall(r"\d+", line)
                    write_metric_to_file(cache_file, METRIC_TRANSM_TOTAL_CNT,
                                         endpoint_name, endpoint_conn_type, endpoint_ID, digits[0])
                    write_metric_to_file(cache_file, METRIC_TRANSM_TOTAL_KB,
                                         endpoint_name, endpoint_conn_type, endpoint_ID, digits[1])
                    next_state = State.SEND_INFO
                else:
                    pass

            elif current_state == State.SEND_INFO:
                next_state = State.IDLE

            else:
                next_state = State.IDLE

            current_state = next_state        # update next State for the State machine
            last_time_stamp = time.time()     # update timestamp
