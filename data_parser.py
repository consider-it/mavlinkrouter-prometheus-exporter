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
PROM_FILE_PATH = "/var/local/exporter.prom"
CACHE_FILE_PATH = "/var/local/cache.prom"


# =============== State machine states ==========================
class state(Enum):
    IDLE = 0
    EVAL_RECEIVED = 1
    EVAL_RECEIVED_CRC_ERR = 2
    EVAL_RECEIVED_SEQ_LOST = 3
    EVAL_RECEIVED_HANDLED = 4
    EVAL_RECEIVED_TOTAL = 5
    EVAL_TRANSMITTED = 6
    EVAL_TRANSMITTED_TOTAL = 7
    SEND_INFO = 8


# initialize states
currentState = state.IDLE
nextState = state.IDLE
# timestamp (in seconds.. as float). initially set to float max,
# because lastUpdateWasOverASecondAgo() shouldnt be triggered in the first iterataiton
lastTimeStamp = sys.float_info.max
deviceID = "DEFAULT"
deviceName = "DEFAULT"
deviceConnType = "DEFAULT"
# this cache file is a textfile where the single lines (data) are written successively.
cacheFile = open(CACHE_FILE_PATH, 'w+')


# Writes a line to the cache textfile
def writeDataToCacheTextfile(dataAsString):
    cacheFile.write(dataAsString)


# The prom file needs to be complete in order to ensure integrity.
# thats why single lines where written to the cache file successively and
# only once the data is complete, the content is written to the prom file as a whole
def updatePROMTextFile():
    global cacheFile
    cacheFile.close()  # close it for safety
    cacheFile = open(CACHE_FILE_PATH, 'r')  # reopen to (only) read
    promFile = open(PROM_FILE_PATH, 'w+')  # open prom file
    for line in cacheFile.readlines():     # transfer all data from cache to prom file
        promFile.write(line)
    promFile.close()                       # save/close prom file
    cacheFile.close()                      # close cache file
    open(CACHE_FILE_PATH, 'w').close()      # clear cache file
    # reopens file, because its needed to be written again
    cacheFile = open(CACHE_FILE_PATH, 'w+')


# Checks, if the last data / update was over 0.9 sec ago
def lastUpdateWasOverASecondAgo(timeStamp):
    if timeStamp < (time.time()-0.9):
        return True
    else:
        return False


# Reads device id out of the string
def readDevID(inputStr):
    start = inputStr.find("[") + 1
    end = inputStr.find("]", start, len(inputStr))
    devID = inputStr[start:end]
    return devID


# Reads device name out of the string
def readDevName(inputStr):
    start = inputStr.find("]") + 1
    end = inputStr.find("{", start, len(inputStr)) - 1
    devName = inputStr[start:end]
    return devName


# Writes a metric to the cache file with the according device name, conn type and so on
def writeMetric(metricStr, value):
    writeDataToCacheTextfile(
        metricStr + "{endpoint_name=\"" + deviceName + "\",conn_type=\"" + deviceConnType + "\",endpoint_id=\"" + deviceID + "\"} " + str(value) + "\n")


if __name__ == "__main__":
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

    # inf. loop
    while True:
        for line in sys.stdin:  # goes through the input line by line in an infinite loop

            sys.stdout.write(line)

            if line.find("TCP Endpoint") != -1:
                deviceConnType = "TCP"
                deviceName = readDevName(line)
                deviceID = readDevID(line)
                if(lastUpdateWasOverASecondAgo(lastTimeStamp)):
                    updatePROMTextFile()
                nextState = state.EVAL_RECEIVED

            elif line.find("UDP Endpoint") != -1:
                deviceConnType = "UDP"
                deviceName = readDevName(line)
                deviceID = readDevID(line)
                if(lastUpdateWasOverASecondAgo(lastTimeStamp)):
                    updatePROMTextFile()
                nextState = state.EVAL_RECEIVED

            elif line.find("UART Endpoint") != -1:
                deviceConnType = "UART"
                deviceName = readDevName(line)
                deviceID = readDevID(line)
                if(lastUpdateWasOverASecondAgo(lastTimeStamp)):
                    updatePROMTextFile()
                nextState = state.EVAL_RECEIVED

        # ========= pseudo Switch case for state machine ==========
            if(currentState == state.IDLE):
                pass
            elif(currentState == state.EVAL_RECEIVED):
                nextState = state.EVAL_RECEIVED_CRC_ERR

            elif(currentState == state.EVAL_RECEIVED_CRC_ERR):
                if(line.find("CRC error") != -1):
                    # regex to find the numbers within the line
                    digits = re.findall(r"\d+", line)
                    writeMetric(METRIC_REC_CRCERR_CNT, digits[0])
                    writeMetric(METRIC_REC_CRCERR_PCT, digits[1])
                    writeMetric(METRIC_REC_CRCERR_KB, digits[2])
                    nextState = state.EVAL_RECEIVED_SEQ_LOST
                else:
                    pass

            elif(currentState == state.EVAL_RECEIVED_SEQ_LOST):
                if(line.find("Sequence lost") != -1):
                    digits = re.findall(r"\d+", line)
                    writeMetric(METRIC_REC_SEQLOST_CNT, digits[0])
                    writeMetric(METRIC_REC_SEQLOST_PCT, digits[1])
                    nextState = state.EVAL_RECEIVED_HANDLED
                else:
                    pass

            elif(currentState == state.EVAL_RECEIVED_HANDLED):
                if(line.find("Handled") != -1):
                    digits = re.findall(r"\d+", line)
                    writeMetric(METRIC_REC_HANDLED_CNT, digits[0])
                    writeMetric(METRIC_REC_HANDLED_KB, digits[1])
                    nextState = state.EVAL_RECEIVED_TOTAL
                else:
                    pass

            elif(currentState == state.EVAL_RECEIVED_TOTAL):
                if(line.find("Total") != -1):
                    digits = re.findall(r"\d+", line)
                    writeMetric(METRIC_REC_TOTAL_CNT, digits[0])
                    nextState = state.EVAL_TRANSMITTED
                else:
                    pass

            elif(currentState == state.EVAL_TRANSMITTED):
                nextState = state.EVAL_TRANSMITTED_TOTAL

            elif(currentState == state.EVAL_TRANSMITTED_TOTAL):
                if(line.find("Total") != -1):
                    digits = re.findall(r"\d+", line)
                    writeMetric(METRIC_TRANSM_TOTAL_CNT, digits[0])
                    writeMetric(METRIC_TRANSM_TOTAL_KB, digits[1])
                    nextState = state.SEND_INFO
                else:
                    pass

            elif(currentState == state.SEND_INFO):
                nextState = state.IDLE

            else:
                nextState = state.IDLE

            currentState = nextState        # update next state for the state machine
            lastTimeStamp = time.time()     # update timestamp
