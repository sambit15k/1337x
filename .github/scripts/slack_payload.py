#!/usr/bin/env python3
import os, json

def load_event(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def short_sha(s):
    return s[:7] if s else ''

def state_to_color(state: str) -> str:
    s = (state or '').lower()
    if s in ('success', 'completed'):
        return '#2EB67D'  # green
    if s in ('failure', 'failed', 'cancelled', 'canceled', 'timed_out'):
        return '#E01E5A'  # red
    if s in ('in_progress', 'queued', 'pending', 'requested', 'started'):
        return '#F2C744'  # yellow
    return '#439FE0'     # blue default

def state_to_emoji(state: str) -> str:
    s = (state or '').lower()
    if s in ('success', 'completed'):
        return ':white_check_mark:'
    if s in ('failure', 'failed', 'cancelled', 'canceled', 'timed_out'):
        return ':x:'
    if s in ('in_progress', 'queued', 'pending', 'requested', 'started'):
        return ':hourglass_flowing_sand:'
    return ':information_source:'

def main():
    repo = os.environ.get('REPO','')
    event = os.environ.get('EVENT','')
    actor = os.environ.get('ACTOR','')
    ref = os.environ.get('REF','')
    run_url = os.environ.get('RUN_URL','')
    evt_path = os.environ.get('GITHUB_EVENT_PATH','')

    data = load_event(evt_path) if evt_path else {}

    # Initialize fields
    pr_num = pr_url = pr_title = ''
    commit_sha = commit_url = commit_msg = ''
    release_url = release_tag = ''
    deploy_env = deploy_state = ''
    state = ''

    # Pull Request
    pr = data.get('pull_request') if isinstance(data, dict) else None
    if isinstance(pr, dict):
        pr_num = str(pr.get('number', '')) or str(pr.get('id',''))
        pr_url = pr.get('html_url','')
        pr_title = pr.get('title','') or ''
        # Try to use PR head SHA if available
        head = pr.get('head') or {}
        commit_sha = head.get('sha') or ''
        if commit_sha:
            commit_url = f"https://github.com/{repo}/commit/{commit_sha}"

    # Push / head_commit
    if not commit_sha:
        head = data.get('head_commit') or {}
        if isinstance(head, dict):
            commit_sha = head.get('id') or head.get('sha') or ''
            commit_msg = head.get('message','') or ''
        else:
            # fallback for push events where 'after' is a sha string
            after = data.get('after')
            if isinstance(after, str):
                commit_sha = after
        if commit_sha:
            commit_url = f"https://github.com/{repo}/commit/{commit_sha}"

    # Release
    rel = data.get('release') if isinstance(data, dict) else None
    if isinstance(rel, dict):
        release_url = rel.get('html_url','') or ''
        release_tag = rel.get('tag_name','') or ''

    # Deployment / deployment_status
    deploy = data.get('deployment') or {}
    if isinstance(deploy, dict):
        deploy_env = deploy.get('environment','') or ''
    deploy_status = data.get('deployment_status') or {}
    if isinstance(deploy_status, dict):
        deploy_state = deploy_status.get('state','') or ''
        state = deploy_state

    # workflow_run conclusion takes precedence if present
    workflow_run = data.get('workflow_run') if isinstance(data, dict) else None
    if isinstance(workflow_run, dict):
        conclusion = (workflow_run.get('conclusion') or '')
        if conclusion:
            state = conclusion

    # Build Blocks
    blocks = []

    # Header
    header_text = f"GitHub — {event}"
    if pr_num:
        header_text += f" · PR #{pr_num}"
    blocks.append({
        "type": "header",
        "text": {"type": "plain_text", "text": header_text}
    })

    # Main section
    repo_link = f"<https://github.com/{repo}|{repo}>"
    section_text = (
        f"*Repository:* {repo_link}\n"
        f"*Ref:* {ref or 'n/a'}\n"
        f"*Actor:* {actor or 'n/a'}\n"
        f"*Run:* <{run_url}|View workflow run>"
    )
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": section_text}})

    # Context/status
    if state:
        blocks.append({
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"{state_to_emoji(state)} *State:* `{state}`"}
            ]
        })

    # PR / Commit / Release / Deployment
    if pr_url:
        blocks.append({"type": "section",
                       "text": {"type": "mrkdwn",
                                "text": f"*Pull Request:* <{pr_url}|#{pr_num} {pr_title}>"}})

    if commit_url:
        txt = f"*Commit:* <{commit_url}|{short_sha(commit_sha)}>"
        if commit_msg:
            txt += f" — {commit_msg}"
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": txt}})

    if release_url or release_tag:
        blocks.append({"type": "section",
                       "text": {"type": "mrkdwn",
                                "text": f"*Release:* <{release_url}|{release_tag or 'view release'}>"}})

    if deploy_env or deploy_state:
        blocks.append({"type": "section",
                       "text": {"type": "mrkdwn",
                                "text": f"*Deployment:* `{deploy_state or 'unknown'}` — environment: `{deploy_env or 'unknown'}`"}})

    # Actions (max 5 elements per block; we keep it to 3)
    elements = []
    if run_url:
        # style 'danger' if something failed so the 'View logs' stands out
        btn = {
            "type": "button",
            "text": {"type": "plain_text", "text": "View logs"},
            "url": run_url,
            "action_id": "view_logs"
        }
        if (state or '').lower() in ('failure', 'failed', 'cancelled', 'canceled', 'timed_out'):
            btn["style"] = "danger"
        elements.append(btn)

    if pr_url:
        elements.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "Open PR"},
            "url": pr_url,
            "style": "primary",  # visually affirming
            "action_id": "open_pr"
        })

    if commit_url:
        elements.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "Open Commit"},
            "url": commit_url,
            "action_id": "open_commit"
        })

    if release_url:
        elements.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "Open Release"},
            "url": release_url,
            "action_id": "open_release"
        })

    if elements:
        blocks.append({"type": "actions", "elements": elements})

    # Attachment color stripe
    color = state_to_color(state)
    payload = {
        "text": f"{event} in {repo}",
        "blocks": blocks,
        "attachments": [{
            "color": color,
            "text": f"Event: {event} · State: {state or 'n/a'}"
        }]
    }

    print(json.dumps(payload))

if __name__ == '__main__':
