---
tags:
  - data-retrieval
  - semantic-embeddings
  - search-optimization
  - chunk-size-debate
  - information-representation
---

[Please Stop Arguing About Chunk Size — You’re Searching on the Wrong Surface](https://www.reddit.com/r/Rag/comments/1oyrxcy/please_stop_arguing_about_chunk_size_youre/)

Shared in r/Rag

•

by Popular_Sand2773 / Nov 16, 2025 at 4:28 PM

**Tldr: search surface <> return surface. Stop beating the horse you shot.**

Before you burn me at the stake just hear me out and I promise your top-1 and top-5 retrieval accuracy will jump by like 10%.

I’ve noticed a common failure pattern here where people are confusing chunks for the data they are returning. This is a problem because often the data you want to return and the chunk you want to search against are not the same thing.

_How can that be? Isn’t my chunk the best representation of itself?_ It is. But search isn’t about being true to yourself it’s about telling two schmucks apart.

_So how do we do that?_ Well most of us are using semantic embeddings. Here is the thing about semantic embeddings they aren’t good at knowing what is and isn’t important. Everything is tokens and all tokens are roughly equal. So when we have a big fat noisy chunk we drown out our search signal with unhelpful tokens. Now if you are thinking easy smaller chunks then you’ve missed the point. It’s not about the size it’s about the signal to noise ratio. A small chunk can be just as noisy as a big one.

Here's the straightforward math for why that is true:  
E_sentence = average(all_token_embeddings)

That's not a size issue - It's a signal issue!

_So what can I do right now with minimal effort to make your life easier?_ Beyond take a bath you can decouple what you embed for search and what you return after said search. The laziest version of this would be to prune chunks for stop-words before embedding.

See the core issue for most rag systems isn’t telling A from B it’s telling AB from BA. It’s the near neighbors. When we decouple our search surface from our return surface this becomes much easier because we can optimize both for their central task.

Retrieval Surface: What is the highest signal representation of the information I want to return that makes it truly distinct.

Return Surface: What information does my downstream system need to succeed.

Often the former wants to be sparse and the latter rich. That’s what causes the constant conflict and endless debates. Once you decouple them this goes away.

**Don’t believe me let me show you how:**

Let's take 5 snippets we might want to return:

```
from sentence_transformers import SentenceTransformer
import numpy as np
import pandas as pd


# ----- Query -----
query = "Where is the analytics warehouse located for EU healthcare customers with patients?"


# ----- 5 big, noisy chunks (return surface) -----
chunks_full = [
    # 1
    """
    Our analytics platform assigns customers to the nearest regional warehouse by default.
    Most EU enterprise tenants, including a mix of retail, finance, and healthcare accounts,
    are routed through our shared cluster in eu-west-1 (Dublin, Ireland) for latency and cost.
    All customers share the same logical schema, catalog, and retention defaults regardless
    of industry. Healthcare-specific settings are applied through policy templates, not
    separate infrastructure.
    """,
    # 2
    """
    For customers operating in highly regulated environments such as EU finance, public
    sector, and life sciences, we provide an advanced compliance tier. This tier uses
    encrypted analytics warehouses in eu-north-1 (Stockholm) with additional audit logging,
    key management controls, and region pinning. Many healthcare organizations choose this
    tier for research workloads, but transactional analytics often remains in the standard
    EU cluster in eu-west-1.
    """,
    # 3 (TARGET)
    """
    EU healthcare tenants that process identifiable patient records are provisioned on a
    dedicated compliance footprint. For these customers, all analytics warehouse tables,
    raw event streams, and derived aggregates are stored exclusively in Frankfurt
    (eu-central-1, Germany). Cross-region replication is disabled by default, and exports
    outside the EU require an explicit data processing agreement and sign-off from the
    customer’s data protection officer.
    """,
    # 4
    """
    To support disaster recovery and business continuity, customers may enable multi-region
    mirroring of their analytics warehouse. Replicas are usually distributed across
    eu-west-1 (Dublin), eu-north-1 (Stockholm), and occasionally eu-central-1 (Frankfurt)
    depending on capacity and failover plans. These mirrors are warm standbys and are not
    exposed as primary endpoints for any specific industry segment, including healthcare.
    """,
    # 5
    """
    Historical analytics data older than three years can be offloaded to our cold-storage
    layer. For most EU customers, these archives are stored across a blend of eu-west-1,
    eu-north-1, and eu-central-1 regions, optimized for cost rather than strict residency.
    Healthcare organizations sometimes enable this option for anonymized aggregates, while
    keeping live patient-related analytics in their primary warehouse region.
    """
]


# ----- 5 one-sentence summaries (search surface) -----
chunks_search = [
    # summary for 1
    "Most EU customers with a mix of retail, finance and healthcare accounts are routed through our shared cluster in eu-west-1 (Dublin).",
    # summary for 2
    "Regulated EU customers can use a compliance tier with encrypted analytics warehouses in eu-north-1 (Stockholm).",
    # summary for 3 (TARGET)
    "EU healthcare customers with patient data store all analytics warehouse tables exclusively in Frankfurt (eu-central-1).",
    # summary for 4
    "Multi-region mirroring keeps standby analytics replicas across eu-west-1, eu-north-1, and sometimes eu-central-1 for failover.",
    # summary for 5
    "Old EU analytics data is archived across mixed regions, balancing cost with flexible residency for anonymized workloads."
]


# Sanity check lengths
assert len(chunks_full) == len(chunks_search) == 5


# ----- Model -----
# Swap to a different MiniLM variant if you prefer; this one is widely available.
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


# ----- Embeddings -----
q_emb = model.encode([query], convert_to_tensor=True, normalize_embeddings=True)


full_embs   = model.encode(chunks_full,   convert_to_tensor=True, normalize_embeddings=True)
sum_embs  = model.encode(chunks_search, convert_to_tensor=True, normalize_embeddings=True)


# Cosine similarities
full_sims  = (full_embs  @ q_emb.T).cpu().numpy().reshape(-1)
sum_sims = (sum_embs @ q_emb.T).cpu().numpy().reshape(-1)


# ----- Ranking helpers -----
def rank_order(scores):
    return np.argsort(-scores)


def rank_of(idx, order):
    return int(np.where(order == idx)[0][0]) + 1  # 1-based rank


full_order  = rank_order(full_sims)
sum_order = rank_order(sum_sims)


rows = []
for i in range(len(chunks_long)):
    rows.append({
        "chunk_id": i + 1,
        "full_sim":  float(full_sims[i]),
        "full_rank": rank_of(i, full_order),
        "sum_sim": float(sum_sims[i]),
        "sum_rank": rank_of(i, sum_order),
    })


df = pd.DataFrame(rows).sort_values("chunk_id")
df.reset_index(drop=True, inplace=True)
df
```

The result:

|**chunk_id**|full_sim|full_rank|sum_sim|sum_rank|
|---|---|---|---|---|
|1|0.741523|1|0.546663|2|
|2|0.616339|3|0.543201|3|
|3|0.672394|2|0.712960|1|
|4|0.547212|5|0.330635|5|
|5|0.609820|4|0.494625|4|

*Disclaimer: I had ChatGPT write the boilerplate code because it’s 2025 and typing it by hand is cosplay.

There are two things to note here:

1. Our target chunk moved from 2 to 1 like we wanted.
    
2. The range of similarity scores drastically increased from .1943 to .3823. This is the most critical piece because it shows that by modifying the search surface we increased our ability to tell records apart!
    

**If you only can remember one damn thing:**

The next time you find yourself asking what is the perfect chunk size please instead think what signal do I need to tell my records apart. And for the love of god stop chunking the whole damn thing.