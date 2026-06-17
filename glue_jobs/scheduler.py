import boto3

glue = boto3.client("glue")


def run_job(job_name):
    try:
        response = glue.start_job_run(JobName=job_name)
        print(f"Job {job_name} started:", response["JobRunId"])
    except Exception as e:
        print(f"Error running {job_name}:", e)


if __name__ == "__main__":
    run_job("bronze_to_silver")
    run_job("silver_to_gold")
