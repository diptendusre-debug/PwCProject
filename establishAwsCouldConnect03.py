import boto3
import pandas as pd
from datetime import datetime, timedelta, timezone
from prophet import Prophet
from openai import OpenAI
from kubernetes import client, config
import matplotlib.pyplot as plt

# --- CONFIGURATION ---
# Applying the custom URL as requested
client_ai = OpenAI(
    api_key='sk-JgUa',
    base_url="" 
)

# ---------------- AWS CONNECTION (FIXED) ----------------
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

# ---------------- 1. COLLECT METRICS (CLOUDWATCH) ----------------
def get_metrics_data(cw_client, cluster, namespace, pod_name):
    end_time = datetime.now(timezone.utc)
    # Using 2 hours of data to give Prophet enough history to learn trends
    start_time = end_time - timedelta(hours=2) 
    
    try:
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
        
        df = pd.DataFrame(response.get('Datapoints', []))
        if df.empty: 
            return None
        
        # Sort and format for Prophet (ds and y columns)
        df = df.sort_values('Timestamp')
        df = df[['Timestamp', 'Average']].rename(columns={'Timestamp': 'ds', 'Average': 'y'})
        df['ds'] = df['ds'].dt.tz_localize(None) 
        return df
    except Exception as e:
        print(f"❌ Error fetching CloudWatch data: {e}")
        return None

# ---------------- 2. FORECAST DEMAND (PROPHET) ----------------
def forecast_demand(df):
    # Suppress prophet logs for cleaner output
    import logging
    logging.getLogger('prophet').setLevel(logging.ERROR)
    
    model = Prophet(interval_width=0.95)
    model.fit(df)
    
    # Predict for the next 15 minutes
    future = model.make_future_dataframe(periods=15, freq='min')
    forecast = model.predict(future)
    
    # Get the predicted value for the end of the 15-min window
    predicted_cpu = forecast.iloc[-1]['yhat']
    return round(predicted_cpu, 2)

# ---------------- 3. DECISION MAKING (OPENAI) ----------------
def get_ai_scaling_decision(predicted_load):
    prompt = f"The predicted pod CPU utilization for the next 15 minutes is {predicted_load}%. If utilization is > 5%, return '2'. If <= 5%, return '1'. Return ONLY the integer."
    
    try:
        response = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        decision = response.choices[0].message.content.strip()
        return int(decision)
    except Exception as e:
        print(f"❌ AI API Error: {e}")
        return 1 # Default fallback

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
            print(f"✅ AI Decision: Maintain {current} replicas.")
    except Exception as e:
        print(f"❌ K8s Scaling Error: {e}")

# ---------------- MAIN ORCHESTRATOR ----------------
if __name__ == "__main__":
    reg = input("AWS Region: ").strip()
    key = input("Access Key: ").strip()
    sec = input("Secret Key: ").strip()
    
    cw = establish_aws_connection(key, sec, reg)
    
    if cw:
        cluster_name = input("Cluster Name: ").strip()
        ns = input("Namespace: ").strip()
        pod = input("Pod Name: ").strip()
        deploy = input("Deployment Name: ").strip()

        print("\n📡 Collecting historical metrics...")
        df_metrics = get_metrics_data(cw, cluster_name, ns, pod)

        if df_metrics is not None:
            print("🔮 Forecasting future demand...")
            predicted_load = forecast_demand(df_metrics)
            print(f"📈 Predicted CPU Load: {predicted_load}%")

            print("🧠 Consulting AI via Custom URL...")
            target = get_ai_scaling_decision(predicted_load)

            scale_k8s(ns, deploy, target)
        else:
            print("❌ No data found. Ensure ContainerInsights is enabled for this pod.")
