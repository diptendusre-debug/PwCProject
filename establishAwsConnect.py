import boto3
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError
from datetime import datetime, timedelta, timezone
import matplotlib.pyplot as plt

# Create Function to establish connection to AWS
def establish_aws_connection(clientId, clientSecret, region):
    try:
        session = boto3.Session(
            aws_access_key_id=clientId,
            aws_secret_access_key=clientSecret,
            region_name=region
        )
        cloudwatch_client = session.client('cloudwatch')
        print("Connection to AWS established successfully.")
        return cloudwatch_client
    except Exception as e:
        print(f"An error occurred while establishing connection to AWS: {e}")
        return None

# Finds all metrics in the container insights namespace and returns them
def findEksMetrics(cloudwatch_client, clusterName):
    try:
        paginator = cloudwatch_client.get_paginator('list_metrics')
        metrics_found = []
        for response in paginator.paginate(
            Namespace='ContainerInsights',
            Dimensions=[{'Name': 'ClusterName', 'Value': clusterName}]
        ):
            for metric in response['Metrics']:
                metrics_found.append({
                    'MetricName': metric['MetricName'],
                    Dimensions: metric['Dimensions']        
                })
        return metrics_found
    except Exception as e:
        print(f"An error occurred while finding EKS metrics: {e}")
        return []

# Fetch CloudWatch time series for one metric
def fetch_metric_time_series(
    cloudwatch_client,
    namespace,
    metric_name,
    dimensions,
    start_time=None,
    end_time=None,
    period=60,
    statistic='Average'
):
    try:
        if end_time is None:
            end_time = datetime.now(timezone.utc)
        if start_time is None:
            start_time = end_time - timedelta(minutes=30)

        response = cloudwatch_client.get_metric_statistics(
            Namespace=namespace,
            MetricName=metric_name,
            Dimensions=dimensions,
            StartTime=start_time,
            EndTime=end_time,
            Period=period,
            Statistics=[statistic]
        )
        return sorted(response.get('Datapoints', []), key=lambda item: item['Timestamp'])
    except Exception as e:
        print(f"An error occurred while fetching metric data: {e}")
        return []

# Plot metric time series and save to PNG
def plot_metric_time_series(datapoints, metric_name, statistic, cluster_name):
    if not datapoints:
        print("No datapoints available for plotting.")
        return None

    timestamps = [point['Timestamp'] for point in datapoints]
    values = [point.get(statistic) for point in datapoints]

    plt.figure(figsize=(10, 5))
    plt.plot(timestamps, values, marker='o', linestyle='-')
    plt.title(f"{metric_name} ({statistic}) for {cluster_name}")
    plt.xlabel('Time (UTC)')
    plt.ylabel(statistic)
    plt.grid(True)
    plt.tight_layout()

    file_name = f"{metric_name.replace(' ', '_')}_{statistic}.png"
    plt.savefig(file_name)
    plt.close()

    print(f"Saved plot to {file_name}")
    return file_name

# Print a summary of available metrics for selection
def print_metric_summary(metrics):
    unique_names = []
    for metric in metrics:
        name = metric['MetricName']
        if name not in unique_names:
            unique_names.append(name)

    print("\nAvailable metrics:")
    for index, name in enumerate(unique_names[:20], start=1):
        print(f"  {index}. {name}")
    if len(unique_names) > 20:
        print(f"  ...and {len(unique_names) - 20} more metrics")
    return unique_names

# Allow the user to choose a metric to visualize
def choose_metric(metrics):
    unique_names = print_metric_summary(metrics)
    choice = input("Enter metric name or number to visualize (press Enter for first metric): ").strip()

    if not choice and unique_names:
        return next((m for m in metrics if m['MetricName'] == unique_names[0]), metrics[0])

    if choice.isdigit():
        index = int(choice) - 1
        if 0 <= index < len(unique_names):
            selected_name = unique_names[index]
            return next((m for m in metrics if m['MetricName'] == selected_name), None)

    return next((m for m in metrics if m['MetricName'].lower() == choice.lower()), None)

if __name__ == "__main__":
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