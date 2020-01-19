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
import os
import sys

REGION = 'us-east-2'
# hardcoded credentials (I'm bad...)
ID = 'AKIAIJBFJOORACQILVDQ'
KEY = '9hEEtcBxV3CifrOCfRUEqV5z4yKA2pzEIaA6CaeB'
AUTH = {'id': ID, 'key': KEY}
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'output')
        

def check_auth(user: str, password: str) -> tuple:
    """
    Return user and password if provided, otherwise use default

    """
    if not user or not password:
        auth = {'id': ID,
                'key': KEY}
    else: 
        auth = {'id': user, 
                'key': password}
    
    return auth


def get_client(service_name='apigateway', auth=AUTH, region_name=REGION) -> boto3.client:
    """
    Simple wrapper to get client from boto3
    """
    
    return boto3.client(service_name, aws_access_key_id=auth['id'], aws_secret_access_key=auth['key'], region_name=region_name)


def get_region(region) -> str:
    """
    Check region (with validation) if provided, otherwise use default
    """
    
    if region:
        df = pd.DataFrame(regions())
        available_regions = list(df['RegionName'].unique())
        available_regions_str = "\n".join(list(df["RegionName"].unique()))
        if region not in available_regions:
            raise Exception(f'Invalid region name. Regions available:\n{available_regions_str}')
            
        return region
    else:
        return REGION
    

def get_config() -> dict:
    """
    Parse commandline arguments and return config dictionary
    """
    
    parser = argparse.ArgumentParser(description='Jestem zajebisty')
    parser.add_argument('-u', '--username', metavar='U', type=str, nargs='?', help='AWS API id')
    parser.add_argument('-p', '--password', metavar='P', type=str, nargs='?', help='AWS API key')
    parser.add_argument('-r', '--region', metavar='R', type=str, nargs='?', help='AWS API Region')
    parser.add_argument('-m', '--methods', metavar='M', type=str, nargs='*', help='AWS API HTTP Methods', choices=['get', 'put', 'delete', 'post', 'options'])
    parser.add_argument('-o', '--output', metavar='O', type=str, nargs='?', help='Script output', choices=['json', 'csv', 'json-pretty'])
    

    args = parser.parse_args()
    
    conf = {
        'id': args.username,
        'key': args.password,
        'region': args.region,
        'methods': args.methods,
        'output': args.output
        }
    
    return conf

def regions():
    """
    Get all available regions
    """
    
    client = get_client('ec2')
    
    regions = client.describe_regions()
    
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
    

def get_api_resources_dataframe(client: boto3.client, rest_apis: list, config) -> pd.DataFrame:  
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
        
        indexes = list(set(indexes))
        
        df_resources = df_resources.reindex(indexes)
    
    return df_resources
    

def get_data(auth: dict, config: dict):
    """
    Get data (main script logic)
    """
    apigw = get_client(service_name='apigateway', auth=auth, region_name=config['region'])
    
    file_name = f'{dt.datetime.now().strftime("%Y%m%d_%H%M%S")}_apigateway_report_{config["region"]}_{auth["id"]}'
    if config['methods']:
        file_name += f'_{"_".join(config["methods"])}'
        
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


if __name__ == '__main__':
    CONFIG = get_config()
    AUTH = check_auth(CONFIG.pop('id'), CONFIG.pop('key'))
    CONFIG['output'] = CONFIG['output'] if CONFIG['output'] else 'csv'
    CONFIG['region'] = get_region(CONFIG['region'])
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    get_data(auth=AUTH, config=CONFIG)
    
    
