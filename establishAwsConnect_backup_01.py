import boto3
from botocore.exceptions import ClientError, NoCredentialsError
#Create Function to establish connection to AWS
def establish_aws_connection(clientId,clientSecret,region):
    try:
        # Create a session using the provided credentials
        session = boto3.Session(
            aws_access_key_id=clientId,
            aws_secret_access_key=clientSecret,
            region_name=region
        )
        # Create an cloudwatch client using the session
        cloudwatch_client = session.client('cloudwatch')
        print("Connection to AWS established successfully.")
        return cloudwatch_client
    except Exception as e:
        print(f"An error occurred while establishing connection to AWS: {e}")
        return None

# Finds all metrics in the container insights namespace and prints them out
def findEksMetrics(cloudwatch_client,clusterName):
    try: 
        paginator = cloudwatch_client.get_paginator('list_metrics')
        metrics_found=[]
        for response in paginator.paginate(Namespace='ContainerInsights',Dimensions=[{'Name': 'ClusterName', 'Value': clusterName}]):
            for metric in response['Metrics']:
                metrics_found.append({
                    'MetricName': metric['MetricName'],
                    'Dimensions': metric['Dimensions']        
                })
        return metrics_found
    except Exception as e:
        print(f"An error occurred while finding EKS metrics: {e}")
        return  []

if __name__ == "__main__":
    # Take inputs from user
    region = input("Enter AWS Region (e.g., ap-south-1): ").strip()
    access_key = input("Enter AWS Access Key: ").strip()
    secret_key = input("Enter AWS Secret Key: ").strip()
    cluster_name = input("Enter EKS Cluster Name: ").strip()
    cloudwatch_client = establish_aws_connection(access_key, secret_key, region)
    if cloudwatch_client:
        metrics = findEksMetrics(cloudwatch_client, cluster_name)
        if metrics:
            print(f"Metrics found for cluster {cluster_name}:")
            for metric in metrics:
                print(metric)
        else:
            print(f"No metrics found for cluster {cluster_name}.")