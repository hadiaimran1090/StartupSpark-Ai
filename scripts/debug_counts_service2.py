from dotenv import load_dotenv
from supabase import create_client
import os
load_dotenv()
SUPABASE_URL=os.getenv('SUPABASE_URL')
SERVICE_KEY=os.getenv('SUPABASE_SERVICE_ROLE_KEY')
client=create_client(SUPABASE_URL,SERVICE_KEY)
res2=client.table('startup_knowledge').select('domain').limit(10000).execute()
print('sample len:', len(getattr(res2,'data',[]) or []))
domains=[r.get('domain') for r in getattr(res2,'data',[]) if r.get('domain')]
from collections import Counter
for k,v in Counter(domains).most_common(50):
    print(k,v)
print('\nHave agritech?', 'agritech' in set(domains))
