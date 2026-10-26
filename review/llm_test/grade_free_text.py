import json, re, sys
p = r"D:\new papers\tls-sok\review\llm_test\free_text_grades.json"
d = json.load(open(p, encoding="utf-8"))

def grade(paper, field, ans):
    a = ans.lower()
    if field == "datasets":
        if paper.startswith("P01"):
            names = ["mta", "tranco", "dohbrw", "ucnet"]
            return "C" if all(x in a for x in names) and re.search(r"metasploit|\bms\b", a) else "P"
        if paper.startswith("P02"):
            return "C" if "mta" in a else "W"
        return "C" if ("sb-" in a or "sandbox" in a) and ("benign" in a or "research network" in a) else "P"
    if field == "model_family":
        if paper.startswith("P01"):
            return "C" if re.search(r"dtc|decision tree", a) and re.search(r"\brf\b|random forest", a) else "P"
        if paper.startswith("P02"):
            return "C" if re.search(r"none|fingerprint|edit distance|levenshtein", a) else "W"
        return "C" if re.search(r"hdbscan|cluster", a) else ("P" if a.strip('"') in ("ml",) else "W")
    if field == "first_n_packets":
        if paper.startswith("P01"):
            return "C" if "20" in a else "W"
        if paper.startswith("P02"):
            return "C" if re.search(r"none|unclear|not_applicable|\b1\b", a) else "W"
        return "C" if re.search(r"none|unclear|not_applicable|(3|three) (rrp|request)", a) else "W"
    if field == "hardware":
        return "C" if re.search(r"none|unclear|not_applicable", a) else "W"
    if field == "best_reported_score":
        if paper.startswith("P01"):
            return "C" if "100" in a and re.search(r"tpr|true positive|detection rate", a) else "P"
        if paper.startswith("P02"):
            return "C" if "0.94" in a else "W"
        return "C" if "0.993" in a else ("P" if "0.9" in a else "W")
    return "?"

n = 0
for paper, fs in d.items():
    for field, ks in fs.items():
        for k, g in ks.items():
            ks[k] = grade(paper, field, k); n += 1  # regrade everything with the current rules
json.dump(d, open(p, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("graded", n)
for paper, fs in d.items():
    for field, ks in fs.items():
        for k, g in ks.items():
            if g != "C":
                print(g, paper[:3], field, k)
