from beacon.application.ports import JobDetail, JobFilters, JobPage, JobRepo


def list_jobs(jobs: JobRepo, filters: JobFilters) -> JobPage:
    return jobs.search(filters)


def get_job(jobs: JobRepo, job_id: int) -> JobDetail | None:
    return jobs.get_job_detail(job_id)
