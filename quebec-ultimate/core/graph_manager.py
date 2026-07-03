"""OSIN CHAIN SUPREME - Graph Manager (Neo4j + NetworkX fallback) - Ghost1o1"""
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from abc import ABC, abstractmethod
from config import config, has_neo4j
from core.logger import logger

class GraphBackend(ABC):
    connected = False
    @abstractmethod
    def create_entity(self, *a, **k): ...
    @abstractmethod
    def create_relationship(self, *a, **k): ...
    @abstractmethod
    def get_entity(self, eid): ...
    @abstractmethod
    def get_neighborhood(self, eid, depth=2): ...
    @abstractmethod
    def search_entities(self, q, limit=20): ...
    @abstractmethod
    def get_graph_stats(self): ...
    @abstractmethod
    def find_paths(self, s, t, m): ...
    @abstractmethod
    def full_export(self): ...
    @abstractmethod
    def clear_session_data(self, sid): ...
    @abstractmethod
    def disconnect(self): ...

class NetworkXGraphManager(GraphBackend):
    def __init__(self):
        import networkx as nx
        self.nx = nx; self.graph = nx.MultiDiGraph(); self.entities = {}
        self.persist_file = config.DATA_DIR / "graph_state.json"
        self.connected = True; self._load()
        logger.info("[Graph] NetworkX backend ready")

    def _load(self):
        if self.persist_file.exists():
            try:
                with open(self.persist_file) as f: st = json.load(f)
                for eid, ed in st.get("entities", {}).items():
                    self.entities[eid] = ed; self.graph.add_node(eid, **ed)
                for r in st.get("relations", []):
                    self.graph.add_edge(r["source"], r["target"], type=r["type"],
                                        weight=r["weight"], evidence=r.get("evidence",""))
                logger.info(f"[Graph] Loaded {len(self.entities)} entities")
            except Exception as e: logger.warning(f"[Graph] Load fail: {e}")

    def _save(self):
        try:
            st = {"entities": self.entities,
                  "relations": [{"source":u,"target":v,"type":d.get("type",""),
                                 "weight":d.get("weight",1.0),"evidence":d.get("evidence","")}
                                for u,v,d in self.graph.edges(data=True)],
                  "saved_at": datetime.utcnow().isoformat()}
            with open(self.persist_file, "w", encoding="utf-8") as f:
                json.dump(st, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e: logger.warning(f"[Graph] Save fail: {e}")

    def create_entity(self, entity_id, entity_type, value, source, confidence, metadata):
        if entity_id in self.entities: return False
        d = {"id":entity_id,"type":entity_type,"value":str(value),"source":source,
             "confidence":confidence,"metadata":metadata or {},
             "created_at": datetime.utcnow().isoformat()}
        self.entities[entity_id] = d; self.graph.add_node(entity_id, **d); self._save(); return True

    def create_relationship(self, source_id, target_id, rel_type, weight, evidence):
        if source_id not in self.entities or target_id not in self.entities: return False
        self.graph.add_edge(source_id, target_id, type=rel_type, weight=weight, evidence=evidence)
        self._save(); return True

    def get_entity(self, eid): return self.entities.get(eid)

    def get_neighborhood(self, eid, depth=2):
        if eid not in self.entities: return {"nodes":[], "edges":[]}
        vis = {eid}; front = {eid}; edges = []
        for _ in range(depth):
            nf = set()
            for n in front:
                for _, t, d in self.graph.out_edges(n, data=True):
                    if t not in vis: vis.add(t); nf.add(t)
                    edges.append({"source":n,"target":t,**d})
                for s, _, d in self.graph.in_edges(n, data=True):
                    if s not in vis: vis.add(s); nf.add(s)
                    edges.append({"source":s,"target":n,**d})
            front = nf
        return {"nodes":[self.entities[n] for n in vis if n in self.entities], "edges":edges}

    def search_entities(self, q, limit=20):
        ql = q.lower(); out = []
        for e in self.entities.values():
            if ql in str(e.get("value","")).lower() or ql in str(e.get("type","")).lower():
                out.append(e)
                if len(out) >= limit: break
        return out

    def get_graph_stats(self):
        tc = {}
        for e in self.entities.values():
            t = e.get("type","unknown"); tc[t] = tc.get(t,0)+1
        return {"total_entities":len(self.entities),"total_relationships":self.graph.number_of_edges(),
                "entities_by_type":[{"type":t,"count":c} for t,c in sorted(tc.items(),key=lambda x:-x[1])],
                "backend":"NetworkX"}

    def find_paths(self, s, t, m=5):
        if s not in self.entities or t not in self.entities: return []
        try: return list(self.nx.all_simple_paths(self.graph, s, t, cutoff=m))[:10]
        except Exception: return []

    def full_export(self):
        return {"nodes":list(self.entities.values()),
                "edges":[{"source":u,"target":v,**d} for u,v,d in self.graph.edges(data=True)]}

    def clear_session_data(self, sid):
        rm = [eid for eid,e in self.entities.items() if e.get("metadata",{}).get("session")==sid]
        for eid in rm:
            if eid in self.entities: del self.entities[eid]
            if self.graph.has_node(eid): self.graph.remove_node(eid)
        self._save(); return len(rm)

    def disconnect(self): self._save()

class Neo4jGraphManager(GraphBackend):
    def __init__(self):
        from neo4j import GraphDatabase
        self.driver = GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD))
        self.driver.verify_connectivity(); self.connected = True
        with self.driver.session() as s:
            s.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE")
        logger.info(f"[Graph] Neo4j connected: {config.NEO4J_URI}")

    def create_entity(self, entity_id, entity_type, value, source, confidence, metadata):
        with self.driver.session() as s:
            s.run("MERGE (n:Entity {id:$id}) SET n.type=$type, n.value=$value, n.source=$source, "
                  "n.confidence=$conf, n.metadata=$meta, n.created_at=datetime()",
                  id=entity_id, type=entity_type, value=str(value), source=source,
                  conf=confidence, meta=json.dumps(metadata or {}))
        return True

    def create_relationship(self, source_id, target_id, rel_type, weight, evidence):
        with self.driver.session() as s:
            s.run("MATCH (a:Entity {id:$s}), (b:Entity {id:$t}) MERGE (a)-[r:REL {type:$rt}]->(b) "
                  "SET r.weight=$w, r.evidence=$ev",
                  s=source_id, t=target_id, rt=rel_type, w=weight, ev=evidence)
        return True

    def get_entity(self, eid):
        with self.driver.session() as s:
            r = s.run("MATCH (n:Entity {id:$id}) RETURN n", id=eid).single()
            return dict(r["n"]) if r else None

    def get_neighborhood(self, eid, depth=2):
        with self.driver.session() as s:
            r = s.run(f"MATCH (n:Entity {{id:$id}})-[*1..{depth}]-(m:Entity) "
                      "RETURN DISTINCT m LIMIT 200", id=eid)
            nodes = {}; edges = []
            for rec in r:
                m = dict(rec["m"]); nodes[m["id"]] = m
            root = self.get_entity(eid)
            if root: nodes[eid] = root
            return {"nodes": list(nodes.values()), "edges": edges}

    def search_entities(self, q, limit=20):
        with self.driver.session() as s:
            r = s.run("MATCH (n:Entity) WHERE toLower(n.value) CONTAINS toLower($q) "
                      "RETURN n LIMIT $l", q=q, l=limit)
            return [dict(rec["n"]) for rec in r]

    def get_graph_stats(self):
        with self.driver.session() as s:
            rec = s.run("MATCH (n:Entity) OPTIONAL MATCH (n)-[r]-() "
                        "RETURN count(DISTINCT n) as te, count(DISTINCT r) as tr").single()
            return {"total_entities":rec["te"],"total_relationships":rec["tr"],
                    "entities_by_type":[],"backend":"Neo4j"}

    def find_paths(self, s, t, m=5):
        with self.driver.session() as ss:
            r = ss.run(f"MATCH p = (a:Entity {{id:$s}})-[*1..{m}]-(b:Entity {{id:$t}}) "
                       "RETURN p LIMIT 10", s=s, t=t)
            return [list(rec["p"].nodes) for rec in r]

    def full_export(self):
        with self.driver.session() as s:
            n = [dict(rec["n"]) for rec in s.run("MATCH (n:Entity) RETURN n")]
            e = [{"source":rec["a.id"],"target":rec["b.id"],"type":rec["r"].get("type","")}
                 for rec in s.run("MATCH (a:Entity)-[r]->(b:Entity) RETURN a.id, b.id, r")]
            return {"nodes":n,"edges":e}

    def clear_session_data(self, sid):
        with self.driver.session() as s:
            return s.run("MATCH (n:Entity) WHERE n.metadata CONTAINS $sid "
                         "DETACH DELETE n RETURN count(n) as c", sid=sid).single()["c"]

    def disconnect(self): self.driver.close()

def create_graph_manager():
    if has_neo4j():
        try: return Neo4jGraphManager()
        except Exception as e: logger.warning(f"[Graph] Neo4j fail: {e}")
    return NetworkXGraphManager()


class GraphManager:
    """Wrapper that delegates to NetworkX or Neo4j backend."""
    def __init__(self):
        self._backend = create_graph_manager()

    @property
    def connected(self):
        return self._backend.connected

    def __getattr__(self, name):
        return getattr(self._backend, name)
