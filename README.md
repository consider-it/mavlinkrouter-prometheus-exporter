# MAVLink Router Prometheus Exporter

Conversion script exporting the [MAVLink Router](https://github.com/mavlink-router/mavlink-router) routing statistics output to Prometheus metrics.

MAVLink router prints some statistics of each endpoint to stdout when started with the `-r` option.
When fed with this output via stdin, this application can parse the data and write them to a file.
This file can then be consumed by prometheus via it's testfile collector.


## Installation

Only python3 is needed since no additional pip modules are used.
Either just clone this repository to somewhere you like or copy the pythons script to a location contained in your `PATH` afterwards for easier usage.

The MAVLink router version needs to be newer than 2022-06-15 as [PR#363](https://github.com/mavlink-router/mavlink-router/pull/363) is needed to work properly.


## Usage

The script will write it's output to `/var/local/` by default using `mavrouter_export.prom` for the actual data and `mavrouter_export.cache` for temporary storage of the output until a full dataset was collected.

Start the chain manually with:
```shell
sudo mavlink-routerd -r | sudo python3 data_parser.py
```

Or modify MAVLink Router's systemd unit like this:
```
ExecStart=/bin/sh -c '/usr/bin/mavlink-routerd -r | python3 /usr/local/bin/data_parser.py'
```

These metrics will be written for each endpoint:

- `mavlinkrouter_receive_crcerror_count`
- `mavlinkrouter_receive_crcerror_percent`
- `mavlinkrouter_receive_crcerror_kilo_byte`
- `mavlinkrouter_receive_seqlost_count`
- `mavlinkrouter_receive_seqlost_percent`
- `mavlinkrouter_receive_handled_count`
- `mavlinkrouter_receive_handled_kilo_byte`
- `mavlinkrouter_receive_total_count`
- `mavlinkrouter_transmit_total_count`
- `mavlinkrouter_transmit_total_kilo_byte`

They are tagged with:

- `conn_type`: UDP, TCP or UART as printed by mavlink-router
- `endpoint_id`: Endpoint number as printed by mavlink-router
- `endpoint_name`: Endpoint name as printed by mavlink-router

Clients connecting to the TCP server port will all have the same endpoint name as mavlink-router does not print a dynamic value (at the time of writing this).
Endpoints created via command line options will also have no (unique) name, so using the config file of MAVLink Router is recommended.

Endpoint IDs might also not be unique during the whole runtime of mavlink-router as they might be re-assigned when a client disconnected.
But this script is only exporting the data available in the statistics output.
