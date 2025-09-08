"""
Generate synthetic user preference personas tailored to your fragrance dataset.

Outputs:
- data/processed/personas.parquet  (table)
- data/processed/personas.jsonl    (raw line-delimited JSON for inspection)"""
import os, json, math, time, argparse
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv

import pandas as pd

from openai import OpenAI

load_dotenv()

# Constants
API_KEY = os.getenv("OPENAI_API_KEY")
ART = Path('../../data/processed')
GENDER_CHOICES = ['men','women','unisex','any']
SEASON_CHOICES = ['spring','summer','fall','winter','all']
USE_CASE_CHOICES = ['office','date','gym','casual','formal','signature']
INTENSITY_CHOICES = ['soft','moderate','loud']

def load_vocab() -> Dict[str, List[str]]:
    meta = json.loads((ART/'feature_meta.json').read_text())
    # use full vocab without downsampling
    return {
        "feature_meta": meta,
        "accords": list(dict.fromkeys([s.strip().lower() for s in meta["accord_vocab"]])),
        "top":     list(dict.fromkeys([s.strip().lower() for s in meta["top_mlb_classes"]])),
        "mid":     list(dict.fromkeys([s.strip().lower() for s in meta["mid_mlb_classes"]])),
        "base":    list(dict.fromkeys([s.strip().lower() for s in meta["base_mlb_classes"]])),
    }

def make_persona_prompt(n_personas: int, vocab: Dict[str, List[str]]) -> str:
    """Strict, short prompt that forces choices from your vocab only."""
    return f"""
Return ONLY valid JSON: an array of {n_personas} persona objects.
Each persona strictly follows this schema (all strings lowercase):

{{
  "liked_accords_ranked": [
    {{"name": str, "rank": 1}},
    {{"name": str, "rank": 2}},
    {{"name": str, "rank": 3}},
    {{"name": str, "rank": 4}},
    {{"name": str, "rank": 5}}
  ],
  "disliked_accords":  [0-3 items from ALLOWED_ACCORDS, no overlap with liked_accords],
  "liked_notes_top":   [5-10 items from ALLOWED_TOP],
  "liked_notes_mid":   [5-10 items from ALLOWED_MID],
  "liked_notes_base":  [5-10 items from ALLOWED_BASE],
  "avoid_notes":       [0-5 items from the union of ALLOWED_TOP/MID/BASE, no overlap with liked notes],
  "gender_focus":      one of {GENDER_CHOICES},
  "season":            one of {SEASON_CHOICES},
  "use_case":          one of {USE_CASE_CHOICES},
  "intensity":         one of {INTENSITY_CHOICES}
}}

Constraints:
- liked_accords_ranked MUST have exactly 5 entries, with unique accords and unique ranks 1–5.
- Ranks must be consecutive integers from 1 through 5.
- Accord "name" must come from ALLOWED_ACCORDS only.
- Use_case must be a single choice, not a list.
- Do NOT invent values outside the allowed lists.

Coherence hints:
- summer → emphasize citrus/aromatic/green/aquatic; winter → amber/woody/sweet/balsamic ok.
- men → woody/aromatic/spicy bias; women → floral/fruity/sweet; unisex → balanced.

ALLOWED_ACCORDS = {vocab['accords']}
ALLOWED_TOP     = {vocab['top']}
ALLOWED_MID     = {vocab['mid']}
ALLOWED_BASE    = {vocab['base']}
"""

def _norm_list(xs):
    seen, out = set(), []
    for x in xs or []:
        s = str(x).strip().lower()
        if s and s not in seen:
            seen.add(s); out.append(s)
    return out

