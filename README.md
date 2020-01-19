#infor_coding

usage: aws_api_gateways.py [-h] [-u [USERNAME]] [-p [PASSWORD]] [-r [us-east-2]] [-m [get [get ...]]] [-o [json, csv, json-pretty]]

Script to gather audit AWS REST API data. If no argument is provided, defaults will be used.

optional arguments:
  -h, --help            show this help message and exit
  -u [USERNAME], --username [USERNAME]
                        AWS API id
  -p [PASSWORD], --password [PASSWORD]
                        AWS API key
  -r [us-east-2], --region [us-east-2]
                        AWS API Region
  -m [get [get ...]], --methods [get [get ...]]
                        AWS API HTTP Methods
  -o [json, csv, json-pretty], --output [json, csv, json-pretty]
                        Script output
