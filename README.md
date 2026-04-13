# PwCProject

            aws_connect.py
**********************************************************
The provided code in aws_connect.py is a Python script that connects to an AWS account using the `boto3` library to list EC2 instances in a specified region. Here's a breakdown of its components and functionality:

### Imports
- `import boto3`: Imports the AWS SDK for Python, which provides interfaces to interact with AWS services.
- `from botocore.exceptions import NoCredentialsError, PartialCredentialsError`: Imports specific exceptions from `botocore` (boto3's underlying library) to handle authentication errors.

### Function: `list_ec2_instances(region, access_key, secret_key)`
This function performs the core logic:
- **Parameters**: Takes the AWS region (e.g., 'us-east-1'), access key ID, and secret access key as inputs.
- **Client Creation**: Uses `boto3.client('ec2', ...)` to create an EC2 client authenticated with the provided credentials. This establishes a connection to the AWS EC2 service in the specified region.
- **API Call**: Calls `ec2.describe_instances()` to retrieve details about all EC2 instances in the account/region. The response is a dictionary containing a list of reservations.
- **Processing and Output**:
  - Iterates through `response['Reservations']` (each reservation can contain multiple instances).
  - For each instance, extracts and prints key details: Instance ID, type, state, and public IP address.
  - If no instances are found, prints a message indicating that.
- **Error Handling**:
  - `NoCredentialsError`: Raised if credentials are missing or invalid.
  - `PartialCredentialsError`: Raised if credentials are incomplete (e.g., only access key provided).
  - Generic `Exception`: Catches and prints any other errors (e.g., network issues or API failures).

### Main Block (`if __name__ == "__main__":`)
- Prompts the user to input the AWS region, access key, and secret key via `input()`.
- Calls `list_ec2_instances()` with these inputs.
- This allows the script to run interactively when executed directly.

### Key Notes
- **Security**: Hardcoding or inputting credentials directly is insecure for production use. Best practices include using AWS IAM roles, environment variables, or AWS CLI configuration (e.g., via `~/.aws/credentials` or `boto3.Session()` for automatic credential resolution).
- **Permissions**: The AWS user/role must have permissions to describe EC2 instances (e.g., via the `ec2:DescribeInstances` policy).
- **Dependencies**: Requires `boto3` (install via `pip install boto3`) and valid AWS credentials.
- **Limitations**: This script only lists instances; it doesn't handle pagination for large result sets or other AWS services.

To run the script, ensure `boto3` is installed (`pip install boto3`), provide valid AWS credentials, and execute it in a terminal. For more advanced usage, consider using AWS SDK best practices like session management.
**********************************************************

