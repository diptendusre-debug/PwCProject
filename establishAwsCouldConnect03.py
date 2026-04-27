import boto3
import pandas as pd
from datetime import datetime, timedelta, timezone
from prophet import Prophet
from openai import OpenAI
from kubernetes import client, config
import matplotlib.pyplot as plt



# --- CONFIGURATION ---
OPENAI_API_KEY = "your-api-key-here"
client_ai = OpenAI(api_key='sk-proj--')

# ---------------- 1. COLLECT METRICS (CLOUDWATCH) ----------------
def get_metrics_data(cw_client, cluster, namespace, pod_name):
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=2) # Fetch last 2 hours for better forecasting
    
    response = cw_client.get_metric_statistics(
        Namespace='ContainerInsights',
        MetricName='pod_cpu_utilization',
        Dimensions=[
            {'Name': 'ClusterName', 'Value': cluster},
            {'Name': 'Namespace', 'Value': namespace},
            {'Name': 'PodName', 'Value': pod_name}
        ],
        StartTime=start_time, EndTime=end_time,
        Period=60, Statistics=['Average']
    )
    
    # Convert to Pandas DataFrame for Prophet
    df = pd.DataFrame(response['Datapoints'])
    if df.empty: return None
    
    df = df[['Timestamp', 'Average']].rename(columns={'Timestamp': 'ds', 'Average': 'y'})
    df['ds'] = df['ds'].dt.tz_localize(None) # Prophet requires timezone-naive
    return df

# ---------------- 2. FORECAST DEMAND (PROPHET) ----------------
def forecast_demand(df):
    model = Prophet(interval_width=0.95)
    model.fit(df)
    
    # Predict for the next 15 minutes
    future = model.make_future_dataframe(periods=15, freq='min')
    forecast = model.predict(future)
    
    # Get the predicted value for the next 5 minutes
    predicted_cpu = forecast.iloc[-1]['yhat']
    return round(predicted_cpu, 2)

# ---------------- 3. DECISION MAKING (OPENAI) ----------------
def get_ai_scaling_decision(predicted_load):
    prompt = f"""
    The predicted pod CPU utilization for the next 15 minutes is {predicted_load}%.
    If utilization is > 5%, recommend scaling to 2 replicas.
    If utilization is <= 5%, recommend scaling to 1 replica.
    Return ONLY the number of replicas as an integer.
    """
    
    response = client_ai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    
    decision = response.choices[0].message.content.strip()
    return int(decision)

# ---------------- 4. EXECUTE SCALING (K8S) ----------------
def scale_k8s(namespace, deployment_name, target_replicas):
    try:
        config.load_kube_config()
        apps_v1 = client.AppsV1Api()
        
        deployment = apps_v1.read_namespaced_deployment(deployment_name, namespace)
        current = deployment.spec.replicas
        
        if current != target_replicas:
            print(f"🤖 AI Decision: Scale from {current} to {target_replicas} replicas.")
            deployment.spec.replicas = target_replicas
            apps_v1.patch_namespaced_deployment(name=deployment_name, namespace=namespace, body=deployment)
        else:
            print(f"✅ AI Decision: Maintain {current} replicas (Load stable).")
    except Exception as e:
        print(f"❌ K8s Error: {e}")

# ---------------- MAIN ORCHESTRATOR ----------------
if __name__ == "__main__":
    # AWS Setup
    region = input("AWS Region: ")
    cw = boto3.Session(
        aws_access_key_id=input("Access Key: "),
        aws_secret_access_key=input("Secret Key: "),
        region_name=region
    ).client('cloudwatch')
    
    cluster = input("Cluster Name: ")
    ns = input("Namespace: ")
    pod = input("Pod Name: ")
    deploy = input("Deployment Name: ")

    # Step 1: Collect
    print("\n📡 Collecting historical metrics...")
    df_metrics = get_metrics_data(cw, cluster, ns, pod)

    if df_metrics is not None:
        # Step 2: Forecast
        print("🔮 Forecasting future demand with Prophet...")
        predicted_load = forecast_demand(df_metrics)
        print(f"📈 Predicted CPU Load: {predicted_load}%")

        # Step 3: Recommend
        print("🧠 Consulting AI for scaling strategy...")
        target_replicas = get_ai_scaling_decision(predicted_load)

        # Step 4: Scale
        scale_k8s(ns, deploy, target_replicas)
    else:
        print("❌ No data found to analyze.")
