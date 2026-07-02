create extension if not exists vector;
create extension if not exists pgcrypto;

create table if not exists startup_knowledge (
    id uuid primary key default gen_random_uuid(),
    domain text not null,
    source text,
    title text,
    content text not null,
    metadata jsonb default '{}'::jsonb,
    embedding vector(768) not null,
    created_at timestamptz default now()
);

create index if not exists startup_knowledge_domain_idx
on startup_knowledge(domain);

create index if not exists startup_knowledge_metadata_gin_idx
on startup_knowledge using gin(metadata);

create index if not exists startup_knowledge_embedding_idx
on startup_knowledge
using ivfflat (embedding vector_cosine_ops)
with (lists = 100);

create or replace function match_startup_knowledge (
    query_embedding float8[],
    query_domain text,
    match_count int default 5
)
returns table (
    id uuid,
    domain text,
    title text,
    content text,
    metadata jsonb,
    similarity float
)
language sql
stable
security definer
as $$
select
    k.id,
    k.domain,
    k.title,
    k.content,
    k.metadata,
    1 - (k.embedding <=> (query_embedding::vector)) as similarity
from startup_knowledge k
where k.domain = query_domain
order by k.embedding <=> (query_embedding::vector)
limit match_count;
$$;