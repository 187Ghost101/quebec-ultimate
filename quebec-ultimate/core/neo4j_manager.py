"""Neo4j Graph Manager - optional backend"""
from typing import Dict, List, Optional
from datetime import datetime
from config import config
from core.logger import logger


class Neo4jGraphManager:
    def __init__(self):
        from neo4j import GraphDatabase
        self.driver = GraphDatabase.driver(
            config.NEO4J_URI,
            auth=(config.NEO4J_USER, config.NEO4J_PASSWORD),
            connection_timeout=3,
        )
        try:
            self.driver.verify_connectivity()
            self.connected = True
            logger.info("[Graph-Neo4j] Connecte")
        except Exception as e:
            self.connected = False
            logger.error(f"[Graph-Neo4j] Connexion echouee: {e}")
            raise

    def create_entity(self, entity_id, entity_type, value, source,
                      confidence, metadata):
        try:
            with self.driver.session() as s:
                s.run(
                    """MERGE (e:Entity {id: $id})
                       ON CREATE SET e.type=$type, e.value=$value,
                                     e.source=$source, e.confidence=$confidence,
                                     e.metadata=$metadata, e.created_at=datetime()
                       ON MATCH SET e.confidence = CASE WHEN $confidence > e.confidence
                                                    THEN $confidence ELSE e.confidence END
                       RETURN e""",
                    id=entity_id, type=entity_type, value=str(value),
                    source=source, confidence=confidence,
                    metadata=str(metadata or {}),
                )
            return True
        except Exception:
            return False

    def create_relationship(self, source_id, target_id, rel_type, weight, evidence):
        try:
            with self.driver.session() as s:
                s.run(
                    """MATCH (a:Entity {id: $s}), (b:Entity {id: $t})
                       MERGE (a)-[r:REL {type: $type}]->(b)
                       ON CREATE SET r.weight=$w, r.evidence=$ev, r.created_at=datetime()
                       RETURN r""",
                    s=source_id, t=target_id, type=rel_type,
                    w=weight, ev=evidence,
                )
            return True
        except Exception:
            return False

    def get_entity(self, eid):
        try:
            with self.driver.session() as s:
                r = s.run("MATCH (e:Entity {id:$id}) RETURN e", id=eid).single()
                if r:
                    return dict(r["e"])
        except Exception:
            pass
        return None

    def get_neighborhood(self, eid, depth=2):
        try:
            with self.driver.session() as s:
                result = s.run(
                    """MATCH path = (e:Entity {id:$id})-[*1..""" + str(depth) +
                    """]-(n)
                    RETURN DISTINCT nodes(path) AS nodes, relationships(path) AS rels""",
                    id=eid,
                )
                nodes = set()
                edges = []
                for record in result:
                    for n in record["nodes"]:
                        nodes.add(dict(n))
                    for r in record["rels"]:
                        edges.append({
                            "source": r.start_node["id"],
                            "target": r.end_node["id"],
                            "type": r.get("type", ""),
                            "weight": r.get("weight", 1.0),
                            "evidence": r.get("evidence", ""),
                        })
                return {"nodes": list(nodes), "edges": edges}
        except Exception:
            return {"nodes": [], "edges": []}

    def search_entities(self, q, limit=20):
        try:
            with self.driver.session() as s:
                result = s.run(
                    """MATCH (e:Entity)
                       WHERE toLower(e.value) CONTAINS toLower($q)
                          OR toLower(e.type) CONTAINS toLower($q)
                       RETURN e LIMIT $limit""",
                    q=q, limit=limit,
                )
                return [dict(r["e"]) for r in result]
        except Exception:
            return []

    def get_graph_stats(self):
        try:
            with self.driver.session() as s:
                total_e = s.run("MATCH (e:Entity) RETURN count(e) AS c").single()["c"]
                total_r = s.run("MATCH ()-[r:REL]->() RETURN count(r) AS c").single()["c"]
                type_counts = s.run(
                    """MATCH (e:Entity) RETURN e.type AS t, count(e) AS c
                       ORDER BY c DESC"""
                )
                return {
                    "total_entities": total_e,
                    "total_relationships": total_r,
                    "entities_by_type": [{"type": r["t"], "count": r["c"]} for r in type_counts],
                    "connected": True,
                }
        except Exception:
            return {"total_entities": 0, "total_relationships": 0, "connected": False}

    def find_paths(self, source, target, max_depth=5):
        try:
            with self.driver.session() as s:
                result = s.run(
                    """MATCH p = (a:Entity {id:$s})-[*1..""" + str(max_depth) +
                    """]-(b:Entity {id:$t})
                    RETURN p LIMIT 20""",
                    s=source, t=target,
                )
                paths = []
                for r in result:
                    path = r["p"]
                    nodes = [n["id"] for n in path.nodes]
                    edges = []
                    for rel in path.relationships:
                        edges.append({
                            "from": rel.start_node["id"],
                            "to": rel.end_node["id"],
                            "type": rel.get("type", ""),
                            "weight": rel.get("weight", 1.0),
                        })
                    paths.append({"length": len(nodes) - 1, "nodes": nodes, "edges": edges})
                return paths
        except Exception:
            return []

    def full_export(self):
        try:
            with self.driver.session() as s:
                nodes = [dict(r["e"]) for r in s.run("MATCH (e:Entity) RETURN e")]
                edges = []
                for r in s.run("MATCH (a)-[r:REL]->(b) RETURN a.id AS s, b.id AS t, r"):
                    edges.append({
                        "source": r["s"],
                        "target": r["t"],
                        "type": r["r"].get("type", ""),
                        "weight": r["r"].get("weight", 1.0),
                    })
                return {"nodes": nodes, "edges": edges}
        except Exception:
            return {"nodes": [], "edges": []}

    def clear_session_data(self, session_id):
        try:
            with self.driver.session() as s:
                # Would need session metadata stored as node property
                return 0
        except Exception:
            return 0

    def disconnect(self):
        try:
            self.driver.close()
        except Exception:
            pass