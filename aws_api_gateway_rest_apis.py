# -*- coding: utf-8 -*-
"""
Created on Sat Jan 18 14:22:25 2020

@author: mchwitczak@gmail.com
"""

import pandas as pd
import json
import argparse
import boto3
import datetime as dt
import configparser
import os
import sys

REGION = 'us-east-2'
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'output')
CONFIG_FILE = os.path.join(os.path.dirname(__file__), '.aws', 'aws.conf')

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)
        

def get_client(aws_id: str, aws_key: str, region_name=REGION, service_name='apigateway') -> boto3.client:
    """
    Simple wrapper to get client from boto3
    """
    
    return boto3.client(service_name, aws_access_key_id=aws_id, aws_secret_access_key=aws_key, region_name=region_name)


def get_region(conf: dict) -> dict:
    """
    Check region (with validation) if provided, otherwise use default
    """
    
    if conf['region']:
        df = pd.DataFrame(get_available_regions(conf))
        available_regions = list(df['RegionName'].unique())
        available_regions_str = "\n".join(list(df["RegionName"].unique()))
        if conf['region'] not in available_regions:
            raise Exception(f'Invalid region name. Regions available:\n{available_regions_str}')
     
    else:
        conf['region'] = REGION
    
    return conf
    

def get_config() -> dict:
    """
    Parse commandline arguments and return config dictionary
    """
    
    parser = argparse.ArgumentParser(description='Script to gather audit AWS REST API data. If no argument is provided, defaults will be used.')
    parser.add_argument('-p', '--profile', metavar='P', type=str, nargs='?', help='AWS API Profile from ~/.aws/aws.conf file')
    parser.add_argument('-r', '--region', metavar='us-east-2', type=str, nargs='?', help='AWS API Region')
    parser.add_argument('-m', '--methods', metavar='get', type=str, nargs='*', help='AWS API HTTP Methods', choices=['get', 'put', 'delete', 'post', 'options'])
    parser.add_argument('-o', '--output', metavar='json, csv, json-pretty', type=str, nargs='?', help='Script output', choices=['json', 'csv', 'json-pretty'])

    args = parser.parse_args()
    
    conf = {
        'profile': args.profile,
        'region': args.region,
        'methods': args.methods,
        'output': args.output
        }
  
    conf = get_profiles(conf)
    
    conf['output'] = conf['output'] if conf['output'] else 'csv'
    conf = get_region(conf)
    
    return conf


def get_available_regions(conf: dict):
    """
    Get all available regions
    """

    ec2 = get_client(aws_id=conf['id'], aws_key=conf['key'], service_name='ec2')
    
    regions = ec2.describe_regions()
    
    return regions['Regions']


def check_response_code(payload: dict) -> None:
    """
    Check response code from calling boto3 client method
    """
    status_code = payload['ResponseMetadata']['HTTPStatusCode']
    if status_code != 200:
        raise Exception(f'{status_code} - Could not obtain rest APIs list')  


def get_rest_apis(client: boto3.client):
    """
    Get all REST APIs for json output
    """
    response = client.get_rest_apis()
    check_response_code(response)
    rest_apis = response['items'] 
    for rest_api in rest_apis:
        rest_api['createdDate'] = rest_api['createdDate'].strftime('%Y-%m-%d %H:%M:%S')
    
    return rest_apis


def get_api_resources(client: boto3.client, rest_apis: list, config):
    """
    Get API Resources for json output
    """
    api_resources = {}
    # call client for resource of given REST API Id
    for rest_api in rest_apis:
        response = client.get_resources(restApiId=rest_api['id'])
        check_response_code(response)
        resource = response['items']
        
        # filter methods 
        if config['methods']:
            desired_methods = [x.upper() for x in config['methods']]
            
            filtered_resource = []
            for res in resource:
                for method in desired_methods:
                    if method in res['resourceMethods'].keys():
                        filtered_resource.append(res)
                        break
                    
            resource = filtered_resource
                 
        api_resources.setdefault(rest_api['id'], resource)
        
    return api_resources

        
