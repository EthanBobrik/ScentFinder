"""
explanations.py
---------------
OpenAI API LLM powered explanations for fragrance explanations.
"""
from __future__ import annotations
import os
from typing import Dict, List, Any
from dotenv import load_dotenv
import pandas as pd
from openai import OpenAI

load_dotenv()

DEFAULT_MODEL = 'gpt-4o-mini'
API_KEY = os.getenv("OPENAI_API_KEY")
TEMPERATURE = 0.2
BATCH_SIZE = 8

client = OpenAI(api_key=API_KEY)

def prompt(item_row: Dict[str, Any], preference: Dict[str, Any]) -> str:
    """
    Compact, deterministic prompt from your existing dataframe fields.
    Expects df to contain:
      Brand, Perfume, Year, Gender,
      mainaccord1..5, why_accords_overlap, sample_notes,
      score_content, score_persona, score_fused
    """
    brand = str(item_row.get("Brand",'')).strip()
    perfume = str(item_row.get("Perfume",'')).strip()
    year = item_row.get("Year",'')
    gender = str(item_row.get("Gender",'')).strip()

    accs = [item_row.get(f'mainaccord{i}','') for i in range(1,6)]
    accs = [a for a in accs if isinstance(a,str) and a.strip()]
    overlap = item_row.get('why_accords_overlap','') or 'none'
    notes = item_row.get('sample_notes','') or 'n/a'

    sc = float(item_row.get('score_content',0.0))
    sp = float(item_row.get('score_persona',0.0))
    sf = float(item_row.get('score_fused',0.0))

    season = str(preference.get('season','any')).lower()
    use_case = str(preference.get('use_case','any')).lower()
    intensity = str(preference.get('intensity','moderate')).lower()
    gender_pref = str(preference.get('gender_focus','any')).lower()

    return (
        "You are a fragrance expert. Explain why this perfume was recommended using the signals provided.\n"
        "Write 1 short sentence + exactly 3 concise bullet points. Avoid hype; be specific. Keep under 70 words total.\n"
        "If accord overlap exists, mention it first. Use season/use-case/intensity only if helpful.\n"
        f"USER CONTEXT: season={season}, use_case={use_case}, intensity={intensity}, gender_focus={gender_pref}\n"
        "ITEM:\n"
        f"- name: {perfume}\n"
        f"- brand: {brand}\n"
        f"- year: {year}\n"
        f"- gender: {gender}\n"
        f"- accords: {', '.join(accs)}\n"
        f"- accord_overlap_with_user: {overlap}\n"
        f"- sample_notes: {notes}\n"
        f"- scores: content={sc:.3f}, persona={sp:.3f}, fused={sf:.3f}\n"
        "OUTPUT FORMAT:\n"
        "Sentence on one line, then exactly 3 bullets starting with '- '."
    )

def generate(df: pd.DataFrame, preference: Dict[str, Any], model: str = DEFAULT_MODEL, batch_size: int = BATCH_SIZE, temperature: float = TEMPERATURE) -> List[str]:
    "Returns a list of explanations aligned with df rows. Fails soft per-row (keeps your recommender fully functional)"
    prompts = [prompt(r.asdict() if hasattr(r,'_asdict') else r.to_dict(), preference) for _,r in df.iterrows()]
    out = [''] * len(prompts)
    for start in range(0,len(prompts), batch_size):
        for i in range(start, min(start + batch_size, len(prompts))):
            try:
                resp = client.chat.completions.create(
                    model = model,
                    messages=[{"role": "user", "content": prompts[i]}],
                    temperature=temperature,
                )
                out[i] = resp.choices[0].message.content.strip()
            except Exception as e:
                out[i] = f"(explanation unavailable: {e})"
    return out

def attach_llm_explanations(df: pd.DataFrame, preference: Dict[str, Any], model:str = DEFAULT_MODEL, column_name: str = 'explanation_llm', **gen_kwargs) -> pd.DataFrame:
    """
    Adds a new column with LLM explanations to a copy of df and returns it. Does nothing is df is empty.
    """
    if df is None or df.empty:
        return df
    expl = generate(df, preference, model=model, **gen_kwargs)
    df_out = df.copy()
    df_out[column_name] = expl
    return df_out