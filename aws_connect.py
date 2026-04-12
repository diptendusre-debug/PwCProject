import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError

def list_ec2_instances(region, access_key, secret_key):
    try:
        # Create EC2 client using provided credentials
        ec2 = boto3.client(
            'ec2',
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )

        response = ec2.describe_instances()

        print(f"\n✅ EC2 Instances in region: {region}\n")

        found = False

        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                found = True

                instance_id = instance.get('InstanceId')
                instance_type = instance.get('InstanceType')
                state = instance.get('State', {}).get('Name')
                public_ip = instance.get('PublicIpAddress', 'N/A')

                print(f"Instance ID   : {instance_id}")
                print(f"Type          : {instance_type}")
                print(f"State         : {state}")
                print(f"Public IP     : {public_ip}")
                print("-" * 40)

        if not found:
            print("No EC2 instances found.")

    except NoCredentialsError:
        print("❌ Credentials not provided or invalid")
    
    except PartialCredentialsError:
        print("❌ Incomplete credentials")
    
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    # Take inputs from user
    region = input("Enter AWS Region (e.g., ap-south-1): ").strip()
    access_key = input("Enter AWS Access Key: ").strip()
    secret_key = input("Enter AWS Secret Key: ").strip()

    list_ec2_instances(region, access_key, secret_key)