def get_rest_apis_dataframe(client: boto3.client) -> pd.DataFrame:
    """
    Get all REST APIs for csv output
    """
    rest_apis = get_rest_apis(client)

    df_rest_apis = []
    for rest_api in rest_apis:
        
        # extract inner dictionary
        endpoint_configuration = rest_api.pop('endpointConfiguration')
        # tags = rest_api.pop('tags')
        
        # join arrays into string
        for key in ['binaryMediaTypes', 'warnings']:
            try:
                rest_api[key] = ', '.join(rest_api[key])
            except KeyError:
                continue
            
        # create DataFrame from dictionary
        df = pd.DataFrame(rest_api, index=[0])
        
        # create columns from extracted inner dictionary
        df['EndpointConfigurationTypes'] = ', '.join(endpoint_configuration['types'])
        try:
            df['EndpointConfigurationVpcEndpointIds'] = ', '.join(endpoint_configuration['vpcEndpointIds'])
        except KeyError:
            pass
        
        df_rest_apis.append(df)
    
    if len(df_rest_apis) != 0:
        df_rest_apis = pd.concat(df_rest_apis, sort=False, ignore_index=True)
    else:
        print(f'No REST APIs found for {client.meta.region_name} region')
        sys.exit(0)
        
    return df_rest_apis
    

def get_api_resources_dataframe(client: boto3.client, rest_apis: list, config: dict) -> pd.DataFrame:  
    """
    Get API Resources for csv output
    """
    df_resources = []
    for rest_api in rest_apis:
        response = client.get_resources(restApiId=rest_api)
        check_response_code(response)
        resource = response['items'] 
        # join arrays into string
        for res in resource:
            try:
                res['resourceMethods'] = ', '.join(res['resourceMethods'].keys())
            except KeyError:
                pass
            
        # create DataFrame from dictionary    
        df = pd.DataFrame(resource)
        
        # attach REST API Id
        df['RestApiId'] = rest_api
        
        df_resources.append(df)
    
    df_resources = pd.concat(df_resources, sort=True, ignore_index=True)
    
    # rename columns
    df_resources.rename(columns={
        'id': 'ResourceId',
        'parentId': 'ParentId',
        'path': 'Path',
        'resourceMethods': 'ResourceMethods',
        }, inplace=True)
    try:
        df_resources.drop(columns='pathPart', inplace=True)
    except KeyError:
        pass
    
    # filter methods
    if config['methods']:
        desired_methods = [x.upper() for x in config['methods']]
        
        indexes = []
        for idx, row in df_resources.iterrows():
            methods = row['ResourceMethods'].split(', ')
            for method in desired_methods:
                if method in methods:
                    indexes.append(idx)
                    break
    
        df_resources = df_resources.reindex(indexes)
    
    return df_resources
    

def get_data(config: dict):
    """
    Get data (main script logic)
    """
    
    print(f'''Getting REST API data for:
          - profile: {'default' if not config["profile"] else config["profile"]}
          - methods: {'ALL' if not config["methods"] else config["methods"]}
          - region: {config["region"]}
          - output: {config["output"]}''')

    apigw = get_client(service_name='apigateway', aws_id=config['id'], aws_key=config['key'], region_name=config['region'])
    
    file_name = f'{dt.datetime.now().strftime("%Y%m%d_%H%M%S")}_apigateway_report_{config["region"]}'
    if config['methods']:
        file_name += f'_{"_".join(config["methods"])}'
    if config['profile']:
        file_name += f'_{config["profile"]}'
        
    if config['output'] == 'csv':
        df_rest_apis = get_rest_apis_dataframe(apigw)
        df_resources = get_api_resources_dataframe(apigw, list(df_rest_apis['id']), config)
        df = df_rest_apis.merge(df_resources, how='outer', left_on='id', right_on='RestApiId')
        file_name += '.csv'
        df.to_csv(os.path.join(OUTPUT_DIR, file_name), sep='|', index=False)

    if 'json' in config['output']:
        rest_apis = get_rest_apis(apigw)
        api_resources = get_api_resources(apigw, rest_apis, config)
        
        for rest_api in rest_apis:
            rest_api['Resources'] = api_resources[rest_api['id']]
            
        output = {'RestApis': rest_apis}
        file_name += '.json'
        with open(os.path.join(OUTPUT_DIR, file_name), 'w') as f:
            if config['output'] == 'json-pretty':
                json.dump(output, f, indent=4)
            else:
                json.dump(output, f)
    print(f'Output file saved: {os.path.join(OUTPUT_DIR, file_name)}')


def get_profiles(config: dict, conf_file=CONFIG_FILE) -> dict:
    profiles = configparser.ConfigParser()
    
    profiles.read(conf_file)
    
    if config['profile']:
        try:
            profile = config['profile'].upper()
            creds = profiles[profile]
        except KeyError:
            print(f'Invalid aws profile: {profile}. Please check configuration file')
            sys.exit(1)
    else:
        creds = profiles['DEFAULT']

    config['id'] = creds['aws_access_key_id']
    config['key'] = creds['aws_secret_access_key']
    
    return config


if __name__ == '__main__':
    config = get_config()  
    get_data(config=config)
