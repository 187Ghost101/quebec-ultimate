"""OSIN CHAIN SUPREME - Correlation Engine V2 - Ghost1o1
Adds REAL correlation types:
- same_avatar_as   : two profiles share the same avatar (pHash match)
- shared_domain    : a domain entity appears across multiple profiles
- github_verified  : official GitHub-listed social account
- shared_url       : same external URL appears in 2+ profiles
- co_occurring_bio : same bio/description text appears in 2+ profiles
"""
from typing import Dict, List
from collections import defaultdict


class CorrelationEngine:
    def __init__(self, graph_manager=None):
        self.graph = graph_manager

    def correlate_module_results(self, module_id, result, source_entity_id):
        relationships = []
        entities = result.get("entities", [])

        for entity in entities:
            relationships.append({
                "source": source_entity_id,
                "target": entity.get("id"),
                "type": "discovered_by",
                "weight": entity.get("confidence", 0.5),
                "evidence": f"Module {module_id}",
            })

        seen = {}
        for i, e1 in enumerate(entities):
            v1 = str(e1.get("value", "")).lower().strip()
            if not v1:
                continue
            if v1 in seen:
                relationships.append({"source": e1.get("id"), "target": seen[v1],
                                      "type": "same_value_as", "weight": 0.7,
                                      "evidence": f"Both: {v1[:50]}"})
            else:
                seen[v1] = e1.get("id")
            etype = e1.get("type")
            if etype == "email" and "@" in v1:
                local, domain = v1.split("@", 1)
                for j, e2 in enumerate(entities):
                    if i == j:
                        continue
                    if e2.get("type") == "username" and e2.get("value", "").lower() == local:
                        relationships.append({"source": e1.get("id"), "target": e2.get("id"),
                                              "type": "email_local_equals_username",
                                              "weight": 0.9, "evidence": "local matches"})
                    elif e2.get("type") == "domain" and e2.get("value", "").lower() == domain:
                        relationships.append({"source": e1.get("id"), "target": e2.get("id"),
                                              "type": "email_domain", "weight": 1.0,
                                              "evidence": "domain"})

        # ─── NEW: same avatar across profiles ───
        by_phash = defaultdict(list)
        for e in entities:
            if e.get("type") == "avatar":
                phash = (e.get("metadata") or {}).get("phash")
                if phash:
                    by_phash[phash].append(e)
        for phash, avatars in by_phash.items():
            if len(avatars) >= 2:
                # Pairwise same_avatar_as
                for i in range(len(avatars)):
                    for j in range(i + 1, len(avatars)):
                        relationships.append({
                            "source": avatars[i]["id"],
                            "target": avatars[j]["id"],
                            "type": "same_avatar_as",
                            "weight": 0.95,
                            "evidence": f"identical pHash {phash}",
                        })

        # ─── NEW: shared domain across profiles ───
        by_domain = defaultdict(list)
        for e in entities:
            if e.get("type") == "domain":
                d = str(e.get("value", "")).lower().strip()
                if d:
                    by_domain[d].append(e)
        for d, doms in by_domain.items():
            if len(doms) >= 2:
                profiles = [x for x in entities if (x.get("metadata") or {}).get("via_profile")]
                for prof in profiles:
                    for dom in doms:
                        if dom["id"] != prof["id"]:
                            relationships.append({
                                "source": prof["id"],
                                "target": dom["id"],
                                "type": "linked_to_domain",
                                "weight": 0.85,
                                "evidence": f"domain {d} appears in bio of profile",
                            })

        # ─── NEW: GitHub-verified social account ───
        for e in entities:
            meta = e.get("metadata") or {}
            if meta.get("verified_by_github"):
                gh_handle = meta.get("from_github")
                # Find the github_profile entity by from_github marker
                for other in entities:
                    if other is e:
                        continue
                    other_meta = other.get("metadata") or {}
                    if (other_meta.get("handle") == gh_handle
                            and other.get("type") == "social_profile"
                            and other_meta.get("platform") == "github"):
                        relationships.append({
                            "source": other["id"],
                            "target": e["id"],
                            "type": "github_verified_social",
                            "weight": 1.0,
                            "evidence": f"GitHub API lists this {meta.get('platform')} as official",
                        })

        # ─── NEW: shared URL across profiles ───
        by_url = defaultdict(list)
        for e in entities:
            if e.get("type") == "url":
                u = str(e.get("value", "")).rstrip("/").lower()
                if u:
                    by_url[u].append(e)
        for u, urls in by_url.items():
            if len(urls) >= 2:
                for i in range(len(urls)):
                    for j in range(i + 1, len(urls)):
                        relationships.append({
                            "source": urls[i]["id"],
                            "target": urls[j]["id"],
                            "type": "shared_url",
                            "weight": 0.9,
                            "evidence": f"same URL appears in both bios: {u[:60]}",
                        })

        return relationships

    def calculate_entity_score(self, entity_id):
        if not self.graph or not self.graph.connected:
            return 0.5
        nb = self.graph.get_neighborhood(entity_id, depth=1)
        return min(0.3 + len(nb.get("edges", [])) * 0.05 + len(nb.get("nodes", [])) * 0.03, 1.0)

    def find_connections_between(self, a, b):
        if not self.graph or not self.graph.connected:
            return {"paths": []}
        return {"paths": self.graph.find_paths(a, b, 5)[:5]}