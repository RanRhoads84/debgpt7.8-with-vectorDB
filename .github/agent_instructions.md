# 🧠 DEBGPT-AUTOFIX AGENT INSTRUCTION SET

**Repository:** `RanRhoads84/debgpt7.8-with-vectorDB`
**Purpose:** Autonomous GitHub Actions self-healing workflow for build-debgpt.yml

---

## 🧩 0. Setup
- Agent identity: `debgpt-ci-bot`
- Branch prefix: `autofix/`
- Working branch: `autofix/testing`
- Required scopes: `repo`, `actions:read`, `pull_requests:write`
- Must have read access to GitHub Actions job logs.

---

## 🔍 1. Detection Phase
- After each Actions run:
  - Fetch workflow logs for `build-debgpt.yml`.
  - Parse logs for error patterns:
    `["error", "fail", "missing", "dpkg", "unconfigured", "health endpoint", "timeout", "curl: (7)", "dependency", "cannot continue"]`
  - Categorize as:
    - **TYPE_A:** Package build errors
    - **TYPE_B:** Missing `.deb` artifacts
    - **TYPE_C:** Dependency or install order failures
    - **TYPE_D:** Bootstrap (setup_vectordb.sh) failures
    - **TYPE_E:** Health endpoint failures
    - **TYPE_F:** Missing environment dependencies
  - Write results to `/.ci/error_report.json`.

---

## 🌱 2. Branch Management
- If branch `testing` does not exist:
  ```bash
  git fetch origin
  git checkout -b testing origin/main
  ```
- If it exists:
  ```bash
  git checkout testing
  git pull --rebase origin main
  ```

---

## 🧰 3. Correction Phase

### TYPE_A – Package Build Failure
```bash
fakeroot dpkg-buildpackage -us -uc -jauto 2>&1 | tee /tmp/build.log
```
**Commit:** `[autofix]: add verbose dpkg-buildpackage output for CI diagnostics (#timestamp)`

---

### TYPE_B – Missing Debian Artifacts
Patch workflow to copy `.deb` files into the workspace root:
```bash
find .. -type f -name '*.deb' -exec mv {} . \; || true
```
**Commit:** `[autofix]: recover misplaced .deb artifacts into workspace root (#timestamp)`

---

### TYPE_C – Install Order / Dependency
Ensure correct install order:
1. debgpt
2. debgpt-vector-service
3. qdrant
Then run `apt-get install -fy`.
**Commit:** `[autofix]: correct package installation order and dependency resolution (#timestamp)`

---

### TYPE_D – Bootstrap Failure
Add pre-check to `setup_vectordb.sh`:
```bash
if ! dpkg-query -W -f='${Status}' debgpt 2>/dev/null | grep -q "install ok installed"; then
  echo "debgpt package not installed/configured; aborting vector DB bootstrap." >&2
  dpkg --audit || true
  exit 2
fi
```
**Commit:** `[autofix]: harden setup_vectordb.sh bootstrap pre-checks (#timestamp)`

---

### TYPE_E – Health Check Failures
Increase timeout and add logs:
```bash
timeout=120
interval=5
while [ $elapsed -lt $timeout ]; do
  if curl -fsS http://127.0.0.1:6333/healthz -o /tmp/qdrant-health.json; then
    echo "qdrant healthy"
    cat /tmp/qdrant-health.json
    exit 0
  fi
  sleep $interval
  elapsed=$((elapsed + interval))
done
```
**Commit:** `[autofix]: extend Qdrant health polling and add diagnostics (#timestamp)`

---

### TYPE_F – Missing Environment Dependencies
Insert missing package installs before dpkg steps:
```bash
apt-get install -y adduser curl jq procps
```
**Commit:** `[autofix]: ensure required system packages pre-installed (#timestamp)`

---

## 🔁 4. Validation Phase
```bash
git push origin autofix/testing --force-with-lease
```
- Trigger new workflow on this branch.
- Wait for completion.
- If `status != success`, re-run detection and fix iteratively.

---

## 🤖 5. Pull Request and Self-Approval
If CI passes:
```bash
gh pr create --title "Autofix: Resolved CI issues from run #<run_id>"   --body-file /.ci/error_report.json --base main --head autofix/testing
gh pr merge --squash --auto --delete-branch
```
**Commit messages:** Must include `[autofix]:` prefix and unique hash (`(#timestamp)` suffix).

---

## ⚖️ 6. Safety Rules
- Do not modify: `README`, `LICENSE`, or non-CI source directories.
- Auto-merge only if the diff < 100 lines.
- If same error reoccurs 3+ times → create GitHub Issue titled `Recurring CI failure [TYPE_X]`.

---

## ✅ 7. Termination Condition
Stop self-repair loop after **3 consecutive successful runs**.
Archive:
- `/.ci/error_report.json`
- `/.ci/patchlog.txt`
as CI artifacts for audit.

---

**End of File**
