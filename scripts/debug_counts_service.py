from supabase import create_client
from dotenv import load_dotenv
import os

load_dotenv()
SUPABASE_URL = os.getenv('SUPABASE_URL')
SERVICE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
client = create_client(SUPABASE_URL, SERVICE_KEY)
res = client.table('startup_knowledge').select('domain,count:id', count='exact').execute()
print('table select error:', getattr(res,'error',None))
# get counts per domain via SQL
sql = "select domain, count(*) as n from startup_knowledge group by domain order by n desc limit 50;"
res2 = client.rpc('sql', {'q': sql}).execute() if hasattr(client, 'rpc') else None
# fallback: use POST /rest/v1 RPC isn't standard; instead run query via client.postgrest
if res2 is None:
    from postgrest import Postgrest
    # try using client.table with filter to list some domains
    res2 = client.table('startup_knowledge').select('domain').limit(1000).execute()
    domains = [r['domain'] for r in getattr(res2,'data',[]) if r.get('domain')]
    from collections import Counter
    print('domain counts (sampled):')
    for k,v in Counter(domains).most_common(20):
        print(k, v)
else:
    print('sql res2 error:', getattr(res2,'error',None))
    print('sql res2 data len:', len(getattr(res2,'data',[]) or []))
    for r in getattr(res2,'data',[]):
        print(r)
print('\nDone')
