"""OSIN CHAIN SUPREME - Correlation Engine - Ghost1o1"""
from typing import Dict, List

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
