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
        print(f"❌ AWS Connection Error: {e}")
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
        print(f"\n✅ Discovered metrics for '{deployment_name}':")
        for metric in discovered:
            print(f"  - {metric['MetricName']}")
    else:
        print(f"\n⚠️ No metrics discovered for '{deployment_name}'. Check ContainerInsights setup.")

    return discovered

def choose_discovered_metrics(metrics):
    unique_names = sorted(list(set(m.get('MetricName') for m in metrics)))
    if not unique_names:
        return []

    print("\nAvailable Metrics:")
    for index, name in enumerate(unique_names, start=1):
        print(f"  {index}. {name}")

    choice = input("\nEnter number(s) (comma-separated) or press Enter for all: ").strip()

    if not choice:
        return unique_names

    selected = []
    for part in choice.split(','):
        part = part.strip()
        if part.isdigit():
            idx = int(part) - 1
            if 0 <= idx < len(unique_names):
                selected.append(unique_names[idx])
    return selected

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
                print(f"🔎 Using dimension: {dimension_name}")
                return datapoints
        except Exception as e:
            continue
    return []

# ---------------- PLOT & DISPLAY ----------------
def plot_metrics(datapoints, metric_label, deployment):
    if not datapoints:
        print(f"No data found for {metric_label}")
        return

    # --- NEW: RAW DATA DISPLAY ---
    print(f"\n--- [DATA REPORT] {metric_label} ---")
    print(f"{'Timestamp (UTC)':<20} | {'Average Value':<15}")
    print("-" * 40)
    
    for p in datapoints:
        ts = p['Timestamp'].strftime('%H:%M:%S')
        val = round(p['Average'], 4)
        print(f"{ts:<20} | {val:<15}")
    print("-" * 40)
    # -----------------------------

    times = [p['Timestamp'].strftime('%H:%M') for p in datapoints]
    values = [p['Average'] for p in datapoints]

    plt.figure(figsize=(10, 5))
    plt.plot(times, values, marker='o', linestyle='-', color='tab:blue')
    plt.title(f"{deployment} - {metric_label}")
    plt.xlabel("Time (UTC)")
    plt.ylabel(metric_label)
    plt.grid(True)

    file_name = f"{deployment}{metric_label.lower().replace(' ', '')}.png"
    plt.savefig(file_name)
    print(f"📊 Graph saved as: {file_name}\n")
    plt.close()

# ---------------- MAIN ----------------
if _name_ == "_main_":
    region = input("AWS Region (e.g., ap-south-1): ").strip()
    access_key = input("Access Key: ").strip()
    secret_key = input("Secret Key: ").strip()
    cluster = input("Cluster Name: ").strip()
    namespace = input("Namespace: ").strip()
    deployment = input("Deployment Name: ").strip()

    cw = establish_aws_connection(access_key, secret_key, region)
    if not cw:
        exit(1)

    available_metrics = list_deployment_metrics(cw, cluster, namespace, deployment)
    if not available_metrics:
        exit(1)

    selected_names = choose_discovered_metrics(available_metrics)
    
    for name in selected_names:
        print(f"\nFetching: {name}...")
        data = get_deployment_metrics(cw, cluster, namespace, deployment, name)
        plot_metrics(data, name, deployment)