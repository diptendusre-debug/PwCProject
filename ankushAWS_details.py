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


# ---------------- LIST PODS ----------------
def list_pods(cw_client, cluster, namespace):
    paginator = cw_client.get_paginator('list_metrics')
    pods = set()

    for response in paginator.paginate(
        Namespace='ContainerInsights',
        Dimensions=[
            {'Name': 'ClusterName', 'Value': cluster},
            {'Name': 'Namespace', 'Value': namespace}
        ]
    ):
        for metric in response.get('Metrics', []):
            for dim in metric.get('Dimensions', []):
                if dim.get('Name') == 'PodName':
                    pods.add(dim.get('Value'))

    if pods:
        print("\n✅ Discovered Pods:")
        for p in sorted(pods):
            print(f"  - {p}")
    else:
        print("\n⚠️ No pods found. Check ContainerInsights setup.")

    return sorted(list(pods))


# ---------------- LIST METRICS FOR A POD ----------------
def list_pod_metrics(cw_client, cluster, namespace, pod_name):
    paginator = cw_client.get_paginator('list_metrics')
    metrics = []

    for response in paginator.paginate(
        Namespace='ContainerInsights',
        Dimensions=[
            {'Name': 'ClusterName', 'Value': cluster},
            {'Name': 'Namespace', 'Value': namespace},
            {'Name': 'PodName', 'Value': pod_name}
        ]
    ):
        for metric in response.get('Metrics', []):
            metrics.append(metric['MetricName'])

    unique_metrics = sorted(list(set(metrics)))

    if unique_metrics:
        print(f"\n📊 Metrics available for pod '{pod_name}':")
        for i, m in enumerate(unique_metrics, 1):
            print(f"  {i}. {m}")
    else:
        print(f"\n⚠️ No metrics found for pod '{pod_name}'")

    return unique_metrics


# ---------------- SELECT METRICS ----------------
def choose_metrics(metric_list):
    choice = input("\nEnter metric number(s) (comma-separated) or press Enter for all: ").strip()

    if not choice:
        return metric_list

    selected = []
    for part in choice.split(','):
        part = part.strip()
        if part.isdigit():
            idx = int(part) - 1
            if 0 <= idx < len(metric_list):
                selected.append(metric_list[idx])

    return selected


# ---------------- FETCH POD METRICS ----------------
def get_pod_metrics(cw_client, cluster, namespace, pod_name, metric_name, period=60, minutes=10):
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=minutes)

    try:
        response = cw_client.get_metric_statistics(
            Namespace='ContainerInsights',
            MetricName=metric_name,
            Dimensions=[
                {'Name': 'ClusterName', 'Value': cluster},
                {'Name': 'Namespace', 'Value': namespace},
                {'Name': 'PodName', 'Value': pod_name}
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=period,
            Statistics=['Average']
        )

        datapoints = sorted(response.get('Datapoints', []), key=lambda x: x['Timestamp'])
        return datapoints

    except Exception as e:
        print(f"❌ Error fetching metrics for pod {pod_name}: {e}")
        return []


# ---------------- PLOT & DISPLAY ----------------
def plot_metrics(datapoints, metric_label, pod_name):
    if not datapoints:
        print(f"No data found for {metric_label}")
        return

    # --- RAW DATA DISPLAY ---
    print(f"\n--- [DATA REPORT] {metric_label} ({pod_name}) ---")
    print(f"{'Timestamp (UTC)':<20} | {'Average Value':<15}")
    print("-" * 40)

    for p in datapoints:
        ts = p['Timestamp'].strftime('%H:%M:%S')
        val = round(p['Average'], 4)
        print(f"{ts:<20} | {val:<15}")

    print("-" * 40)

    times = [p['Timestamp'].strftime('%H:%M') for p in datapoints]
    values = [p['Average'] for p in datapoints]

    plt.figure(figsize=(10, 5))
    plt.plot(times, values, marker='o', linestyle='-')
    plt.title(f"{pod_name} - {metric_label}")
    plt.xlabel("Time (UTC)")
    plt.ylabel(metric_label)
    plt.grid(True)

    file_name = f"{pod_name}_{metric_label.lower().replace(' ', '_')}.png"
    plt.savefig(file_name)
    print(f"📊 Graph saved as: {file_name}\n")
    plt.close()


# ---------------- MAIN ----------------
if __name__ == "__main__":
    region = input("AWS Region (e.g., ap-south-1): ").strip()
    access_key = input("Access Key: ").strip()
    secret_key = input("Secret Key: ").strip()
    cluster = input("Cluster Name: ").strip()
    namespace = input("Namespace: ").strip()

    cw = establish_aws_connection(access_key, secret_key, region)
    if not cw:
        exit(1)

    # Step 1: Get Pods
    pods = list_pods(cw, cluster, namespace)
    if not pods:
        exit(1)

    pod_name = input("\nEnter Pod Name: ").strip()

    # Step 2: Get Metrics
    metrics = list_pod_metrics(cw, cluster, namespace, pod_name)
    if not metrics:
        exit(1)

    selected_metrics = choose_metrics(metrics)

    # Step 3: Fetch + Plot
    for metric in selected_metrics:
        print(f"\nFetching: {metric}...")
        data = get_pod_metrics(cw, cluster, namespace, pod_name, metric)
        plot_metrics(data, metric, pod_name)