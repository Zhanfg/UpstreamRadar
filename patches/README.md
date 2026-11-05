# GitLab downstream permission soft-fail

`scripts/downstream_gitlab.py` is not in this repository. The GitLab Bridge
clones it from `https://gitlab.com/axymorrsen/upstreamradar.git` and, until
that file already soft-fails, applies:

`patches/downstream_gitlab_permission_soft_fail.patch`

Apply the same patch on the GitLab project so the bridge can stop patching
the clone. From a checkout of `axymorrsen/upstreamradar` on `main`:

```sh
patch --forward --batch -p1 -i downstream_gitlab_permission_soft_fail.patch
python -m unittest tests.test_downstream_gitlab_executor -v
```

The patch updates `scripts/downstream_gitlab.py` and adds
`tests/test_downstream_gitlab_executor.py`. After it is committed on GitLab,
the bridge sees `skipped_permission` in the script and does not apply the
patch again.

Creating an issue returns success for HTTP 401, 403, and 404: the run logs
`DOWNSTREAM=WARN skip issue creation`, names the impact and target repo,
redacts the token, skips that impact, and continues. Any other status,
including 410 when issues are disabled and 500, still fails the run.
