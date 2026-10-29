# GitHub publication checklist

- [ ] Confirm no private data in screenshots or source files.
- [ ] Confirm `.env`, `data/`, virtual environments and local databases are absent from `git status`.
- [ ] Run app locally and verify homepage, CV matching and saved jobs.
- [ ] Run `python run_all_tests.py` and review any network/provider failures.
- [ ] Confirm ownership/permission for code and design assets.
- [ ] Publish as **Public** only after reviewing staged changes.
- [ ] Add a GitHub description and topics (python, fastapi, job-search, resume-parser, portfolio-project).
- [ ] For LinkedIn, use a GitHub repo link and one UI screenshot. Describe match score as a heuristic, not hiring prediction.

## VS Code publishing

1. Open the extracted `SCOUTY-AI` folder in VS Code.
2. In **Source Control**, select **Initialize Repository** (if needed).
3. Check changed files; confirm secrets and database files are excluded.
4. Enter commit message: `Initial public release: SCOUTY AI` and select **Commit**.
5. Select **Publish Branch / Publish to GitHub**.
6. Sign into GitHub, select a new repo named `SCOUTY-AI`, and choose visibility.
7. Open your GitHub repository page and verify the README images load.

Command-line alternative (after checking files):

```bash
git init
git add .
git status
git commit -m "Initial public release: SCOUTY AI"
```

To push via VS Code choose **Publish Branch**; it handles remote creation.
