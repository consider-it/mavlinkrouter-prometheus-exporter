"""
 * @file      data_parser.py
 * @brief     Mavlink-Router Data parser, 
 *    This Program is writing Metrics for Promepheus / Grafana in a textfile
 *    The Grafana-agent installed on the system redirects the periodic Poll to the Textfile generated by this program
 * @author    Oemer Yilmaz <yilmaz@consider-it.de>
 * @copyright (c) Consider-IT, 2022
 """

import sys
import time
import re
from enum import Enum

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

PROM_FILE_PATH = "/var/local/node_exporter/exporter.prom"
CACHE_FILE_PATH = "/var/local/node_exporter/cache.prom"


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
# timestamp (in seconds.. as float). initially set to float max, because i dont want it to be triggered in the first iterataiton
lastTimeStamp = sys.float_info.max
deviceID = "DEFAULT"
deviceName = "DEFAULT"
deviceConnType = "DEFAULT"
cache_file = open(CACHE_FILE_PATH, 'w+')


def writeDataToCacheTextfile(dataAsString):
    cache_file.write(dataAsString)


def updatePROMTextFile():
    global cache_file
    cache_file.close()  # close it for safety
    cache_file = open(CACHE_FILE_PATH, 'r')  # reopen to (only) read
    prom_file = open(PROM_FILE_PATH, 'w+')  # open prom file
    for line in cache_file.readlines():     # transfer all data from cache to prom file
        prom_file.write(line)
    prom_file.close()                       # save/close prom file
    cache_file.close()                      # close cache file
    open(CACHE_FILE_PATH, 'w').close()      # clear cache file
    # reopens file, because its needed to be written again
    cache_file = open(CACHE_FILE_PATH, 'w+')


def lastUpdateWasOverASecondAgo(timeStamp):
    if(timeStamp < (time.time()-0.9)):
        return True
    else:
        return False


def readDevID(inputStr):
    start = inputStr.find("[") + 1
    end = inputStr.find("]", start, len(inputStr))
    devID = inputStr[start:end]
    return devID


def readDevName(inputStr):
    start = inputStr.find("]") + 1
    end = inputStr.find("{", start, len(inputStr)) - 1
    devName = inputStr[start:end]
    return devName


def writeMetric(metricStr, value):
    writeDataToCacheTextfile(
        metricStr + "{device_name=\"" + deviceName + "\",conn_type=\"" + deviceConnType + "\",device_id=\"" + deviceID + "\"} " + str(value) + "\n")


# inf. blocking loop
while True:
    for line in sys.stdin:

        sys.stdout.write(line)  # TODO: What does this do ?

        if(line.find("TCP Endpoint") != -1):
            deviceConnType = "TCP"
            deviceName = readDevName(line)
            deviceID = readDevID(line)
            if(lastUpdateWasOverASecondAgo(lastTimeStamp)):
                updatePROMTextFile()
            nextState = state.EVAL_RECEIVED

        elif(line.find("UDP Endpoint") != -1):
            deviceConnType = "UDP"
            deviceName = readDevName(line)
            deviceID = readDevID(line)
            if(lastUpdateWasOverASecondAgo(lastTimeStamp)):
                updatePROMTextFile()
            nextState = state.EVAL_RECEIVED

        elif(line.find("UART Endpoint") != -1):
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

        currentState = nextState
        lastTimeStamp = time.time()
