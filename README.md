# MAVLink-prometheus_parser
                    
## Explanation
A Python script, wich parses the stdout of the mavlink_router to a textfile.
This is usefull, once the prometheus-agent forwards the statistics (from a prom textfile) to grafana

The statistics of the mavlink router will be output, once the "-r" argument is passed.
The resulting output can be piped into this python script (see section "Usage")
This script then evaluates each line of the piped input accordingly.
A statemachine is used to go through line for line and write relevant data into a chache textfile
Once a complete set of informations was collected, the content of the cache textfile is copied into the actual prom textfile

                    
## Usage
<code>"mavlinkrouter -r | python3 data_parser.py"</code>
                       
## Output (textfile) location:
<code>/var/local/exporter.prom</code>
                        