import boto3
from datetime import datetime, timedelta, timezone
import matplotlib.pyplot as plt

# ---------------- AWS CONNECTION ----------------
def establish_aws_connection(access_key, secret_key, region):
    try:
        session = boto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )
        return session.client('cloudwatch')
    except Exception as e:
        print(f"AWS Connection Error: {e}")
        return None

# ---------------- CLOUDWATCH METRICS ----------------
DEPLOYMENT_DIMENSION_CANDIDATES = [
    'DeploymentName',
    'Deployment',
    'WorkloadName',
    'Workload',
    'KubernetesDeployment'
]

def list_deployment_metrics(cw_client, cluster, namespace, deployment_name):
    paginator = cw_client.get_paginator('list_metrics')
    discovered = []

    for response in paginator.paginate(
        Namespace='ContainerInsights',
        Dimensions=[
            {'Name': 'ClusterName', 'Value': cluster},
            {'Name': 'Namespace', 'Value': namespace}
        ]
    ):
        for metric in response.get('Metrics', []):
            if any(
                dim.get('Name') in DEPLOYMENT_DIMENSION_CANDIDATES and dim.get('Value') == deployment_name
                for dim in metric.get('Dimensions', [])
            ):
                discovered.append(metric)

    if discovered:
        print(f"\nDiscovered deployment metrics for '{deployment_name}':")
        for metric in discovered:
            print(f"  - {metric['MetricName']} | Dimensions: {metric['Dimensions']}")
    else:
        print(f"\nNo deployment metrics discovered for '{deployment_name}' under cluster '{cluster}' and namespace '{namespace}'.")

    return discovered


def choose_discovered_metrics(metrics):
    unique_names = []
    for metric in metrics:
        name = metric.get('MetricName')
        if name and name not in unique_names:
            unique_names.append(name)

    if not unique_names:
        return []

    print("\nAvailable discovered deployment metrics:")
    for index, name in enumerate(unique_names, start=1):
        print(f"  {index}. {name}")

    choice = input(
        "Enter metric number(s) to fetch (comma-separated), or press Enter to fetch all discovered metrics: "
    ).strip()

    if not choice:
        return unique_names

    selected = []
    for part in choice.split(','):
        part = part.strip()
        if not part:
            continue
        if part.isdigit():
            idx = int(part) - 1
            if 0 <= idx < len(unique_names):
                selected.append(unique_names[idx])
        else:
            if part in unique_names:
                selected.append(part)

    return selected


def find_deployment_dimension(cw_client, cluster, namespace, deployment_name, metric_name):
    paginator = cw_client.get_paginator('list_metrics')

    for response in paginator.paginate(
        Namespace='ContainerInsights',
        Dimensions=[
            {'Name': 'ClusterName', 'Value': cluster},
            {'Name': 'Namespace', 'Value': namespace}
        ]
    ):
        for metric in response.get('Metrics', []):
            if metric.get('MetricName') != metric_name:
                continue
            for dim in metric.get('Dimensions', []):
                if dim.get('Name') in DEPLOYMENT_DIMENSION_CANDIDATES and dim.get('Value') == deployment_name:
                    return dim.get('Name')
    return None


def get_deployment_metrics(cw_client, cluster, namespace, deployment_name, metric_name, period=60, minutes=10):
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=minutes)

    for dimension_name in DEPLOYMENT_DIMENSION_CANDIDATES:
        try:
            response = cw_client.get_metric_statistics(
                Namespace='ContainerInsights',
                MetricName=metric_name,
                Dimensions=[
                    {'Name': 'ClusterName', 'Value': cluster},
                    {'Name': 'Namespace', 'Value': namespace},
                    {'Name': dimension_name, 'Value': deployment_name}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=period,
                Statistics=['Average']
            )

            datapoints = sorted(response.get('Datapoints', []), key=lambda x: x['Timestamp'])
            if datapoints:
                print(f"Using dimension '{dimension_name}' for deployment metric '{metric_name}'")
                return datapoints
        except Exception as e:
            print(f"CloudWatch Error ({dimension_name}): {e}")

    return []

# ---------------- PLOT ----------------
def plot_metrics(datapoints, metric_label, deployment):
    if not datapoints:
        print(f"No data found for {metric_label}")
        return

    times = [p['Timestamp'].strftime('%H:%M') for p in datapoints]
    values = [p['Average'] for p in datapoints]

    plt.figure(figsize=(10, 5))
    plt.plot(times, values, marker='o')
    plt.title(f"{deployment} - {metric_label} (Last {len(datapoints)} points)")
    plt.xlabel("Time (UTC)")
    plt.ylabel(metric_label)
    plt.grid(True)

    file_name = f"{deployment}_{metric_label.lower().replace(' ', '_')}.png"
    plt.savefig(file_name)
    print(f"Saved: {file_name}")
    plt.close()

# ---------------- MAIN ----------------
if __name__ == "__main__":
    region = input("AWS Region: ").strip()
    access_key = input("Access Key: ").strip()
    secret_key = input("Secret Key: ").strip()
    cluster = input("Cluster Name: ").strip()
    namespace = input("Namespace: ").strip()
    deployment = input("Deployment Name: ").strip()

    cw = establish_aws_connection(access_key, secret_key, region)
    if not cw:
        exit(1)

    if not deployment:
        print("Deployment Name is required to fetch deployment metrics.")
        exit(1)

    metrics = [
        {'name': 'pod_cpu_utilization', 'label': 'CPU Utilization (%)'},
        {'name': 'pod_memory_utilization', 'label': 'Memory Utilization (%)'}
    ]

    available_metrics = list_deployment_metrics(cw, cluster, namespace, deployment)
    if not available_metrics:
        print("Please verify the deployment name, namespace, cluster, and CloudWatch ContainerInsights setup.")
        exit(1)

    selected_metric_names = choose_discovered_metrics(available_metrics)
    if not selected_metric_names:
        print("No metrics selected. Exiting.")
        exit(0)

    for metric_name in selected_metric_names:
        print(f"\nFetching metric '{metric_name}' for deployment '{deployment}'...")
        datapoints = get_deployment_metrics(
            cw,
            cluster,
            namespace,
            deployment,
            metric_name
        )
        if not datapoints:
            print(f"No datapoints returned for metric '{metric_name}'.")
        plot_metrics(datapoints, metric_name, deployment)
