import boto3

glue = boto3.client("glue")

def run_job(job_name):
    response = glue.start_job_run(JobName=job_name)
    print("Job started:", response["JobRunId"])

if __name__ == "__main__":
    run_job("bronze_to_silver")
    run_job("silver_to_gold")
