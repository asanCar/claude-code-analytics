from bash_classifier import classify_bash, classify_bash_part


# --- Single-part classification ---

def test_read():
    assert classify_bash_part("cat foo.txt") == "read"
    assert classify_bash_part("ls -la") == "read"
    assert classify_bash_part("find . -name '*.py'") == "read"


def test_search():
    assert classify_bash_part("grep -n foo file") == "search"
    assert classify_bash_part("rg pattern") == "search"
    assert classify_bash_part("sed -n '1,10p' file") == "search"


def test_git_read():
    assert classify_bash_part("git log --oneline") == "git-read"
    assert classify_bash_part("git status") == "git-read"
    assert classify_bash_part("git diff HEAD~1") == "git-read"


def test_git_write():
    assert classify_bash_part("git commit -am 'fix'") == "git-write"
    assert classify_bash_part("git push origin main") == "git-write"
    assert classify_bash_part("git checkout main") == "git-write"
    assert classify_bash_part("gh pr create --title 'x'") == "git-write"
    assert classify_bash_part("gh pr merge 123") == "git-write"


def test_fileops():
    assert classify_bash_part("rm -rf /tmp/foo") == "fileops"
    assert classify_bash_part("mv src dest") == "fileops"
    assert classify_bash_part("sed -i 's/foo/bar/' file") == "fileops"


def test_infra_write():
    assert classify_bash_part("kubectl apply -f deploy.yaml") == "infra-write"
    assert classify_bash_part("docker push img:tag") == "infra-write"
    assert classify_bash_part("terraform apply") == "infra-write"


def test_infra_read():
    assert classify_bash_part("kubectl get pods") == "infra-read"
    assert classify_bash_part("docker ps") == "infra-read"
    assert classify_bash_part("kustomize build .") == "infra-read"
    assert classify_bash_part("gsutil ls gs://bucket") == "infra-read"


def test_test():
    assert classify_bash_part("pytest tests/") == "test"
    assert classify_bash_part("npm test") == "test"
    assert classify_bash_part("go test ./...") == "test"


def test_build():
    assert classify_bash_part("make all") == "build"
    assert classify_bash_part("npm run build") == "build"
    assert classify_bash_part("prettier --check .") == "build"
    assert classify_bash_part("terraform fmt") == "build"


def test_deps():
    assert classify_bash_part("npm install") == "deps"
    assert classify_bash_part("pip install requests") == "deps"
    assert classify_bash_part("brew install jq") == "deps"


def test_exec():
    assert classify_bash_part("python script.py") == "exec"
    assert classify_bash_part("./run.sh") == "exec"
    assert classify_bash_part("bun run dev") == "exec"


def test_research():
    assert classify_bash_part("curl https://example.com") == "research"
    assert classify_bash_part("gh api repos/foo/bar") == "research"


def test_db():
    assert classify_bash_part("psql -U user db") == "db"


def test_path_like_exec_fallback():
    assert classify_bash_part("tools/foo/bin/foo --help") == "exec"


def test_unknown():
    assert classify_bash_part("xyzzy --foo") == "bash-other"


# --- Pre-processing: comments, env vars, subshells, no-ops ---

def test_strip_leading_comment():
    assert classify_bash_part("# comment\ncat foo") == "read"
    assert classify_bash_part("# c1\n# c2\nrm bar") == "fileops"


def test_comment_only_returns_none():
    assert classify_bash_part("# just a comment") is None


def test_strip_env_var_prefix():
    assert classify_bash_part("PYTHONPATH=. pytest tests/") == "test"
    assert classify_bash_part("FOO=bar BAZ=qux python s.py") == "exec"


def test_subshell_assignment_recurses():
    assert classify_bash_part("BODY=$(curl https://x.com)") == "research"
    assert classify_bash_part("RESULT=$(rm -rf /tmp/foo)") == "fileops"


def test_noop_cd_returns_none():
    assert classify_bash_part("cd /foo/bar") is None


def test_noop_source_returns_none():
    assert classify_bash_part("source .env") is None
    assert classify_bash_part(". /path/to/script.sh") is None


def test_noop_export_returns_none():
    assert classify_bash_part("export FOO=bar") is None


# --- Compound commands and priority resolution ---

def test_compound_fileops_beats_read():
    assert classify_bash("cat foo && rm bar") == "fileops"


def test_compound_git_write_beats_test_and_read():
    assert classify_bash("git status && pytest && git commit -am 'fix'") == "git-write"


def test_compound_pipe_search_wins():
    assert classify_bash("find . | grep foo | head") == "search"


def test_compound_infra_write_beats_read():
    assert classify_bash("docker ps && docker push img") == "infra-write"


def test_compound_pipe_infra_read():
    assert classify_bash("kubectl get pods | grep err") == "infra-read"


def test_compound_sed_inplace_beats_cat():
    assert classify_bash("cat foo | sed -i 's/X/Y/' bar") == "fileops"


def test_compound_cd_then_ls():
    assert classify_bash("cd /foo && ls") == "read"


def test_compound_cd_then_rm():
    assert classify_bash("cd /foo && rm -rf bar") == "fileops"


def test_compound_source_then_python():
    assert classify_bash("source .env && python script.py") == "exec"


def test_empty_or_none():
    assert classify_bash(None) is None
    assert classify_bash("") is None
    assert classify_bash("   ") is None


def test_only_comments_returns_bash_other():
    assert classify_bash("# just a comment") == "bash-other"
