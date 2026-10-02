"""Call this exact private Site's MCP using platform service access from stdin."""
import json
import sys
import urllib.request
import urllib.error

ORIGIN = 'https://leo-x-daily.howailok1120jp2.chatgpt.site'

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def main():
    settings = None
    if sys.stdin.isatty():
        import termios
        settings = termios.tcgetattr(sys.stdin.fileno())
        hidden = termios.tcgetattr(sys.stdin.fileno())
        hidden[3] &= ~termios.ECHO
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, hidden)
    print('Ready for service request JSON on stdin (input is hidden).', flush=True)
    try:
        value = json.loads(sys.stdin.readline())
    finally:
        if settings is not None:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, settings)
    if value.get('origin') != ORIGIN or not isinstance(value.get('token'), str) or not value['token']:
        raise ValueError('invalid_service_access')
    operation = value.get('operation', 'mcp')
    if operation == 'status':
        path, method, payload = '/api/status', 'GET', None
    elif operation == 'instructions':
        path, method, payload = '/api/instructions', 'GET', None
    elif operation == 'publish':
        if 'publication_file' in value:
            from pathlib import Path
            publication = json.loads(Path(value['publication_file']).read_text())
        else:
            publication = value['publication']
        path, method, payload = '/api/publish', 'POST', publication
    elif operation == 'read':
        import re
        key = value['key']
        if not re.fullmatch(r'x-digest-\d{4}-\d{2}-\d{2}-v\d+', key):
            raise ValueError('invalid_edition_key')
        path, method, payload = '/editions/' + key + '.md', 'GET', None
    elif operation == 'mcp':
        path, method, payload = '/mcp', 'POST', {'jsonrpc':'2.0','id':1,'method':value['method'],'params':value.get('params',{})}
    else:
        raise ValueError('invalid_service_operation')
    encoded = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
    request = urllib.request.Request(ORIGIN + path, data=encoded, headers={'Content-Type':'application/json','Accept':'application/json, text/plain','OAI-Sites-Authorization':'Bearer '+value['token']}, method=method)
    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(request, timeout=25) as response:
            if operation == 'read' and 'text/plain' in response.headers.get('Content-Type',''):
                result = {'key':value['key'], 'markdown':response.read().decode('utf-8')}
            elif 'application/json' in response.headers.get('Content-Type',''):
                result=json.load(response)
            else:
                raise ValueError('unexpected_response_type')
    except urllib.error.HTTPError as error:
        print(json.dumps({'ok':False,'error':'http_'+str(error.code)}));return 2
    except urllib.error.URLError:
        print(json.dumps({'ok':False,'error':'service_network_unavailable'}));return 2
    print(json.dumps(result,ensure_ascii=False))
    return 0 if 'error' not in result and not result.get('result',{}).get('isError') else 2

if __name__ == '__main__':
    try: raise SystemExit(main())
    except (ValueError,KeyError):
        print(json.dumps({'ok':False,'error':'invalid_service_request_or_response'}));raise SystemExit(2)