def validate(p: Dict[str, Any], v: Dict[str,List[str]]) -> Dict[str,Any]:
    accords = set(v['accords']); top=set(v['top']); mid = set(v['mid']); base = set(v['base'])
    all_notes = top|mid|base

    p['liked_accords_ranked'] = [{"name": a['name'], "rank": i + 1} for i, a in
                                 enumerate(list(p.get('liked_accords_ranked', []))) if a['name'] in accords][:5]
    p['disliked_accords'] = [a for a in list(p.get('disliked_accords', [])) if
                             a in accords and a not in [item['name'] for item in p['liked_accords_ranked']]][:3]
    p["liked_notes_top"]  = [n for n in _norm_list(p.get("liked_notes_top", []))  if n in top][:10]
    p["liked_notes_mid"]  = [n for n in _norm_list(p.get("liked_notes_mid", []))  if n in mid][:10]
    p["liked_notes_base"] = [n for n in _norm_list(p.get("liked_notes_base", [])) if n in base][:10]

    avoid = [n for n in _norm_list(p.get('avoid_notes',[])) if (n in all_notes
                                                                and n not in p['liked_notes_top']
                                                                and n not in p['liked_notes_mid']
                                                                and n not in p['liked_notes_base'])]
    p['avoid_notes'] = avoid[:5]

    p['gender_focus'] = (p.get('gender_focus','any')or 'any').lower()
    if p['gender_focus'] not in GENDER_CHOICES: p['gender_focus']='any'
    p["season"] = (p.get("season", "all") or "all").lower()
    if p["season"] not in SEASON_CHOICES: p["season"] = "all"
    p["use_case"] = (p.get('use_case','casual') or 'casual').lower()
    if p['use_case'] not in USE_CASE_CHOICES: p['use_case'] = 'casual'
    p["intensity"] = (p.get("intensity", "moderate") or "moderate").lower()
    if p["intensity"] not in INTENSITY_CHOICES: p["intensity"] = "moderate"

    if len(p['liked_accords_ranked']) < 3:
        for a in ['woody', 'citrus', 'aromatic', 'floral', 'amber']:
            if a in accords and a not in [item['name'] for item in p['liked_accords_ranked']]:
                current_rank = len(p['liked_accords_ranked']) + 1
                p['liked_accords_ranked'].append({"name": a, "rank": current_rank})
            if len(p['liked_accords_ranked']) >= 5: break

    if not (p["liked_notes_top"] or p["liked_notes_mid"] or p["liked_notes_base"]):
        p["liked_notes_top"]  = list(top)[:5]
        p["liked_notes_mid"]  = list(mid)[:5]
        p["liked_notes_base"] = list(base)[:5]
    return p

def ask_openai(n_personas: int, prompt:str, model='gpt-4o-mini',temperature=0.4) -> List[Dict[str, Any]]:
    client = OpenAI(api_key=API_KEY)
    resp = client.chat.completions.create(
        model=model, messages=[{'role':'user','content':prompt}],
        temperature=temperature, response_format={'type':'json_object'}
    )
    obj = json.loads(resp.choices[0].message.content)
    if isinstance(obj,dict):
        for v in obj.values():
            if isinstance(v,list): return v
    raise ValueError("Invalid JSON structure in model response.")

def generate(n_total=100, batch_size=25, sleep_s=0.5,model='gpt-4o-mini',temperature=0.4):
    v = load_vocab()
    out = []
    n_batches = math.ceil(n_total/batch_size)
    for b in range(n_batches):
        n_this = batch_size if b < n_batches-1 else n_total-batch_size*(n_batches-1)
        prompt = make_persona_prompt(n_this,v)
        raw = ask_openai(n_this,prompt,model=model,temperature=temperature)
        out.extend(validate(p,v) for p in raw)
        time.sleep(sleep_s)
    return out[:n_total]

def save(personas: List[Dict[str,Any]],prefix='personas'):
    ART.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(personas).to_parquet(ART/f"{prefix}.parquet",index=False)
    with (ART/f'{prefix}.jsonl').open("w",encoding='utf-8') as f:
        for p in personas:
            f.write(json.dumps(p,ensure_ascii=False) + '\n')
    print(f"Saved -> {ART/f'{prefix}.parquet'} and {ART/f"{prefix}.jsonl"}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n",type=int,default=100,help='Total personas (50-100 recommended).')
    ap.add_argument("--batch",type=int,default=25,help='Batch Size per API call.')
    ap.add_argument("--model",type=str,default='gpt-4o-mini')
    ap.add_argument("--temp",type=float,default=0.4)
    ap.add_argument("--prefix",type=str,default='personas_fullmeta')
    args = ap.parse_args()

    if not API_KEY:
        raise SystemExit("Please set OPENAI_API_KEY")

    personas = generate(n_total=args.n, batch_size=args.batch, model=args.model,temperature=args.temp)
    print(f"Generated personas: {len(personas)}")
    save(personas,prefix=args.prefix)

if __name__ == '__main__':
    main()


