## Description
Script to gather audit AWS REST API data. If no argument is provided, defaults will be used.

## Usage

```
aws_api_gateway_rest_apis.py [-h] [-p [P]] [-r [us-east-2]] [-m [get [get ...]]] [-o [json, csv, json-pretty]]

Script to gather audit AWS REST API data. If no argument is provided, defaults will be used.

optional arguments:
  -h, --help            show this help message and exit
  -p [P], --profile [P]
                        AWS API Profile from ~/.aws/aws.conf file
  -r [us-east-2], --region [us-east-2]
                        AWS API Region
  -m [get [get ...]], --methods [get [get ...]]
                        AWS API HTTP Methods
  -o [json, csv, json-pretty], --output [json, csv, json-pretty]
                        Script output
```
