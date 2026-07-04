from beacon.application.ports import JobFilters, JobPage, JobRepo


def list_jobs(jobs: JobRepo, filters: JobFilters) -> JobPage:
    return jobs.search(filters)
