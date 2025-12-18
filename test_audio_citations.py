"""
Test the full analyze_legal_case pipeline to check if audio sources 
appear in the sources list and get injected into citations.
"""
from rag_answer import analyze_legal_case

# Simulate metadata from UI
metadata = {
    "matterOverview": "Potential discrimination and workplace misconduct involving Indian workers.",
    "peopleAndAliases": "William Davis, Francis Ham",
    "noteworthyOrganizations": "",
    "noteworthyTerms": "",
    "additionalContext": ""
}

filenames = ["aiRwilliam.mp3", "aiRfrancis.mp3"]

print("=" * 80)
print("Testing analyze_legal_case with audio files")
print("=" * 80)

result = analyze_legal_case(metadata, filenames, top_k=100)

print("\n=== SOURCES LIST ===")
for s in result.get("sources", [])[:10]:
    print(f"  {s['file']} (score: {s['score']:.4f})")

print("\n=== CHECKING FOR AUDIO IN SOURCES ===")
audio_in_sources = [s for s in result.get("sources", []) 
                    if s['file'].endswith('.mp3') or s['file'].endswith('.wav')]
if audio_in_sources:
    print(f"✅ Found {len(audio_in_sources)} audio sources:")
    for a in audio_in_sources:
        print(f"   - {a['file']} (score: {a['score']:.4f})")
else:
    print("❌ NO AUDIO SOURCES in sources list!")
    print("   This means audio chunks are not being retrieved.")

print("\n=== FIRST 3 ISSUES WITH CITATIONS ===")
for issue in result.get("issues", [])[:3]:
    print(f"\nIssue: {issue.get('title', 'N/A')}")
    print(f"  Citations: {issue.get('citations', 'NONE')}")
    
    # Check if audio appears
    citations = issue.get("citations", "")
    has_audio = any(ext in citations for ext in ['.mp3', '.wav', '.m4a'])
    if has_audio:
        print("  ✅ Audio source found in citations!")
    else:
        print("  ❌ Audio source NOT in citations")

print("\n" + "=" * 80)
