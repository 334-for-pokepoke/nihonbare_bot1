import urllib.error
import urllib.request
import requests

async def dl(url, name):
    try:
        with urllib.request.urlopen(url) as web_file:
            data = web_file.read()
            with open(name, mode='wb') as local_file:
                local_file.write(data)
        return 1
    except urllib.error.URLError as e:
        print(e)
        return 0
    
async def audio_dl(url, name):
    r = requests.get(url, stream=True)
    if r.status_code == 200:
        with open(name, 'wb') as f:
            f.write(r.content)
        return 1
    else:
        return 0