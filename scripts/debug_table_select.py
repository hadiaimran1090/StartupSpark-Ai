from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY')
client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
res = client.table('startup_knowledge').select('id,domain,title').limit(3).execute()
print('error:', getattr(res,'error',None))
print('len:', len(getattr(res,'data',[]) or []))
print('sample:', getattr(res,'data',None))
