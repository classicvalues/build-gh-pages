import json
import hashlib
import hmac
import git
import os
import base64
import requests
import shutil
from sphinx.application import Sphinx
from boto3 import client as boto3_client


lambda_client = boto3_client('lambda', region_name="us-east-1",)


def validate_signature(headers, event_body, github_token):
    try:
        signature = headers['X-Hub-Signature']
        _, sha1 = signature.split('=')
    except:
        return "Bad Request"
    digest = hmac.new(github_token.encode(), event_body.encode(), hashlib.sha1).hexdigest()
    if not hmac.compare_digest(digest.encode(), sha1.encode()):
        return "Not Authorized"


def docs_files_changed(pr_number):
    file_endpoint = "https://api.github.com/repos/conda/conda/pulls/%s/files" % (pr_number)
    files = json.loads(requests.get(file_endpoint).content)
    for file in files:
        if "docs" in file["filename"]:
            return True
    return False


def build(event, context):
    SPHINXBUILD = os.getenv('SPHINXBUILD', 'sphinx-build')
    json_payload = json.loads(event["body"])

    github_repo = json_payload["repository"]['html_url']
    pr_number = json_payload["number"]

    repo_path = "/tmp/conda"
    try:
        shutil.rmtree(repo_path)
    except FileNotFoundError:
        # It's ok if file was not found, didn't want the file anyway
        pass
    git.exec_command("clone", github_repo, repo_path)
    os.chdir(repo_path)
    git.exec_command("fetch", "origin", "+refs/pull/%s/head:pr/%s" % (pr_number, pr_number), cwd=repo_path)
    git.exec_command("checkout", "pr/%s" % pr_number, cwd=repo_path)

    docs_path = os.path.join(repo_path, "docs/source")
    confdir = docs_path
    build_output = os.path.join(repo_path, "pr-%s" % (pr_number))
    doctreedir = os.path.join(build_output, "doctrees")
    builder = "html"

    app = Sphinx(docs_path, confdir, build_output, doctreedir, builder)
    app.build()

    response_body = "built docs change"

    response = {
        "statusCode": 200,
        "body": json.dumps(response_body)
    }
    print(response)
    return response


def build_docs(event, context):
    github_token = os.environ["github_token"]
    headers = event["headers"]

    # Make sure request came from github
    try:
        event_type = headers['X-GitHub-Event']
    except KeyError:
        raise Exception("Bad Request")

    # Make sure request has valid token
    signature_response = validate_signature(headers, event["body"], github_token)
    if signature_response is not None:
        response = {
            "statusCode": 500,
            "body": "ohhhh no %s" % signature_response
        }
        return response

    if event['isBase64Encoded'] == True:
        print("Decoding body")
        event["body"] = base64.b64decode(event['body'])

    json_payload = json.loads(event["body"])

    github_repo = json_payload["repository"]['html_url']
    pr_number = json_payload["number"]

    if not docs_files_changed(pr_number):
        response_body = "no docs changes"
    else:
        print("passing off build")
        # build(event, context)
        lambda_client.invoke(
            FunctionName="build-gh-pages-dev-build",
            InvocationType='Event',
            Payload=json.dumps(event)
        )
        response_body = "building docs change"

    response = {
        "statusCode": 202,
        "body": json.dumps(response_body)
    }
    print(response)
    return response


if __name__ == "__main__":
    event = {"resource": "/build_docs", "path": "/build_docs", "httpMethod": "POST", "headers": {"Accept": "*/*", "CloudFront-Forwarded-Proto": "https", "CloudFront-Is-Desktop-Viewer": "true", "CloudFront-Is-Mobile-Viewer": "false", "CloudFront-Is-SmartTV-Viewer": "false", "CloudFront-Is-Tablet-Viewer": "false", "CloudFront-Viewer-Country": "US", "content-type": "application/json", "Host": "c8r02uj8n9.execute-api.us-east-1.amazonaws.com", "User-Agent": "GitHub-Hookshot/123faed", "Via": "1.1 8918721f9949345e08455e61518a59ed.cloudfront.net (CloudFront)", "X-Amz-Cf-Id": "9jMvE0W_dXW_3RuB2NyqJ0PSUK1B8gjjcm-RPzuSyCeRJQ_oX5wVcQ==", "X-Amzn-Trace-Id": "Root=1-5c82b3fa-771e10f0ce8735f8a48d2fc2", "X-Forwarded-For": "192.30.252.45, 70.132.32.151", "X-Forwarded-Port": "443", "X-Forwarded-Proto": "https", "X-GitHub-Delivery": "b2de5960-4156-11e9-8d36-8478a8ef7285", "X-GitHub-Event": "pull_request", "X-Hub-Signature": "sha1=bb15d1e71eebc5807ed04587b068ecb7a6aacfd4"}, "multiValueHeaders": {"Accept": ["*/*"], "CloudFront-Forwarded-Proto": ["https"], "CloudFront-Is-Desktop-Viewer": ["true"], "CloudFront-Is-Mobile-Viewer": ["false"], "CloudFront-Is-SmartTV-Viewer": ["false"], "CloudFront-Is-Tablet-Viewer": ["false"], "CloudFront-Viewer-Country": ["US"], "content-type": ["application/json"], "Host": ["c8r02uj8n9.execute-api.us-east-1.amazonaws.com"], "User-Agent": ["GitHub-Hookshot/123faed"], "Via": ["1.1 8918721f9949345e08455e61518a59ed.cloudfront.net (CloudFront)"], "X-Amz-Cf-Id": ["9jMvE0W_dXW_3RuB2NyqJ0PSUK1B8gjjcm-RPzuSyCeRJQ_oX5wVcQ=="], "X-Amzn-Trace-Id": ["Root=1-5c82b3fa-771e10f0ce8735f8a48d2fc2"], "X-Forwarded-For": ["192.30.252.45, 70.132.32.151"], "X-Forwarded-Port": ["443"], "X-Forwarded-Proto": ["https"], "X-GitHub-Delivery": ["b2de5960-4156-11e9-8d36-8478a8ef7285"], "X-GitHub-Event": ["pull_request"], "X-Hub-Signature": ["sha1=bb15d1e71eebc5807ed04587b068ecb7a6aacfd4"]}, "queryStringParameters": None, "multiValueQueryStringParameters": None, "pathParameters": None, "stageVariables": None, "requestContext": {"resourceId": "l7y2fz", "resourcePath": "/build_docs", "httpMethod": "POST", "extendedRequestId": "WPEPJFBPoAMF_qA=", "requestTime": "08/Mar/2019:18:27:06 +0000", "path": "/dev/build_docs", "accountId": "588676144775", "protocol": "HTTP/1.1", "stage": "dev", "domainPrefix": "c8r02uj8n9", "requestTimeEpoch": 1552069626579, "requestId": "c71812a4-41cf-11e9-a27a-5fb4796f6331", "identity": {"cognitoIdentityPoolId": None, "accountId": None, "cognitoIdentityId": None, "caller": None, "sourceIp": "192.30.252.45", "accessKey": None, "cognitoAuthenticationType": None, "cognitoAuthenticationProvider": None, "userArn": None, "userAgent": "GitHub-Hookshot/123faed", "user": None}, "domainName": "c8r02uj8n9.execute-api.us-east-1.amazonaws.com", "apiId": "c8r02uj8n9"}, "body": "{\"action\":\"opened\",\"number\":8390,\"pull_request\":{\"url\":\"https://api.github.com/repos/conda/conda/pulls/8390\",\"id\":259353868,\"node_id\":\"MDExOlB1bGxSZXF1ZXN0MjU5MzUzODY4\",\"html_url\":\"https://github.com/conda/conda/pull/8390\",\"diff_url\":\"https://github.com/conda/conda/pull/8390.diff\",\"patch_url\":\"https://github.com/conda/conda/pull/8390.patch\",\"issue_url\":\"https://api.github.com/repos/conda/conda/issues/8390\",\"number\":8390,\"state\":\"open\",\"locked\":false,\"title\":\"Test webhook\",\"user\":{\"login\":\"soapy1\",\"id\":976973,\"node_id\":\"MDQ6VXNlcjk3Njk3Mw==\",\"avatar_url\":\"https://avatars0.githubusercontent.com/u/976973?v=4\",\"gravatar_id\":\"\",\"url\":\"https://api.github.com/users/soapy1\",\"html_url\":\"https://github.com/soapy1\",\"followers_url\":\"https://api.github.com/users/soapy1/followers\",\"following_url\":\"https://api.github.com/users/soapy1/following{/other_user}\",\"gists_url\":\"https://api.github.com/users/soapy1/gists{/gist_id}\",\"starred_url\":\"https://api.github.com/users/soapy1/starred{/owner}{/repo}\",\"subscriptions_url\":\"https://api.github.com/users/soapy1/subscriptions\",\"organizations_url\":\"https://api.github.com/users/soapy1/orgs\",\"repos_url\":\"https://api.github.com/users/soapy1/repos\",\"events_url\":\"https://api.github.com/users/soapy1/events{/privacy}\",\"received_events_url\":\"https://api.github.com/users/soapy1/received_events\",\"type\":\"User\",\"site_admin\":false},\"body\":\"\",\"created_at\":\"2019-03-08T04:00:23Z\",\"updated_at\":\"2019-03-08T04:00:23Z\",\"closed_at\":null,\"merged_at\":null,\"merge_commit_sha\":null,\"assignee\":null,\"assignees\":[],\"requested_reviewers\":[],\"requested_teams\":[],\"labels\":[],\"milestone\":null,\"commits_url\":\"https://api.github.com/repos/conda/conda/pulls/8390/commits\",\"review_comments_url\":\"https://api.github.com/repos/conda/conda/pulls/8390/comments\",\"review_comment_url\":\"https://api.github.com/repos/conda/conda/pulls/comments{/number}\",\"comments_url\":\"https://api.github.com/repos/conda/conda/issues/8390/comments\",\"statuses_url\":\"https://api.github.com/repos/conda/conda/statuses/ae3e2a519b02694775ebaeacedcd90c4ecbf590c\",\"head\":{\"label\":\"soapy1:docs-test\",\"ref\":\"docs-test\",\"sha\":\"ae3e2a519b02694775ebaeacedcd90c4ecbf590c\",\"user\":{\"login\":\"soapy1\",\"id\":976973,\"node_id\":\"MDQ6VXNlcjk3Njk3Mw==\",\"avatar_url\":\"https://avatars0.githubusercontent.com/u/976973?v=4\",\"gravatar_id\":\"\",\"url\":\"https://api.github.com/users/soapy1\",\"html_url\":\"https://github.com/soapy1\",\"followers_url\":\"https://api.github.com/users/soapy1/followers\",\"following_url\":\"https://api.github.com/users/soapy1/following{/other_user}\",\"gists_url\":\"https://api.github.com/users/soapy1/gists{/gist_id}\",\"starred_url\":\"https://api.github.com/users/soapy1/starred{/owner}{/repo}\",\"subscriptions_url\":\"https://api.github.com/users/soapy1/subscriptions\",\"organizations_url\":\"https://api.github.com/users/soapy1/orgs\",\"repos_url\":\"https://api.github.com/users/soapy1/repos\",\"events_url\":\"https://api.github.com/users/soapy1/events{/privacy}\",\"received_events_url\":\"https://api.github.com/users/soapy1/received_events\",\"type\":\"User\",\"site_admin\":false},\"repo\":{\"id\":66866992,\"node_id\":\"MDEwOlJlcG9zaXRvcnk2Njg2Njk5Mg==\",\"name\":\"conda\",\"full_name\":\"soapy1/conda\",\"private\":false,\"owner\":{\"login\":\"soapy1\",\"id\":976973,\"node_id\":\"MDQ6VXNlcjk3Njk3Mw==\",\"avatar_url\":\"https://avatars0.githubusercontent.com/u/976973?v=4\",\"gravatar_id\":\"\",\"url\":\"https://api.github.com/users/soapy1\",\"html_url\":\"https://github.com/soapy1\",\"followers_url\":\"https://api.github.com/users/soapy1/followers\",\"following_url\":\"https://api.github.com/users/soapy1/following{/other_user}\",\"gists_url\":\"https://api.github.com/users/soapy1/gists{/gist_id}\",\"starred_url\":\"https://api.github.com/users/soapy1/starred{/owner}{/repo}\",\"subscriptions_url\":\"https://api.github.com/users/soapy1/subscriptions\",\"organizations_url\":\"https://api.github.com/users/soapy1/orgs\",\"repos_url\":\"https://api.github.com/users/soapy1/repos\",\"events_url\":\"https://api.github.com/users/soapy1/events{/privacy}\",\"received_events_url\":\"https://api.github.com/users/soapy1/received_events\",\"type\":\"User\",\"site_admin\":false},\"html_url\":\"https://github.com/soapy1/conda\",\"description\":\"OS-agnostic, system-level binary package manager and ecosystem\",\"fork\":true,\"url\":\"https://api.github.com/repos/soapy1/conda\",\"forks_url\":\"https://api.github.com/repos/soapy1/conda/forks\",\"keys_url\":\"https://api.github.com/repos/soapy1/conda/keys{/key_id}\",\"collaborators_url\":\"https://api.github.com/repos/soapy1/conda/collaborators{/collaborator}\",\"teams_url\":\"https://api.github.com/repos/soapy1/conda/teams\",\"hooks_url\":\"https://api.github.com/repos/soapy1/conda/hooks\",\"issue_events_url\":\"https://api.github.com/repos/soapy1/conda/issues/events{/number}\",\"events_url\":\"https://api.github.com/repos/soapy1/conda/events\",\"assignees_url\":\"https://api.github.com/repos/soapy1/conda/assignees{/user}\",\"branches_url\":\"https://api.github.com/repos/soapy1/conda/branches{/branch}\",\"tags_url\":\"https://api.github.com/repos/soapy1/conda/tags\",\"blobs_url\":\"https://api.github.com/repos/soapy1/conda/git/blobs{/sha}\",\"git_tags_url\":\"https://api.github.com/repos/soapy1/conda/git/tags{/sha}\",\"git_refs_url\":\"https://api.github.com/repos/soapy1/conda/git/refs{/sha}\",\"trees_url\":\"https://api.github.com/repos/soapy1/conda/git/trees{/sha}\",\"statuses_url\":\"https://api.github.com/repos/soapy1/conda/statuses/{sha}\",\"languages_url\":\"https://api.github.com/repos/soapy1/conda/languages\",\"stargazers_url\":\"https://api.github.com/repos/soapy1/conda/stargazers\",\"contributors_url\":\"https://api.github.com/repos/soapy1/conda/contributors\",\"subscribers_url\":\"https://api.github.com/repos/soapy1/conda/subscribers\",\"subscription_url\":\"https://api.github.com/repos/soapy1/conda/subscription\",\"commits_url\":\"https://api.github.com/repos/soapy1/conda/commits{/sha}\",\"git_commits_url\":\"https://api.github.com/repos/soapy1/conda/git/commits{/sha}\",\"comments_url\":\"https://api.github.com/repos/soapy1/conda/comments{/number}\",\"issue_comment_url\":\"https://api.github.com/repos/soapy1/conda/issues/comments{/number}\",\"contents_url\":\"https://api.github.com/repos/soapy1/conda/contents/{+path}\",\"compare_url\":\"https://api.github.com/repos/soapy1/conda/compare/{base}...{head}\",\"merges_url\":\"https://api.github.com/repos/soapy1/conda/merges\",\"archive_url\":\"https://api.github.com/repos/soapy1/conda/{archive_format}{/ref}\",\"downloads_url\":\"https://api.github.com/repos/soapy1/conda/downloads\",\"issues_url\":\"https://api.github.com/repos/soapy1/conda/issues{/number}\",\"pulls_url\":\"https://api.github.com/repos/soapy1/conda/pulls{/number}\",\"milestones_url\":\"https://api.github.com/repos/soapy1/conda/milestones{/number}\",\"notifications_url\":\"https://api.github.com/repos/soapy1/conda/notifications{?since,all,participating}\",\"labels_url\":\"https://api.github.com/repos/soapy1/conda/labels{/name}\",\"releases_url\":\"https://api.github.com/repos/soapy1/conda/releases{/id}\",\"deployments_url\":\"https://api.github.com/repos/soapy1/conda/deployments\",\"created_at\":\"2016-08-29T17:55:26Z\",\"updated_at\":\"2019-03-07T14:24:54Z\",\"pushed_at\":\"2019-03-08T04:00:11Z\",\"git_url\":\"git://github.com/soapy1/conda.git\",\"ssh_url\":\"git@github.com:soapy1/conda.git\",\"clone_url\":\"https://github.com/soapy1/conda.git\",\"svn_url\":\"https://github.com/soapy1/conda\",\"homepage\":\"conda.pydata.org\",\"size\":46781,\"stargazers_count\":0,\"watchers_count\":0,\"language\":\"Python\",\"has_issues\":false,\"has_projects\":true,\"has_downloads\":true,\"has_wiki\":true,\"has_pages\":true,\"forks_count\":0,\"mirror_url\":null,\"archived\":false,\"open_issues_count\":0,\"license\":{\"key\":\"other\",\"name\":\"Other\",\"spdx_id\":\"NOASSERTION\",\"url\":null,\"node_id\":\"MDc6TGljZW5zZTA=\"},\"forks\":0,\"open_issues\":0,\"watchers\":0,\"default_branch\":\"master\"}},\"base\":{\"label\":\"conda:master\",\"ref\":\"master\",\"sha\":\"c7f388c917404b10e4fe4e16df0063465ee2ea61\",\"user\":{\"login\":\"conda\",\"id\":6392739,\"node_id\":\"MDEyOk9yZ2FuaXphdGlvbjYzOTI3Mzk=\",\"avatar_url\":\"https://avatars0.githubusercontent.com/u/6392739?v=4\",\"gravatar_id\":\"\",\"url\":\"https://api.github.com/users/conda\",\"html_url\":\"https://github.com/conda\",\"followers_url\":\"https://api.github.com/users/conda/followers\",\"following_url\":\"https://api.github.com/users/conda/following{/other_user}\",\"gists_url\":\"https://api.github.com/users/conda/gists{/gist_id}\",\"starred_url\":\"https://api.github.com/users/conda/starred{/owner}{/repo}\",\"subscriptions_url\":\"https://api.github.com/users/conda/subscriptions\",\"organizations_url\":\"https://api.github.com/users/conda/orgs\",\"repos_url\":\"https://api.github.com/users/conda/repos\",\"events_url\":\"https://api.github.com/users/conda/events{/privacy}\",\"received_events_url\":\"https://api.github.com/users/conda/received_events\",\"type\":\"Organization\",\"site_admin\":false},\"repo\":{\"id\":6235174,\"node_id\":\"MDEwOlJlcG9zaXRvcnk2MjM1MTc0\",\"name\":\"conda\",\"full_name\":\"conda/conda\",\"private\":false,\"owner\":{\"login\":\"conda\",\"id\":6392739,\"node_id\":\"MDEyOk9yZ2FuaXphdGlvbjYzOTI3Mzk=\",\"avatar_url\":\"https://avatars0.githubusercontent.com/u/6392739?v=4\",\"gravatar_id\":\"\",\"url\":\"https://api.github.com/users/conda\",\"html_url\":\"https://github.com/conda\",\"followers_url\":\"https://api.github.com/users/conda/followers\",\"following_url\":\"https://api.github.com/users/conda/following{/other_user}\",\"gists_url\":\"https://api.github.com/users/conda/gists{/gist_id}\",\"starred_url\":\"https://api.github.com/users/conda/starred{/owner}{/repo}\",\"subscriptions_url\":\"https://api.github.com/users/conda/subscriptions\",\"organizations_url\":\"https://api.github.com/users/conda/orgs\",\"repos_url\":\"https://api.github.com/users/conda/repos\",\"events_url\":\"https://api.github.com/users/conda/events{/privacy}\",\"received_events_url\":\"https://api.github.com/users/conda/received_events\",\"type\":\"Organization\",\"site_admin\":false},\"html_url\":\"https://github.com/conda/conda\",\"description\":\"OS-agnostic, system-level binary package manager and ecosystem\",\"fork\":false,\"url\":\"https://api.github.com/repos/conda/conda\",\"forks_url\":\"https://api.github.com/repos/conda/conda/forks\",\"keys_url\":\"https://api.github.com/repos/conda/conda/keys{/key_id}\",\"collaborators_url\":\"https://api.github.com/repos/conda/conda/collaborators{/collaborator}\",\"teams_url\":\"https://api.github.com/repos/conda/conda/teams\",\"hooks_url\":\"https://api.github.com/repos/conda/conda/hooks\",\"issue_events_url\":\"https://api.github.com/repos/conda/conda/issues/events{/number}\",\"events_url\":\"https://api.github.com/repos/conda/conda/events\",\"assignees_url\":\"https://api.github.com/repos/conda/conda/assignees{/user}\",\"branches_url\":\"https://api.github.com/repos/conda/conda/branches{/branch}\",\"tags_url\":\"https://api.github.com/repos/conda/conda/tags\",\"blobs_url\":\"https://api.github.com/repos/conda/conda/git/blobs{/sha}\",\"git_tags_url\":\"https://api.github.com/repos/conda/conda/git/tags{/sha}\",\"git_refs_url\":\"https://api.github.com/repos/conda/conda/git/refs{/sha}\",\"trees_url\":\"https://api.github.com/repos/conda/conda/git/trees{/sha}\",\"statuses_url\":\"https://api.github.com/repos/conda/conda/statuses/{sha}\",\"languages_url\":\"https://api.github.com/repos/conda/conda/languages\",\"stargazers_url\":\"https://api.github.com/repos/conda/conda/stargazers\",\"contributors_url\":\"https://api.github.com/repos/conda/conda/contributors\",\"subscribers_url\":\"https://api.github.com/repos/conda/conda/subscribers\",\"subscription_url\":\"https://api.github.com/repos/conda/conda/subscription\",\"commits_url\":\"https://api.github.com/repos/conda/conda/commits{/sha}\",\"git_commits_url\":\"https://api.github.com/repos/conda/conda/git/commits{/sha}\",\"comments_url\":\"https://api.github.com/repos/conda/conda/comments{/number}\",\"issue_comment_url\":\"https://api.github.com/repos/conda/conda/issues/comments{/number}\",\"contents_url\":\"https://api.github.com/repos/conda/conda/contents/{+path}\",\"compare_url\":\"https://api.github.com/repos/conda/conda/compare/{base}...{head}\",\"merges_url\":\"https://api.github.com/repos/conda/conda/merges\",\"archive_url\":\"https://api.github.com/repos/conda/conda/{archive_format}{/ref}\",\"downloads_url\":\"https://api.github.com/repos/conda/conda/downloads\",\"issues_url\":\"https://api.github.com/repos/conda/conda/issues{/number}\",\"pulls_url\":\"https://api.github.com/repos/conda/conda/pulls{/number}\",\"milestones_url\":\"https://api.github.com/repos/conda/conda/milestones{/number}\",\"notifications_url\":\"https://api.github.com/repos/conda/conda/notifications{?since,all,participating}\",\"labels_url\":\"https://api.github.com/repos/conda/conda/labels{/name}\",\"releases_url\":\"https://api.github.com/repos/conda/conda/releases{/id}\",\"deployments_url\":\"https://api.github.com/repos/conda/conda/deployments\",\"created_at\":\"2012-10-15T22:08:03Z\",\"updated_at\":\"2019-03-08T00:07:24Z\",\"pushed_at\":\"2019-03-07T21:12:25Z\",\"git_url\":\"git://github.com/conda/conda.git\",\"ssh_url\":\"git@github.com:conda/conda.git\",\"clone_url\":\"https://github.com/conda/conda.git\",\"svn_url\":\"https://github.com/conda/conda\",\"homepage\":\"https://conda.io\",\"size\":47035,\"stargazers_count\":2765,\"watchers_count\":2765,\"language\":\"Python\",\"has_issues\":true,\"has_projects\":false,\"has_downloads\":true,\"has_wiki\":true,\"has_pages\":true,\"forks_count\":691,\"mirror_url\":null,\"archived\":false,\"open_issues_count\":930,\"license\":{\"key\":\"other\",\"name\":\"Other\",\"spdx_id\":\"NOASSERTION\",\"url\":null,\"node_id\":\"MDc6TGljZW5zZTA=\"},\"forks\":691,\"open_issues\":930,\"watchers\":2765,\"default_branch\":\"master\"}},\"_links\":{\"self\":{\"href\":\"https://api.github.com/repos/conda/conda/pulls/8390\"},\"html\":{\"href\":\"https://github.com/conda/conda/pull/8390\"},\"issue\":{\"href\":\"https://api.github.com/repos/conda/conda/issues/8390\"},\"comments\":{\"href\":\"https://api.github.com/repos/conda/conda/issues/8390/comments\"},\"review_comments\":{\"href\":\"https://api.github.com/repos/conda/conda/pulls/8390/comments\"},\"review_comment\":{\"href\":\"https://api.github.com/repos/conda/conda/pulls/comments{/number}\"},\"commits\":{\"href\":\"https://api.github.com/repos/conda/conda/pulls/8390/commits\"},\"statuses\":{\"href\":\"https://api.github.com/repos/conda/conda/statuses/ae3e2a519b02694775ebaeacedcd90c4ecbf590c\"}},\"author_association\":\"CONTRIBUTOR\",\"draft\":false,\"merged\":false,\"mergeable\":null,\"rebaseable\":null,\"mergeable_state\":\"unknown\",\"merged_by\":null,\"comments\":0,\"review_comments\":0,\"maintainer_can_modify\":true,\"commits\":1,\"additions\":2,\"deletions\":0,\"changed_files\":1},\"repository\":{\"id\":6235174,\"node_id\":\"MDEwOlJlcG9zaXRvcnk2MjM1MTc0\",\"name\":\"conda\",\"full_name\":\"conda/conda\",\"private\":false,\"owner\":{\"login\":\"conda\",\"id\":6392739,\"node_id\":\"MDEyOk9yZ2FuaXphdGlvbjYzOTI3Mzk=\",\"avatar_url\":\"https://avatars0.githubusercontent.com/u/6392739?v=4\",\"gravatar_id\":\"\",\"url\":\"https://api.github.com/users/conda\",\"html_url\":\"https://github.com/conda\",\"followers_url\":\"https://api.github.com/users/conda/followers\",\"following_url\":\"https://api.github.com/users/conda/following{/other_user}\",\"gists_url\":\"https://api.github.com/users/conda/gists{/gist_id}\",\"starred_url\":\"https://api.github.com/users/conda/starred{/owner}{/repo}\",\"subscriptions_url\":\"https://api.github.com/users/conda/subscriptions\",\"organizations_url\":\"https://api.github.com/users/conda/orgs\",\"repos_url\":\"https://api.github.com/users/conda/repos\",\"events_url\":\"https://api.github.com/users/conda/events{/privacy}\",\"received_events_url\":\"https://api.github.com/users/conda/received_events\",\"type\":\"Organization\",\"site_admin\":false},\"html_url\":\"https://github.com/conda/conda\",\"description\":\"OS-agnostic, system-level binary package manager and ecosystem\",\"fork\":false,\"url\":\"https://api.github.com/repos/conda/conda\",\"forks_url\":\"https://api.github.com/repos/conda/conda/forks\",\"keys_url\":\"https://api.github.com/repos/conda/conda/keys{/key_id}\",\"collaborators_url\":\"https://api.github.com/repos/conda/conda/collaborators{/collaborator}\",\"teams_url\":\"https://api.github.com/repos/conda/conda/teams\",\"hooks_url\":\"https://api.github.com/repos/conda/conda/hooks\",\"issue_events_url\":\"https://api.github.com/repos/conda/conda/issues/events{/number}\",\"events_url\":\"https://api.github.com/repos/conda/conda/events\",\"assignees_url\":\"https://api.github.com/repos/conda/conda/assignees{/user}\",\"branches_url\":\"https://api.github.com/repos/conda/conda/branches{/branch}\",\"tags_url\":\"https://api.github.com/repos/conda/conda/tags\",\"blobs_url\":\"https://api.github.com/repos/conda/conda/git/blobs{/sha}\",\"git_tags_url\":\"https://api.github.com/repos/conda/conda/git/tags{/sha}\",\"git_refs_url\":\"https://api.github.com/repos/conda/conda/git/refs{/sha}\",\"trees_url\":\"https://api.github.com/repos/conda/conda/git/trees{/sha}\",\"statuses_url\":\"https://api.github.com/repos/conda/conda/statuses/{sha}\",\"languages_url\":\"https://api.github.com/repos/conda/conda/languages\",\"stargazers_url\":\"https://api.github.com/repos/conda/conda/stargazers\",\"contributors_url\":\"https://api.github.com/repos/conda/conda/contributors\",\"subscribers_url\":\"https://api.github.com/repos/conda/conda/subscribers\",\"subscription_url\":\"https://api.github.com/repos/conda/conda/subscription\",\"commits_url\":\"https://api.github.com/repos/conda/conda/commits{/sha}\",\"git_commits_url\":\"https://api.github.com/repos/conda/conda/git/commits{/sha}\",\"comments_url\":\"https://api.github.com/repos/conda/conda/comments{/number}\",\"issue_comment_url\":\"https://api.github.com/repos/conda/conda/issues/comments{/number}\",\"contents_url\":\"https://api.github.com/repos/conda/conda/contents/{+path}\",\"compare_url\":\"https://api.github.com/repos/conda/conda/compare/{base}...{head}\",\"merges_url\":\"https://api.github.com/repos/conda/conda/merges\",\"archive_url\":\"https://api.github.com/repos/conda/conda/{archive_format}{/ref}\",\"downloads_url\":\"https://api.github.com/repos/conda/conda/downloads\",\"issues_url\":\"https://api.github.com/repos/conda/conda/issues{/number}\",\"pulls_url\":\"https://api.github.com/repos/conda/conda/pulls{/number}\",\"milestones_url\":\"https://api.github.com/repos/conda/conda/milestones{/number}\",\"notifications_url\":\"https://api.github.com/repos/conda/conda/notifications{?since,all,participating}\",\"labels_url\":\"https://api.github.com/repos/conda/conda/labels{/name}\",\"releases_url\":\"https://api.github.com/repos/conda/conda/releases{/id}\",\"deployments_url\":\"https://api.github.com/repos/conda/conda/deployments\",\"created_at\":\"2012-10-15T22:08:03Z\",\"updated_at\":\"2019-03-08T00:07:24Z\",\"pushed_at\":\"2019-03-07T21:12:25Z\",\"git_url\":\"git://github.com/conda/conda.git\",\"ssh_url\":\"git@github.com:conda/conda.git\",\"clone_url\":\"https://github.com/conda/conda.git\",\"svn_url\":\"https://github.com/conda/conda\",\"homepage\":\"https://conda.io\",\"size\":47035,\"stargazers_count\":2765,\"watchers_count\":2765,\"language\":\"Python\",\"has_issues\":true,\"has_projects\":false,\"has_downloads\":true,\"has_wiki\":true,\"has_pages\":true,\"forks_count\":691,\"mirror_url\":null,\"archived\":false,\"open_issues_count\":930,\"license\":{\"key\":\"other\",\"name\":\"Other\",\"spdx_id\":\"NOASSERTION\",\"url\":null,\"node_id\":\"MDc6TGljZW5zZTA=\"},\"forks\":691,\"open_issues\":930,\"watchers\":2765,\"default_branch\":\"master\"},\"organization\":{\"login\":\"conda\",\"id\":6392739,\"node_id\":\"MDEyOk9yZ2FuaXphdGlvbjYzOTI3Mzk=\",\"url\":\"https://api.github.com/orgs/conda\",\"repos_url\":\"https://api.github.com/orgs/conda/repos\",\"events_url\":\"https://api.github.com/orgs/conda/events\",\"hooks_url\":\"https://api.github.com/orgs/conda/hooks\",\"issues_url\":\"https://api.github.com/orgs/conda/issues\",\"members_url\":\"https://api.github.com/orgs/conda/members{/member}\",\"public_members_url\":\"https://api.github.com/orgs/conda/public_members{/member}\",\"avatar_url\":\"https://avatars0.githubusercontent.com/u/6392739?v=4\",\"description\":\"Conda is an OS-agnostic, system-level binary package manager\"},\"sender\":{\"login\":\"soapy1\",\"id\":976973,\"node_id\":\"MDQ6VXNlcjk3Njk3Mw==\",\"avatar_url\":\"https://avatars0.githubusercontent.com/u/976973?v=4\",\"gravatar_id\":\"\",\"url\":\"https://api.github.com/users/soapy1\",\"html_url\":\"https://github.com/soapy1\",\"followers_url\":\"https://api.github.com/users/soapy1/followers\",\"following_url\":\"https://api.github.com/users/soapy1/following{/other_user}\",\"gists_url\":\"https://api.github.com/users/soapy1/gists{/gist_id}\",\"starred_url\":\"https://api.github.com/users/soapy1/starred{/owner}{/repo}\",\"subscriptions_url\":\"https://api.github.com/users/soapy1/subscriptions\",\"organizations_url\":\"https://api.github.com/users/soapy1/orgs\",\"repos_url\":\"https://api.github.com/users/soapy1/repos\",\"events_url\":\"https://api.github.com/users/soapy1/events{/privacy}\",\"received_events_url\":\"https://api.github.com/users/soapy1/received_events\",\"type\":\"User\",\"site_admin\":false}}", "isBase64Encoded": False}

    build_docs(event, '')
